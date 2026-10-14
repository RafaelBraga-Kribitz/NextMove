"""The four comparison baselines of AC-10: do-nothing, always-discount, top-seller and a
hand-written rules-only CRM playbook. All thresholds come from `config/policies.yaml`."""

from __future__ import annotations

from nextmove.config.models import BaselinesConfig
from nextmove.decisions.actions import Candidate
from nextmove.decisions.context import DecisionContext
from nextmove.policies.base import ScoredCandidate, preference_scores

__all__ = [
    "AlwaysDiscountPolicy",
    "DoNothingPolicy",
    "RulesOnlyPolicy",
    "TopSellerPolicy",
    "baseline_policies",
]


class _Baseline:
    name = "baseline"

    @property
    def model_versions(self) -> dict[str, str]:
        return {}


class DoNothingPolicy(_Baseline):
    name = "do_nothing"

    def score(self, context, survivors, penalties_cents) -> list[ScoredCandidate]:
        return preference_scores(survivors, "none", "Do-nothing baseline")


class AlwaysDiscountPolicy(_Baseline):
    """The largest discount the constraints allow; nothing if none is allowed."""

    name = "always_discount"

    def score(self, context, survivors, penalties_cents) -> list[ScoredCandidate]:
        discounts = [c for c in survivors if c.discount_bps > 0]
        best = max(discounts, key=lambda c: (c.discount_bps, c.id), default=None)
        return preference_scores(
            survivors, best.id if best else None, "Always-discount baseline: largest allowed"
        )


class TopSellerPolicy(_Baseline):
    name = "top_seller"

    def __init__(self, config: BaselinesConfig) -> None:
        self._target = config.top_seller_candidate

    def score(self, context, survivors, penalties_cents) -> list[ScoredCandidate]:
        return preference_scores(survivors, self._target, "Top-seller baseline")


class RulesOnlyPolicy(_Baseline):
    """A hand-written CRM playbook over observable features (see config/policies.yaml)."""

    name = "rules_only"

    def __init__(self, config: BaselinesConfig) -> None:
        self._rules = config.rules_only

    def _choose(self, context: DecisionContext) -> tuple[str | None, str]:
        rules = self._rules
        features = context.features
        cart = features.get("cart_state_units") or 0
        proxy = features.get("price_sensitivity_proxy") or 0.0
        visits = features.get("session_visits_count") or 0
        recency = features.get("rfm_recency_days")
        if cart >= rules.cart_units_min and proxy >= rules.price_sensitivity_proxy_min:
            return rules.discount_candidate, "Playbook: items in cart and buys on discount"
        if visits >= rules.engaged_sessions_min:
            return rules.engaged_candidate, "Playbook: engaged browser"
        if recency is not None and recency >= rules.lapsed_recency_days_min:
            return rules.lapsed_candidate, "Playbook: lapsing customer"
        return None, "Playbook: no rule matched"

    def score(
        self, context: DecisionContext, survivors: list[Candidate], penalties_cents
    ) -> list[ScoredCandidate]:
        target, note = self._choose(context)
        return preference_scores(survivors, target or "none", note)


def baseline_policies(config: BaselinesConfig) -> list:
    return [
        DoNothingPolicy(),
        AlwaysDiscountPolicy(),
        TopSellerPolicy(config),
        RulesOnlyPolicy(config),
    ]
