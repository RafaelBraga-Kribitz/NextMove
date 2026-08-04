"""Tests for the inward-only IngestAdapter registry (DATA-01, D-13)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nextmove.ingest.adapters import IngestAdapter, SimulatorAdapter, get_adapter, register_adapter

BASE_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _canonical_record(**overrides) -> dict:
    data = {
        "event_id": "e1",
        "customer_id": "c1",
        "session_id": "s1",
        "ts": BASE_TS,
        "type": "product_view",
        "payload": {
            "type": "product_view",
            "sku": "sku-1",
            "category": "shoes",
            "unit_price_cents": 1999,
        },
    }
    data.update(overrides)
    return data


def test_ingest_adapter_declares_single_conversion_direction() -> None:
    attrs = {a for a in IngestAdapter.__protocol_attrs__ if not a.startswith("_")}
    assert "to_canonical" in attrs
    assert "name" in attrs
    assert not any("from_canonical" in a or "to_external" in a for a in attrs)


def test_registering_duplicate_name_raises() -> None:
    class DuplicateSimulatorAdapter:
        name = "simulator"

        def to_canonical(self, records):
            return []

    with pytest.raises(ValueError):
        register_adapter(DuplicateSimulatorAdapter)


def test_get_adapter_unregistered_name_raises_and_lists_registered() -> None:
    with pytest.raises(KeyError) as exc_info:
        get_adapter("does-not-exist")
    message = str(exc_info.value)
    assert "does-not-exist" in message
    assert "simulator" in message


def test_get_adapter_returns_simulator_adapter() -> None:
    assert get_adapter("simulator").name == "simulator"


def test_simulator_adapter_validates_already_canonical_dicts() -> None:
    adapter = SimulatorAdapter()
    events = adapter.to_canonical([_canonical_record()])
    assert len(events) == 1
    assert events[0].source == "simulator"


def test_simulator_adapter_empty_input_returns_empty_list() -> None:
    adapter = SimulatorAdapter()
    assert adapter.to_canonical([]) == []


def test_simulator_adapter_missing_required_field_raises() -> None:
    adapter = SimulatorAdapter()
    bad_record = _canonical_record()
    del bad_record["session_id"]
    with pytest.raises(ValidationError):
        adapter.to_canonical([bad_record])


def test_simulator_adapter_output_is_canonically_sorted() -> None:
    adapter = SimulatorAdapter()
    later = _canonical_record(event_id="e2", ts=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC))
    earlier = _canonical_record(event_id="e1", ts=BASE_TS)
    events = adapter.to_canonical([later, earlier])
    assert [e.event_id for e in events] == ["e1", "e2"]
