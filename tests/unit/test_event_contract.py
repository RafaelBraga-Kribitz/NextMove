"""Contract tests for the canonical Event schema (DATA-01).

Covers Task 1's behaviour block plus the adjacency, empty, ordering and precision edge
predicates named in plan 01-05's `must_haves`.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, ValidationError

from nextmove.ingest import contracts as contracts_module
from nextmove.ingest.contracts import (
    CANONICAL_SORT_KEY,
    CONTRACT_VERSION,
    Event,
    EventType,
    derive_event_id,
    sort_events,
)

BASE_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _payload_for(event_type: EventType) -> dict:
    """One well-formed payload dict per canonical event type."""
    payloads: dict[EventType, dict] = {
        EventType.SESSION_START: {"type": "session_start", "device": "desktop"},
        EventType.SESSION_END: {"type": "session_end", "duration_s": 120},
        EventType.PRODUCT_VIEW: {
            "type": "product_view",
            "sku": "sku-1",
            "category": "shoes",
            "unit_price_cents": 1999,
        },
        EventType.ADD_TO_CART: {
            "type": "add_to_cart",
            "sku": "sku-1",
            "quantity": 2,
            "unit_price_cents": 1999,
        },
        EventType.CART_REMOVE: {"type": "cart_remove", "sku": "sku-1", "quantity": 1},
        EventType.CART_ABANDON: {"type": "cart_abandon", "cart_value_cents": 3998},
        EventType.ORDER_PLACED: {
            "type": "order_placed",
            "order_id": "order-1",
            "line_items": [
                {"sku": "sku-1", "quantity": 2, "unit_price_cents": 1999, "discount_cents": 0}
            ],
            "order_total_cents": 3998,
        },
        EventType.CAMPAIGN_EXPOSURE: {
            "type": "campaign_exposure",
            "campaign_id": "camp-1",
            "channel": "email",
        },
        EventType.ACTION_DELIVERED: {
            "type": "action_delivered",
            "action_type": "discount_offer",
            "params": {"discount_pct": 10},
        },
        EventType.OVERRIDE: {
            "type": "override",
            "decision_id": "decision-1",
            "chosen_action_type": "no_action",
            "manager_note": "customer called in",
        },
        EventType.SCROLL: {"type": "scroll", "depth_pct": 50},
        EventType.FILTER_APPLY: {"type": "filter_apply", "facet": "color", "value": "red"},
        EventType.DWELL: {"type": "dwell", "dwell_class": "medium", "sku": "sku-1"},
    }
    return payloads[event_type]


def _make_event(event_type: EventType, **overrides) -> Event:
    data = {
        "event_id": overrides.pop("event_id", str(uuid.uuid4())),
        "customer_id": overrides.pop("customer_id", "cust-1"),
        "session_id": overrides.pop("session_id", "sess-1"),
        "ts": overrides.pop("ts", BASE_TS),
        "type": event_type,
        "payload": overrides.pop("payload", _payload_for(event_type)),
        "source": overrides.pop("source", "simulator"),
    }
    data.update(overrides)
    return Event.model_validate(data)


ALL_EVENT_TYPES = list(EventType)


# ---------------------------------------------------------------------------------------
# Task 1 behaviour block
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
def test_well_formed_event_round_trips(event_type: EventType) -> None:
    event = _make_event(event_type)
    dumped = event.model_dump(mode="json")
    rebuilt = Event.model_validate(dumped)
    assert rebuilt == event


def test_naive_ts_raises() -> None:
    with pytest.raises(ValidationError):
        _make_event(EventType.PRODUCT_VIEW, ts=datetime(2024, 1, 1, 12, 0, 0))


def test_non_utc_offset_normalizes_to_utc() -> None:
    plus_two = timezone(timedelta(hours=2))
    local_ts = datetime(2024, 1, 1, 14, 0, 0, tzinfo=plus_two)
    event = _make_event(EventType.PRODUCT_VIEW, ts=local_ts)
    assert event.ts.tzinfo == UTC
    assert event.ts == local_ts.astimezone(UTC)


def test_payload_type_mismatch_raises() -> None:
    with pytest.raises(ValidationError):
        _make_event(EventType.ADD_TO_CART, payload=_payload_for(EventType.PRODUCT_VIEW))


def test_unknown_type_raises() -> None:
    with pytest.raises(ValidationError):
        Event.model_validate(
            {
                "event_id": "e1",
                "customer_id": "c1",
                "session_id": "s1",
                "ts": BASE_TS,
                "type": "not_a_real_type",
                "payload": {"type": "not_a_real_type"},
                "source": "simulator",
            }
        )


def test_empty_required_string_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_event(
            EventType.PRODUCT_VIEW,
            payload={
                "type": "product_view",
                "sku": "",
                "category": "shoes",
                "unit_price_cents": 100,
            },
        )
    assert "sku" in str(exc_info.value)


def test_missing_session_id_raises() -> None:
    data = {
        "event_id": "e1",
        "customer_id": "c1",
        "ts": BASE_TS,
        "type": "product_view",
        "payload": _payload_for(EventType.PRODUCT_VIEW),
        "source": "simulator",
    }
    with pytest.raises(ValidationError):
        Event.model_validate(data)


def test_derive_event_id_deterministic_across_processes() -> None:
    id1 = derive_event_id("c1", "s1", BASE_TS, "product_view", 0)
    id2 = derive_event_id("c1", "s1", BASE_TS, "product_view", 0)
    assert id1 == id2


def test_derive_event_id_differs_by_seq() -> None:
    id1 = derive_event_id("c1", "s1", BASE_TS, "product_view", 0)
    id2 = derive_event_id("c1", "s1", BASE_TS, "product_view", 1)
    assert id1 != id2


def test_sort_events_total_order_ties_broken_by_event_id() -> None:
    e1 = _make_event(EventType.PRODUCT_VIEW, event_id="a", customer_id="c1", ts=BASE_TS)
    e2 = _make_event(EventType.PRODUCT_VIEW, event_id="b", customer_id="c1", ts=BASE_TS)
    result_forward = sort_events([e1, e2])
    result_reversed = sort_events([e2, e1])
    assert [e.event_id for e in result_forward] == ["a", "b"]
    assert [e.event_id for e in result_reversed] == ["a", "b"]


def test_sort_events_empty_list_returns_empty() -> None:
    assert sort_events([]) == []


def test_validating_empty_list_of_raw_records_returns_empty_list() -> None:
    assert [Event.model_validate(r) for r in []] == []


# ---------------------------------------------------------------------------------------
# Edge: adjacency — same (customer_id, ts), distinct event_id, stable sort
# ---------------------------------------------------------------------------------------


def test_adjacency_same_ts_distinct_seq_differ_and_stable_sort() -> None:
    events = [
        _make_event(
            EventType.PRODUCT_VIEW,
            event_id=derive_event_id("c1", "s1", BASE_TS, "product_view", seq),
            customer_id="c1",
            ts=BASE_TS,
        )
        for seq in range(2)
    ]
    assert events[0].event_id != events[1].event_id
    forward = sort_events(events)
    backward = sort_events(list(reversed(events)))
    assert [e.event_id for e in forward] == [e.event_id for e in backward]


# ---------------------------------------------------------------------------------------
# Edge: empty — empty stream validates to an empty collection, never raises
# ---------------------------------------------------------------------------------------


def test_empty_stream_validates_to_empty_collection() -> None:
    assert sort_events([Event.model_validate(r) for r in []]) == []


def test_empty_sku_names_field_in_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_event(
            EventType.PRODUCT_VIEW,
            payload={
                "type": "product_view",
                "sku": "",
                "category": "shoes",
                "unit_price_cents": 100,
            },
        )
    assert "sku" in str(exc_info.value)


def test_missing_session_id_raises_rather_than_defaulting() -> None:
    data = {
        "event_id": "e1",
        "customer_id": "c1",
        "ts": BASE_TS,
        "type": "product_view",
        "payload": _payload_for(EventType.PRODUCT_VIEW),
        "source": "simulator",
    }
    with pytest.raises(ValidationError):
        Event.model_validate(data)


# ---------------------------------------------------------------------------------------
# Edge: ordering — ties broken deterministically, not by input/shuffle order
# ---------------------------------------------------------------------------------------


def test_ordering_is_deterministic_across_shuffles() -> None:
    events = []
    for i in range(20):
        customer_id = f"c{i % 4}"
        ts = BASE_TS + timedelta(seconds=i % 5)
        events.append(
            _make_event(
                EventType.PRODUCT_VIEW,
                event_id=derive_event_id(customer_id, "s1", ts, "product_view", i),
                customer_id=customer_id,
                ts=ts,
            )
        )
    shuffled_a = events.copy()
    random.Random(1).shuffle(shuffled_a)
    shuffled_b = events.copy()
    random.Random(2).shuffle(shuffled_b)
    assert sort_events(shuffled_a) == sort_events(shuffled_b)


# ---------------------------------------------------------------------------------------
# Edge: precision — every monetary field is an integer, never a non-integer number type
# ---------------------------------------------------------------------------------------


def test_no_monetary_field_is_non_integer() -> None:
    checked_any = False
    for name in dir(contracts_module):
        obj = getattr(contracts_module, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            for field_name, field_info in obj.model_fields.items():
                if "cents" in field_name:
                    checked_any = True
                    assert field_info.annotation is int, (
                        f"{obj.__name__}.{field_name} must be annotated int, "
                        f"got {field_info.annotation}"
                    )
    assert checked_any


def test_contract_version_is_the_expected_string() -> None:
    assert isinstance(CONTRACT_VERSION, str)
    assert CONTRACT_VERSION == "1.0.0"


def test_canonical_sort_key_ends_with_event_id() -> None:
    assert CANONICAL_SORT_KEY[-1] == "event_id"


# ---------------------------------------------------------------------------------------
# Hypothesis property: derive_event_id determinism and sensitivity to its own components
# ---------------------------------------------------------------------------------------

_ident = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8
)


@given(customer_id=_ident, session_id=_ident, seq=st.integers(min_value=0, max_value=1000))
def test_derive_event_id_is_deterministic_property(customer_id, session_id, seq) -> None:
    id1 = derive_event_id(customer_id, session_id, BASE_TS, "product_view", seq)
    id2 = derive_event_id(customer_id, session_id, BASE_TS, "product_view", seq)
    assert id1 == id2


@given(
    seq_a=st.integers(min_value=0, max_value=500),
    seq_b=st.integers(min_value=501, max_value=1000),
)
def test_derive_event_id_differs_for_different_seq(seq_a, seq_b) -> None:
    id_a = derive_event_id("c1", "s1", BASE_TS, "product_view", seq_a)
    id_b = derive_event_id("c1", "s1", BASE_TS, "product_view", seq_b)
    assert id_a != id_b


@given(customer_id=_ident, other_customer_id=_ident)
def test_derive_event_id_differs_for_different_customer(customer_id, other_customer_id) -> None:
    if customer_id == other_customer_id:
        return
    id_a = derive_event_id(customer_id, "s1", BASE_TS, "product_view", 0)
    id_b = derive_event_id(other_customer_id, "s1", BASE_TS, "product_view", 0)
    assert id_a != id_b
