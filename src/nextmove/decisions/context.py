"""The point-in-time inputs one decision is made from (`DECISION_ENGINE_DESIGN.md` §2).

A `DecisionContext` is assembled from observable data only: the customer's feature-grid row as
of `as_of`, their contact history, and the business state (inventory, margins, prices) at the
same instant. Simulator latent traits never appear here; missing values are explicit `None`,
never silently imputed at this layer.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["BusinessState", "DecisionContext"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BusinessState(_Frozen):
    """Business context at decision time, per product category."""

    category_min_stock_units: dict[str, int]
    low_stock_threshold: int = Field(ge=0)
    category_margin_rate: dict[str, float]
    category_avg_price_cents: dict[str, int]
    top_seller_category: str = Field(min_length=1)

    def is_scarce(self, category: str) -> bool:
        units = self.category_min_stock_units.get(category)
        return units is not None and units <= self.low_stock_threshold


class DecisionContext(_Frozen):
    """Everything a policy may look at for one customer at one instant."""

    customer_id: str = Field(min_length=1)
    as_of: datetime
    primary_category: str = Field(min_length=1)
    features: dict[str, float | None]
    contact_days_ago: tuple[int, ...] = Field(
        default=(), description="Days since each past contact, most recent first."
    )
    business: BusinessState

    def contacts_within(self, window_days: int) -> int:
        """Contacts in the trailing `window_days` (a contact `0` days ago counts)."""
        return sum(1 for days in self.contact_days_ago if days < window_days)

    @property
    def margin_rate(self) -> float:
        return self.business.category_margin_rate[self.primary_category]

    @property
    def order_value_cents(self) -> int:
        return self.business.category_avg_price_cents[self.primary_category]
