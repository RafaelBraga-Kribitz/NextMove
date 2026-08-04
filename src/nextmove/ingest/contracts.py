"""The one canonical event schema the whole project is built on (DATA-01).

Every event that reaches a canonical table — whether emitted by the simulator or mapped in
by a future adapter (D-13) — is an `Event` instance: `event(event_id, customer_id,
session_id, ts, type, payload, source)` with a typed `payload` per event `type`. This module
is the project's only input-validation surface for events; nothing downstream re-validates.

Two properties matter more than the rest and are enforced structurally, not by convention:

- **Timezone safety** (RESEARCH Pitfall 1): a naive `ts` is rejected outright rather than
  silently interpreted as local time, because a naive/aware comparison mid-pipeline breaks
  monotonicity checks and ASOF joins in ways that are easy to miss in review.
- **Deterministic identity**: `derive_event_id` is a stable hash over an event's own
  identifying tuple, never a random generator, so two seeded runs produce identical event
  ids and the canonical table can be byte-identical (a precondition for ENG-04).

Money is an exact integer count of minor units (cents) on every payload field that carries
it. No monetary field anywhere in this module is a non-integer number type — text formatting
of non-integer numbers is a documented source of byte-level instability (RESEARCH Pitfall 3),
and cents already are money's exact minor unit.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "1.0.0"

# Fixed, hardcoded namespace for event-id derivation (uuid.uuid5). Never regenerate this
# value — every id derived from this namespace changes if it does, breaking ENG-04's
# byte-identical claim for every previously-generated dataset.
EVENT_ID_NAMESPACE = uuid.UUID("7c1de923-3e3a-4b0a-9b3b-1f7b6d6a9b3e")


class EventType(StrEnum):
    """One member per canonical event kind the simulator (or a future adapter) emits."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRODUCT_VIEW = "product_view"
    ADD_TO_CART = "add_to_cart"
    CART_REMOVE = "cart_remove"
    CART_ABANDON = "cart_abandon"
    ORDER_PLACED = "order_placed"
    CAMPAIGN_EXPOSURE = "campaign_exposure"
    ACTION_DELIVERED = "action_delivered"
    OVERRIDE = "override"
    SCROLL = "scroll"
    FILTER_APPLY = "filter_apply"
    DWELL = "dwell"


class StrictPayload(BaseModel):
    """Shared payload base: unknown keys fail loudly, instances are immutable once built."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------------------
# Session events
# ---------------------------------------------------------------------------------------


class SessionStartPayload(StrictPayload):
    type: Literal["session_start"]
    device: Literal["desktop", "mobile", "tablet"]


class SessionEndPayload(StrictPayload):
    type: Literal["session_end"]
    duration_s: int = Field(ge=0)


# ---------------------------------------------------------------------------------------
# Browse / cart events
# ---------------------------------------------------------------------------------------


class ProductViewPayload(StrictPayload):
    type: Literal["product_view"]
    sku: str = Field(min_length=1)
    category: str = Field(min_length=1)
    unit_price_cents: int = Field(ge=0)


class AddToCartPayload(StrictPayload):
    type: Literal["add_to_cart"]
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)


class CartRemovePayload(StrictPayload):
    type: Literal["cart_remove"]
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)


class CartAbandonPayload(StrictPayload):
    type: Literal["cart_abandon"]
    cart_value_cents: int = Field(ge=0)


# ---------------------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------------------


class OrderLineItem(StrictPayload):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)
    discount_cents: int = Field(ge=0)


class OrderPlacedPayload(StrictPayload):
    type: Literal["order_placed"]
    order_id: str = Field(min_length=1)
    line_items: list[OrderLineItem] = Field(min_length=1)
    order_total_cents: int = Field(ge=0)


# ---------------------------------------------------------------------------------------
# Campaigns and actions
# ---------------------------------------------------------------------------------------


class CampaignExposurePayload(StrictPayload):
    type: Literal["campaign_exposure"]
    campaign_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class ActionDeliveredPayload(StrictPayload):
    type: Literal["action_delivered"]
    action_type: str = Field(min_length=1)
    params: dict[str, str | int]


class OverridePayload(StrictPayload):
    type: Literal["override"]
    decision_id: str = Field(min_length=1)
    chosen_action_type: str = Field(min_length=1)
    manager_note: str = Field(min_length=1)


# ---------------------------------------------------------------------------------------
# Micro-conversion (PCR) events (SIM-04). Emitted as a class, never a weight or a
# conversion probability — deriving how much a micro-action predicts a macro conversion is
# Phase 4 work per D-06; shipping a number here would be a guess wearing a derived number's
# clothes.
# ---------------------------------------------------------------------------------------


class ScrollPayload(StrictPayload):
    type: Literal["scroll"]
    depth_pct: int = Field(ge=0, le=100)


class FilterApplyPayload(StrictPayload):
    type: Literal["filter_apply"]
    facet: str = Field(min_length=1)
    value: str = Field(min_length=1)


class DwellPayload(StrictPayload):
    type: Literal["dwell"]
    dwell_class: Literal["short", "medium", "long"]
    sku: str = Field(min_length=1)


EventPayload = (
    SessionStartPayload
    | SessionEndPayload
    | ProductViewPayload
    | AddToCartPayload
    | CartRemovePayload
    | CartAbandonPayload
    | OrderPlacedPayload
    | CampaignExposurePayload
    | ActionDeliveredPayload
    | OverridePayload
    | ScrollPayload
    | FilterApplyPayload
    | DwellPayload
)


class Event(BaseModel):
    """The canonical event row: `event(event_id, customer_id, session_id, ts, type, payload,
    source)` (DATA-01). Unknown keys fail loudly and instances are immutable once built.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    ts: datetime
    type: EventType
    payload: EventPayload = Field(discriminator="type")
    source: Literal["simulator", "adapter"]

    @field_validator("ts", mode="after")
    @classmethod
    def _reject_naive_and_normalize_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "ts must be a timezone-aware datetime; a naive datetime for field 'ts' is "
                "rejected rather than silently interpreted as local time"
            )
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _check_payload_type_matches_event_type(self) -> "Event":
        if self.payload.type != self.type:
            raise ValueError(
                f"payload.type {self.payload.type!r} does not match event type {self.type!r}"
            )
        return self


def derive_event_id(
    customer_id: str,
    session_id: str,
    ts: datetime,
    event_type: EventType | str,
    seq: int,
) -> str:
    """Derive a deterministic event id from an event's own identifying tuple.

    Never a random generator: the same identifying tuple always derives the same id, in this
    process or any other, which is the precondition for two seeded runs producing an
    identical canonical table.
    """
    if ts.tzinfo is None:
        raise ValueError("derive_event_id requires a timezone-aware ts, got a naive datetime")
    ts_utc = ts.astimezone(UTC)
    canonical = "|".join([customer_id, session_id, ts_utc.isoformat(), str(event_type), str(seq)])
    return str(uuid.uuid5(EVENT_ID_NAMESPACE, canonical))


CANONICAL_SORT_KEY: tuple[str, str, str] = ("customer_id", "ts", "event_id")


def sort_events(events: list[Event]) -> list[Event]:
    """Return a new list of `events` sorted by `CANONICAL_SORT_KEY`.

    `event_id` is the tiebreak that makes the order total: two events sharing a customer and
    a timestamp always land in the same relative position, regardless of input order.
    """
    return sorted(events, key=lambda event: (event.customer_id, event.ts, event.event_id))
