"""Example plugin (AC-13): a new Constraint kind and a new ActionProvider, added purely through
the public registries, with zero edits to any module under `src/nextmove/`.

- `quiet_after_purchase` (constraint kind): no contact within N days of the customer's last
  order, read from the `rfm_recency_days` feature. Configure it like any built-in kind.
- `loyalty_points` (action provider): a points-boost message, a non-price retention action.

Usage: import this module once (it registers both), add a `quiet_after_purchase` entry to the
constraint config, and pass `"loyalty_points"` to `build_providers`.
"""

from __future__ import annotations

from nextmove.config.models import ActionsConfig, ConstraintSpec
from nextmove.decisions.actions import Candidate, register_action_provider
from nextmove.decisions.context import DecisionContext
from nextmove.rules import Verdict, register_constraint


@register_constraint("quiet_after_purchase")
class QuietAfterPurchase:
    def __init__(self, spec: ConstraintSpec) -> None:
        self.spec = spec

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict:
        if not candidate.contact:
            return Verdict(False)
        recency = context.features.get("rfm_recency_days")
        quiet_days = float(self.spec.params["quiet_days"])  # type: ignore[arg-type]
        if recency is not None and recency < quiet_days:
            return Verdict(True, f"ordered {int(recency)} days ago (quiet period {quiet_days:g})")
        return Verdict(False)


@register_action_provider("loyalty_points")
class LoyaltyPointsProvider:
    name = "loyalty_points"

    def __init__(self, config: ActionsConfig) -> None:
        self._candidate = Candidate(
            id="loyalty_points__double",
            archetype="loyalty_points",
            params={"multiplier": 2, "channel": "email"},
            contact=True,
            cost_cents=8,
        )

    def expand(self, context: DecisionContext) -> list[Candidate]:
        return [self._candidate]
