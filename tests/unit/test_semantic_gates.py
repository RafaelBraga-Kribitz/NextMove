"""The three DATA-03 semantic gates, evaluated per batch (review HIGH-11)."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta

import pytest

from nextmove.config.loader import load_config
from nextmove.ingest.contracts import Event, EventType, ProductViewPayload
from nextmove.ingest.semantic import (
    CatalogIndex,
    SessionMonotonicityTracker,
    catalog_referential_integrity,
    monotonic_session_timestamps,
    non_negative_price,
    run_semantic_gates,
)

BASE_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _event(
    event_id: str,
    session_id: str = "s1",
    customer_id: str = "c1",
    ts: datetime = BASE_TS,
    sku: str = "sku-1",
    price: int = 1000,
) -> Event:
    return Event.model_validate(
        {
            "event_id": event_id,
            "customer_id": customer_id,
            "session_id": session_id,
            "ts": ts,
            "type": "product_view",
            "payload": {
                "type": "product_view",
                "sku": sku,
                "category": "shoes",
                "unit_price_cents": price,
            },
            "source": "simulator",
        }
    )


def _event_with_price(
    event_id: str, price: int, session_id: str = "s1", ts: datetime = BASE_TS
) -> Event:
    """Bypasses `ProductViewPayload.unit_price_cents`'s `ge=0` contract validator via
    `model_construct` -- the gate itself is tested in isolation here, independent of the fact
    that a negative price can never actually survive contract validation and reach a gate in
    the real pipeline (that boundary is why the semantic-only reject-threshold test in
    `test_reject_threshold.py` uses referential integrity instead)."""
    payload = ProductViewPayload.model_construct(
        type="product_view", sku="sku-1", category="shoes", unit_price_cents=price
    )
    return Event.model_construct(
        event_id=event_id,
        customer_id="c1",
        session_id=session_id,
        ts=ts,
        type=EventType.PRODUCT_VIEW,
        payload=payload,
        source="simulator",
    )


def _catalog(skus: tuple[str, ...] = ("sku-1",)) -> CatalogIndex:
    return CatalogIndex(skus=frozenset(skus))


def _tracker(span: int = 86400) -> SessionMonotonicityTracker:
    return SessionMonotonicityTracker(session_max_span_seconds=span)


def _event_ids(rejects) -> set[str]:
    return {json.loads(r.raw_record)["event_id"] for r in rejects}


# ---------------------------------------------------------------------------------------
# non_negative_price
# ---------------------------------------------------------------------------------------


def test_price_zero_passes():
    result = non_negative_price([_event_with_price("e0", 0)], _catalog(), _tracker())
    assert result.passed is True
    assert result.violation_count == 0


def test_price_minus_one_fails():
    result = non_negative_price([_event_with_price("e1", -1)], _catalog(), _tracker())
    assert result.passed is False
    assert result.violation_count == 1
    assert _event_ids(result.rejects) == {"e1"}
    assert "non_negative_price" in result.rejects[0].reason


def test_price_gate_collects_all_violations_not_just_first():
    events = [
        _event_with_price("e0", -1, session_id="s1"),
        _event_with_price("e1", -2, session_id="s2"),
    ]
    result = non_negative_price(events, _catalog(), _tracker())
    assert result.violation_count == 2
    assert _event_ids(result.rejects) == {"e0", "e1"}


# ---------------------------------------------------------------------------------------
# monotonic_session_timestamps
# ---------------------------------------------------------------------------------------


def test_monotonicity_single_event_session_passes():
    result = monotonic_session_timestamps([_event("e0")], _catalog(), _tracker())
    assert result.passed is True
    assert result.violation_count == 0


def test_monotonicity_rejects_when_two_events_share_a_timestamp_within_a_session():
    # Within-batch monotonicity is checked *after* sorting the batch by (session_id, ts), so
    # a batch presented out of chronological order is not itself a violation -- sorting
    # re-establishes order for any set of *distinct* timestamps. Only an exact tie survives
    # the sort as adjacent-and-equal, which is what this gate actually detects within one
    # batch; genuine temporal disorder *across* batches is the tracker's job (see
    # `test_session_split_across_two_batches_is_still_caught`).
    events = [
        _event("e0", ts=BASE_TS),
        _event("e1", ts=BASE_TS + timedelta(seconds=5)),
        _event("e2", ts=BASE_TS + timedelta(seconds=5)),  # ties with e1
    ]
    result = monotonic_session_timestamps(events, _catalog(), _tracker())
    assert result.passed is False
    assert result.violation_count == 1


def test_monotonicity_equal_timestamps_in_one_session_is_a_violation():
    events = [_event("e0", ts=BASE_TS), _event("e1", ts=BASE_TS)]
    result = monotonic_session_timestamps(events, _catalog(), _tracker())
    assert result.passed is False


def test_monotonicity_two_distinct_sessions_each_single_event_passes():
    events = [
        _event("e0", session_id="s1", ts=BASE_TS),
        _event("e1", session_id="s2", ts=BASE_TS),
    ]
    result = monotonic_session_timestamps(events, _catalog(), _tracker())
    assert result.passed is True


def test_session_split_across_two_batches_is_still_caught():
    tracker = _tracker()
    catalog = _catalog()
    batch1 = [_event("e0", session_id="s1", ts=BASE_TS + timedelta(seconds=10))]
    batch2 = [_event("e1", session_id="s1", ts=BASE_TS)]  # precedes e0's carried timestamp

    result1 = monotonic_session_timestamps(batch1, catalog, tracker)
    result2 = monotonic_session_timestamps(batch2, catalog, tracker)

    assert result1.passed is True
    assert result2.passed is False
    assert "s1" in result2.rejects[0].reason


def test_batch_equivalence_one_batch_of_n_vs_n_batches_of_one():
    # Events are fed in ascending timestamp order (the realistic shape for both a single
    # batch and a stream of one-row batches) with one exact tie, which is the only violation
    # mode a within-batch sort cannot erase -- see the note on
    # `test_monotonicity_rejects_when_two_events_share_a_timestamp_within_a_session`.
    events = [
        _event("e0", ts=BASE_TS),
        _event("e1", ts=BASE_TS + timedelta(seconds=5)),
        _event("e2", ts=BASE_TS + timedelta(seconds=5)),  # ties with e1
    ]
    catalog = _catalog()

    one_batch_result = monotonic_session_timestamps(list(events), catalog, _tracker())
    one_batch_rejects = _event_ids(one_batch_result.rejects)

    tracker_many = _tracker()
    many_batches_rejects: set[str] = set()
    for event in events:
        result = monotonic_session_timestamps([event], catalog, tracker_many)
        many_batches_rejects |= _event_ids(result.rejects)

    assert one_batch_rejects == many_batches_rejects


def test_tracker_entry_count_stays_flat_as_sessions_accumulate():
    tracker = _tracker(span=60)
    catalog = _catalog()
    max_len = 0
    for i in range(30):
        ts = BASE_TS + timedelta(seconds=i * 120)
        batch = [_event(f"e{i}", session_id=f"session-{i}", ts=ts)]
        monotonic_session_timestamps(batch, catalog, tracker)
        max_len = max(max_len, len(tracker))
    assert max_len <= 3, f"tracker grew to {max_len} entries -- it should stay bounded"


def test_session_reappearing_after_eviction_is_a_violation_not_a_silent_pass():
    tracker = _tracker(span=60)
    catalog = _catalog()

    monotonic_session_timestamps([_event("e0", session_id="s1", ts=BASE_TS)], catalog, tracker)
    # Advance far enough that s1's carried entry is evicted.
    monotonic_session_timestamps(
        [_event("e1", session_id="s2", ts=BASE_TS + timedelta(seconds=1000))], catalog, tracker
    )
    assert len(tracker) == 1  # only s2 remains; s1 was evicted

    # s1 "reappears" with a timestamp that is itself behind the current watermark -- the only
    # mechanically detectable signal that distinguishes a late/reappearing session from a
    # genuinely new one without retaining the evicted session's state (which would defeat the
    # tracker's whole memory bound).
    result = monotonic_session_timestamps(
        [_event("e2", session_id="s1", ts=BASE_TS + timedelta(seconds=500))], catalog, tracker
    )
    assert result.passed is False
    assert "s1" in result.rejects[0].reason


# ---------------------------------------------------------------------------------------
# catalog_referential_integrity
# ---------------------------------------------------------------------------------------


def test_referential_integrity_unknown_sku_names_it_in_reason():
    result = catalog_referential_integrity(
        [_event("e0", sku="sku-unknown")], _catalog(skus=("sku-1",)), _tracker()
    )
    assert result.passed is False
    assert "sku-unknown" in result.rejects[0].reason


def test_referential_integrity_empty_catalog_and_empty_batch_passes():
    result = catalog_referential_integrity([], _catalog(skus=()), _tracker())
    assert result.passed is True
    assert result.violation_count == 0


def test_referential_integrity_collects_all_violations():
    events = [
        _event("e0", sku="sku-unknown-1", session_id="s1"),
        _event("e1", sku="sku-unknown-2", session_id="s2"),
    ]
    result = catalog_referential_integrity(events, _catalog(skus=("sku-1",)), _tracker())
    assert result.violation_count == 2
    assert _event_ids(result.rejects) == {"e0", "e1"}


# ---------------------------------------------------------------------------------------
# run_semantic_gates
# ---------------------------------------------------------------------------------------


def _config_with_gates(gate_names: list[str]):
    resolved = load_config("tiny")
    new_dq = resolved.config.data_quality.model_copy(update={"semantic_gates": gate_names})
    return resolved.config.model_copy(update={"data_quality": new_dq})


def test_run_semantic_gates_returns_results_in_config_declared_order():
    config = _config_with_gates(
        ["catalog_referential_integrity", "non_negative_price", "monotonic_session_timestamps"]
    )
    results = run_semantic_gates([_event("e0")], _catalog(), _tracker(), config)
    assert [r.gate_name for r in results] == [
        "catalog_referential_integrity",
        "non_negative_price",
        "monotonic_session_timestamps",
    ]


def test_gate_not_listed_in_config_does_not_run():
    config = _config_with_gates(["non_negative_price"])
    events = [_event("e0", sku="sku-unknown")]
    results = run_semantic_gates(events, _catalog(skus=("sku-1",)), _tracker(), config)
    assert [r.gate_name for r in results] == ["non_negative_price"]


def test_configured_gate_with_no_implementation_raises_keyerror_naming_it():
    config = _config_with_gates(["not_a_real_gate"])
    with pytest.raises(KeyError, match="not_a_real_gate"):
        run_semantic_gates([], _catalog(), _tracker(), config)


def test_semantic_gates_contains_exactly_the_three_configured_names():
    from nextmove.ingest.semantic import SEMANTIC_GATES

    assert set(SEMANTIC_GATES) == {
        "non_negative_price",
        "monotonic_session_timestamps",
        "catalog_referential_integrity",
    }


def test_run_semantic_gates_signature_has_no_whole_history_dataframe_param():
    params = inspect.signature(run_semantic_gates).parameters
    assert not any(name.endswith("_df") for name in params)


def test_data_quality_config_carries_session_max_span_seconds():
    resolved = load_config("tiny")
    assert resolved.config.data_quality.session_max_span_seconds == 86400
