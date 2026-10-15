"""The built-in constraint kinds. Every threshold comes from the constraint's configured
`params`; none is a code literal."""

from __future__ import annotations

from nextmove.config.models import ConstraintSpec
from nextmove.decisions.actions import Candidate
from nextmove.decisions.context import DecisionContext
from nextmove.rules.registry import Verdict, register_constraint

__all__ = [
    "DiscountCeiling",
    "FatiguePenalty",
    "FrequencyCap",
    "InventoryScarcity",
    "MarginFloor",
]

_OK = Verdict(violated=False)


class _Base:
    def __init__(self, spec: ConstraintSpec) -> None:
        self.spec = spec

    def _param(self, key: str) -> float:
        if key not in self.spec.params:
            raise KeyError(f"constraint {self.spec.name!r} requires param {key!r}")
        return float(self.spec.params[key])  # type: ignore[arg-type]


@register_constraint("discount_ceiling")
class DiscountCeiling(_Base):
    """No discount above the configured ceiling (a Tier 3, human-only boundary)."""

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict:
        ceiling = self._param("max_discount_bps")
        if candidate.discount_bps > ceiling:
            return Verdict(
                True, f"{candidate.discount_bps} bps exceeds the {int(ceiling)} bps ceiling"
            )
        return _OK


@register_constraint("margin_floor")
class MarginFloor(_Base):
    """The category margin left after a discount must stay at or above the floor."""

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict:
        if candidate.discount_bps <= 0:
            return _OK
        floor = self._param("min_margin_rate_after_discount")
        remaining = context.margin_rate - candidate.discount_bps / 10_000
        if remaining < floor - 1e-12:
            return Verdict(
                True,
                f"margin after discount {remaining:.0%} is below the {floor:.0%} floor",
            )
        return _OK


@register_constraint("inventory_scarcity")
class InventoryScarcity(_Base):
    """Suppress demand-boosting archetypes while the customer's category is low on stock."""

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict:
        archetypes = self.spec.params.get("archetypes", [])
        if candidate.archetype not in archetypes:
            return _OK
        if context.business.is_scarce(context.primary_category):
            units = context.business.category_min_stock_units[context.primary_category]
            return Verdict(
                True,
                f"stock for {context.primary_category} is {units} units, at or below the "
                f"{context.business.low_stock_threshold}-unit threshold",
            )
        return _OK


@register_constraint("frequency_cap")
class FrequencyCap(_Base):
    """No further contact once the trailing-window contact count reaches the cap."""

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict:
        if not candidate.contact:
            return _OK
        cap = int(self._param("max_contacts"))
        window = int(self._param("window_days"))
        recent = context.contacts_within(window)
        if recent >= cap:
            return Verdict(True, f"{recent} contacts in the last {window} days (cap {cap})")
        return _OK


@register_constraint("fatigue_penalty")
class FatiguePenalty(_Base):
    """Graded cost of contacting a customer who was contacted recently."""

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict:
        if not candidate.contact:
            return _OK
        window = int(self._param("window_days"))
        recent = context.contacts_within(window)
        if recent == 0:
            return _OK
        penalty = recent * self._param("penalty_cents_per_recent_contact")
        return Verdict(True, f"{recent} contacts in the last {window} days", penalty)
