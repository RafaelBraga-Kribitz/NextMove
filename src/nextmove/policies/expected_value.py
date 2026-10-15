"""The expected-value policy (C1, `DECISION_ENGINE_DESIGN.md` §1):

    score(a) = E[uplift(a)] x value - cost(a) - soft penalties(a) - risk_aversion x sd(a)

`wait` delivers nothing inside the decision horizon, so it is priced exactly like `none` (its
purpose is re-evaluation, not a response); ties go to `none`.

computed per ensemble member as incremental profit versus doing nothing, in cents:

    profit_b(a) = p_b(a) * V * (margin - discount(a)) - p_b(none) * V * margin - cost(a)

where `p_b` is member `b`'s calibrated purchase probability and `V` the category's average
order value. `none` therefore scores exactly 0 with zero spread, which makes restraint the
natural fallback whenever an action's expected gain does not clear its uncertainty. The
confidence of a choice is the share of ensemble members under which it ranks first.
"""

from __future__ import annotations

import numpy as np

from nextmove.config.models import ExpectedValuePolicyConfig
from nextmove.decisions.actions import Candidate
from nextmove.decisions.context import DecisionContext
from nextmove.models.features import context_row
from nextmove.models.response import ResponseModel
from nextmove.policies.base import ScoredCandidate

__all__ = ["ExpectedValuePolicy"]

_NO_DELIVERY = frozenset({"none", "wait"})


class ExpectedValuePolicy:
    def __init__(
        self,
        model: ResponseModel,
        config: ExpectedValuePolicyConfig,
        categories: list[str],
        top_k: int,
        name: str | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self.categories = categories
        self.top_k = top_k
        self.name = name or f"expected_value_{model.family}"
        self._cache: dict[
            tuple[str, str], tuple[np.ndarray, dict[tuple[str, int], np.ndarray]]
        ] = {}

    @property
    def model_versions(self) -> dict[str, str]:
        return {"response_model": self.model.version}

    def prepare(self, contexts: list[DecisionContext], candidates: list[Candidate]) -> None:
        """Batch-predict every (context, action) pair needed by `score`."""
        self._cache.clear()
        if not contexts:
            return
        x = np.asarray([context_row(c, self.categories) for c in contexts], dtype=float)
        keys = sorted({(c.archetype, c.discount_bps) for c in candidates} | {("none", 0)})
        known = set(self.model.archetypes)
        preds = {}
        for archetype, bps in keys:
            if archetype not in known:
                continue
            preds[(archetype, bps)] = self.model.predict_members(
                x, [archetype] * len(x), [bps / 10_000] * len(x)
            )
        for index, context in enumerate(contexts):
            self._cache[(context.customer_id, context.as_of.isoformat())] = (
                x[index],
                {key: value[index] for key, value in preds.items()},
            )

    def _lookup(self, context: DecisionContext, survivors: list[Candidate]):
        key = (context.customer_id, context.as_of.isoformat())
        needed = {
            (c.archetype, c.discount_bps) for c in survivors if c.archetype in self.model.archetypes
        }
        cached = self._cache.get(key)
        if cached is None or not needed <= set(cached[1]):
            self.prepare([context], survivors)
            cached = self._cache[key]
        return cached

    def score(
        self,
        context: DecisionContext,
        survivors: list[Candidate],
        penalties_cents: dict[str, float],
    ) -> list[ScoredCandidate]:
        x_row, preds = self._lookup(context, survivors)
        value = float(context.order_value_cents)
        margin = float(context.margin_rate)
        p_none = preds[("none", 0)]
        lam = self.config.risk_aversion
        q_low, q_high = self.config.interval_quantiles
        profits: dict[str, np.ndarray] = {}
        uplifts: dict[str, np.ndarray] = {}
        for candidate in survivors:
            key = (candidate.archetype, candidate.discount_bps)
            if candidate.archetype in _NO_DELIVERY or key not in preds:
                # Restraint delivers nothing inside the horizon: identical to `none`.
                p = p_none
                profit = np.zeros_like(p_none) - candidate.cost_cents
            else:
                p = preds[key]
                discount = candidate.discount_bps / 10_000
                profit = (
                    p * value * (margin - discount) - p_none * value * margin - candidate.cost_cents
                )
            penalty = penalties_cents.get(candidate.id, 0.0)
            profits[candidate.id] = profit - penalty
            uplifts[candidate.id] = p - p_none
        ids = [c.id for c in survivors]
        stacked = np.stack([profits[i] for i in ids])  # (n_candidates, n_members)
        winners = np.argmax(stacked, axis=0)
        win_counts = np.bincount(winners, minlength=len(ids))
        scored = []
        for index, candidate in enumerate(survivors):
            member_profit = profits[candidate.id]
            uplift = uplifts[candidate.id]
            sd = float(member_profit.std())
            penalty = penalties_cents.get(candidate.id, 0.0)
            mean_profit = float(member_profit.mean())
            score = mean_profit - lam * sd
            scored.append(
                ScoredCandidate(
                    candidate=candidate,
                    score=score,
                    uplift=float(uplift.mean()),
                    uplift_interval=(
                        float(np.quantile(uplift, q_low)),
                        float(np.quantile(uplift, q_high)),
                    ),
                    value_cents=mean_profit + penalty + candidate.cost_cents,
                    cost_cents=float(candidate.cost_cents),
                    risk_penalty_cents=float(penalty + lam * sd),
                    win_rate=float(win_counts[index] / stacked.shape[1]),
                    extra={"expected_profit_cents": mean_profit + penalty, "profit_sd_cents": sd},
                )
            )
        return scored

    def explain(self, context: DecisionContext, candidate: Candidate) -> list[tuple[str, float]]:
        """Top-k signed uplift attributions for the chosen candidate (empty for `none`)."""
        if candidate.archetype not in self.model.archetypes or candidate.archetype == "none":
            return []
        x_row = np.asarray(context_row(context, self.categories), dtype=float)
        pairs = self.model.uplift_attributions(
            x_row, candidate.archetype, candidate.discount_bps / 10_000
        )
        pairs = [p for p in pairs if abs(p[1]) > 0]
        pairs.sort(key=lambda p: (-abs(p[1]), p[0]))
        return [(name, round(weight, 6)) for name, weight in pairs[: self.top_k]]
