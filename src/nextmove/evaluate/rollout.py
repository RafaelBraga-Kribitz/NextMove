"""The shared simulated rollout loop behind the randomized experiment and the policy replay.

For each decision day, every eligible customer gets a point-in-time context (including the
contacts this rollout has already made), the candidates that survive the hard constraints, and
one choice from a `Chooser`. The outcome is drawn from the `OutcomeOracle` with common random
numbers (one uniform draw per customer and day, shared by every policy), and delivered contacts
feed back into later contexts (frequency caps, fatigue) and into the oracle's contact counter.

Money is accounted per decision, in cents:

    profit = converted * order_value * (margin_rate - discount_rate) - contact_cost

where `order_value` and `margin_rate` are the business reference values of the customer's
primary category (historical average order value, catalog margin). `expected_profit` replaces
`converted` with the ground-truth probability, which removes outcome noise from comparisons.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from nextmove.config.models import ActionsConfig
from nextmove.decisions.actions import ActionProvider, Candidate, generate_candidates
from nextmove.decisions.assembly import ContextStore
from nextmove.decisions.context import DecisionContext
from nextmove.evaluate.world import OutcomeOracle, common_random_numbers
from nextmove.rules import FilterOutcome, RuleSet

__all__ = ["Choice", "Chooser", "RolloutSpec", "rollout"]


@dataclass(frozen=True)
class Choice:
    candidate: Candidate
    extra: dict[str, object] = field(default_factory=dict)


#: Given a day, its contexts and their constraint outcomes, return one choice per context.
Chooser = Callable[[int, list[DecisionContext], list[FilterOutcome]], list[Choice]]


@dataclass(frozen=True)
class RolloutSpec:
    days: Sequence[int]
    outcome_seed: int
    record_features: Callable[[DecisionContext], list[float]] | None = None
    feature_names: Sequence[str] = ()
    customers: Sequence[str] | None = None


def rollout(
    store: ContextStore,
    oracle: OutcomeOracle,
    rules: RuleSet,
    providers: list[ActionProvider],
    actions: ActionsConfig,
    chooser: Chooser,
    spec: RolloutSpec,
) -> pd.DataFrame:
    """Run `chooser` over `spec.days` and return one row per decision."""
    contacts: dict[str, list[int]] = {}
    deliveries: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    feature_rows: list[list[float]] = []
    only = set(spec.customers) if spec.customers is not None else None
    for day in spec.days:
        day_rows = store.day_rows(day)
        customer_ids = store.eligible_customers(day, day_rows)
        if only is not None:
            customer_ids = [cid for cid in customer_ids if cid in only]
        if not customer_ids:
            continue
        business = store.business_state(day)
        contexts = [
            store.context(cid, day, contacts.get(cid, ()), business=business, row=day_rows[cid])
            for cid in customer_ids
        ]
        outcomes = []
        for context in contexts:
            candidates = generate_candidates(context, providers, actions)
            outcomes.append(rules.apply(candidates, context))
        choices = chooser(day, contexts, outcomes)
        draws = common_random_numbers(spec.outcome_seed, day, oracle.n_customers)
        for context, outcome, choice in zip(contexts, outcomes, choices, strict=True):
            cid = context.customer_id
            candidate = choice.candidate
            prior = len(store.exposure_days_before(cid, day)) + deliveries.get(cid, 0)
            p_action = oracle.p_convert(cid, day, candidate.archetype, candidate.params, prior)
            p_none = oracle.p_convert(cid, day, "none", {}, prior)
            u = float(draws[int(cid)])
            converted = u < p_action
            value = float(context.order_value_cents)
            margin = float(context.margin_rate)
            discount_rate = candidate.discount_bps / 10_000
            unit_profit = value * (margin - discount_rate)
            unit_profit_none = value * margin
            record: dict[str, object] = {
                "customer_id": cid,
                "day": day,
                "primary_category": context.primary_category,
                "candidate_id": candidate.id,
                "archetype": candidate.archetype,
                "discount_bps": candidate.discount_bps,
                "contact": candidate.contact,
                "n_survivors": len(outcome.survivors),
                "n_filtered": len(outcome.filtered),
                "fired_rules": ",".join(outcome.fired_rules),
                "recent_contacts_7d": int(context.features.get("contacts_7d") or 0),
                "prior_contacts": prior,
                "p_action": p_action,
                "p_none": p_none,
                "draw": u,
                "converted": bool(converted),
                "would_buy_anyway": bool(u < p_none),
                "order_value_cents": value,
                "margin_rate": margin,
                "profit_cents": (unit_profit if converted else 0.0) - candidate.cost_cents,
                "profit_none_cents": unit_profit_none if u < p_none else 0.0,
                "expected_profit_cents": p_action * unit_profit - candidate.cost_cents,
                "expected_profit_none_cents": p_none * unit_profit_none,
            }
            record.update(choice.extra)
            rows.append(record)
            if spec.record_features is not None:
                feature_rows.append(spec.record_features(context))
            if candidate.archetype not in ("none", "wait"):
                deliveries[cid] = deliveries.get(cid, 0) + 1
            if candidate.contact:
                contacts.setdefault(cid, []).append(day)
    frame = pd.DataFrame(rows)
    if spec.record_features is not None and len(frame):
        features = pd.DataFrame(np.asarray(feature_rows), columns=list(spec.feature_names))
        frame = pd.concat([frame, features], axis=1)
    return frame
