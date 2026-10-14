"""The application service behind the HTTP API and the demo: the same decision engine the
batch replay uses, served on demand at any `as_of` (ADR-002: batch is the operational truth,
the identical engine also answers on demand).
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cached_property
from pathlib import Path

import pandas as pd

from nextmove.config.loader import ResolvedConfig
from nextmove.decisions.actions import build_providers, generate_candidates
from nextmove.decisions.assembly import ContextStore
from nextmove.decisions.context import DecisionContext
from nextmove.decisions.contract import Decision
from nextmove.decisions.engine import DecisionEngine
from nextmove.explain.templates import FEATURE_PHRASES
from nextmove.models.train import load_model
from nextmove.policies.expected_value import ExpectedValuePolicy
from nextmove.rules import RuleSet
from nextmove.storage import Zone, read_frame, table_exists

__all__ = ["DecisionService", "NotFound", "OverrideRejected"]


class NotFound(LookupError):
    pass


class OverrideRejected(ValueError):
    pass


class DecisionService:
    def __init__(self, resolved: ResolvedConfig, root: Path | None = None) -> None:
        self.resolved = resolved
        self.root = root
        config = resolved.config
        self.config = config
        self.train_end, self.validation_end, self.horizon = config.evaluation.windows(
            config.simulator.horizon_days
        )
        self.store = ContextStore(
            resolved, root, days=None, business_reference_cutoff=self.train_end
        )
        self.rules = RuleSet.from_config(config.constraints)
        self.providers = build_providers(config.actions, ["catalog"])
        self.family = self._selected_family()
        ev = config.policies.expected_value
        self.policy = ExpectedValuePolicy(
            load_model(self.family, root),
            ev,
            self.store.categories,
            config.models.attribution_top_k,
        )
        self.engine = DecisionEngine(
            self.policy,
            self.rules,
            self.providers,
            config.actions,
            resolved.config_hash,
            ev.min_confidence,
        )

    def _selected_family(self) -> str:
        configured = self.config.policies.expected_value.family
        if configured != "auto":
            return configured
        if table_exists("policy_summary", Zone.EVALUATION, self.root):
            summary = read_frame("policy_summary", Zone.EVALUATION, self.root)
            chosen = summary[summary["is_ml_policy"]]
            if len(chosen):
                return str(chosen["policy"].iloc[0]).removeprefix("expected_value_")
        return "gbm"

    # -- helpers ---------------------------------------------------------------------------

    def day_of(self, as_of: date) -> int:
        day = (as_of - self.config.simulator.start_date).days
        if not 0 <= day < self.horizon:
            raise NotFound(
                f"as_of {as_of.isoformat()} is outside the simulated horizon "
                f"({self.config.simulator.start_date.isoformat()} + {self.horizon} days)"
            )
        return day

    def default_as_of(self) -> date:
        """The first decision day of the held-out test window."""
        return self.config.simulator.start_date + timedelta(days=self.validation_end)

    def context(self, customer_id: str, as_of: date) -> DecisionContext:
        day = self.day_of(as_of)
        first = self.store.first_active_day(customer_id)
        if first is None or first >= day:
            raise NotFound(f"customer {customer_id!r} has no activity before {as_of.isoformat()}")
        try:
            return self.store.context(customer_id, day)
        except LookupError as error:
            raise NotFound(str(error)) from error

    # -- use cases -------------------------------------------------------------------------

    def decide(self, customer_id: str, as_of: date) -> Decision:
        return self.engine.decide(self.context(customer_id, as_of))

    def customer(self, customer_id: str, as_of: date) -> dict:
        context = self.context(customer_id, as_of)
        decision = self.engine.decide(context)
        segment = None
        if table_exists("segments", Zone.MODELS, self.root):
            segments = self._segments
            if customer_id in segments.index:
                segment = str(segments.loc[customer_id, "segment_name"])
        features = []
        for name, value in sorted(context.features.items()):
            features.append(
                {
                    "name": name,
                    "label": FEATURE_PHRASES.get(name, name.replace("_", " ")),
                    "value": value,
                }
            )
        return {
            "customer_id": customer_id,
            "as_of": as_of.isoformat(),
            "primary_category": context.primary_category,
            "segment": segment,
            "contacts_last_7_days": context.contacts_within(7),
            "contacts_total": len(context.contact_days_ago),
            "features": features,
            "decision": decision.model_dump(mode="json"),
            "overrides": [
                r.model_dump(mode="json") for r in self.overrides() if r.customer_id == customer_id
            ],
        }

    @cached_property
    def _segments(self) -> pd.DataFrame:
        return read_frame("segments", Zone.MODELS, self.root).set_index("customer_id")

    def candidates(self, customer_id: str, as_of: date) -> list[dict]:
        context = self.context(customer_id, as_of)
        candidates = generate_candidates(context, self.providers, self.config.actions)
        outcome = self.rules.apply(candidates, context)
        excluded = {r.candidate_id: r for r in outcome.filtered}
        return [
            {
                "candidate_id": c.id,
                "archetype": c.archetype,
                "allowed": c.id not in excluded,
                "rule": excluded[c.id].rule if c.id in excluded else None,
                "detail": excluded[c.id].detail if c.id in excluded else None,
            }
            for c in candidates
        ]

    def record_override(
        self,
        *,
        decision_id: str,
        customer_id: str,
        as_of: date,
        override_candidate: str,
        reason: str,
        operator: str,
    ) -> dict:
        from nextmove.evaluate.overrides import append_override

        decision = self.decide(customer_id, as_of)
        if decision.decision_id != decision_id:
            raise OverrideRejected(
                f"decision {decision_id!r} is not the current decision for customer "
                f"{customer_id!r} at {as_of.isoformat()} (current: {decision.decision_id})"
            )
        options = {c["candidate_id"]: c for c in self.candidates(customer_id, as_of)}
        option = options.get(override_candidate)
        if option is None:
            raise OverrideRejected(f"unknown action {override_candidate!r}")
        if not option["allowed"]:
            raise OverrideRejected(
                f"{override_candidate!r} is excluded by hard rule {option['rule']!r}: "
                f"{option['detail']}. Overrides may overrule the model, not the rules."
            )
        if override_candidate == decision.action.candidate_id:
            raise OverrideRejected("the override equals the engine's choice")
        record = append_override(
            self.root,
            decision_id=decision_id,
            customer_id=customer_id,
            day=self.day_of(as_of),
            original_candidate=decision.action.candidate_id,
            override_candidate=override_candidate,
            reason=reason,
            operator=operator,
        )
        return record.model_dump(mode="json")

    def overrides(self):
        from nextmove.evaluate.overrides import read_overrides

        return read_overrides(self.root)

    def override_evaluation(self) -> dict:
        """Live UC1 view: every override priced against the engine's choice (simulation)."""
        from nextmove.evaluate.overrides import evaluate_overrides
        from nextmove.evaluate.world import OutcomeOracle

        records = self.overrides()
        frame = evaluate_overrides(records, self.store, self._oracle(OutcomeOracle))
        return {
            "count": int(len(frame)),
            "net_effect_eur": float(frame["override_effect_cents"].sum() / 100)
            if len(frame)
            else 0.0,
            "overrides": frame.to_dict(orient="records"),
            "note": "Expected-profit effect in simulation only (ADR-004).",
        }

    def _oracle(self, factory):
        if not hasattr(self, "_oracle_instance"):
            self._oracle_instance = factory(self.resolved, self.root)
        return self._oracle_instance

    def policy_summary(self) -> list[dict]:
        if not table_exists("policy_summary", Zone.EVALUATION, self.root):
            return []
        return read_frame("policy_summary", Zone.EVALUATION, self.root).to_dict(orient="records")

    def sample_customers(self, as_of: date, limit: int = 25) -> list[str]:
        day = self.day_of(as_of)
        return self.store.eligible_customers(day)[:limit]
