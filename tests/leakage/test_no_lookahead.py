"""FEAT-02 leakage proof over the materialized grid (phase success criterion 3).

Three complementary checks, per the plan's risk note that a leakage test must actually be able
to fail:

1. **General mutation proof, over the whole `tiny`-profile grid.** Two runs of the identical
   pipeline differ only in that the second has a handful of synthetic events appended to the
   canonical `events` table, timestamped ten years after the grid's last snapshot. If any
   feature value in the materialized grid changed between the two runs, some transform read an
   event that postdates every `as_of_ts` it was computing for -- which is impossible if the
   point-in-time boundary holds, and would be silently possible if `_build_asof_sql` or a
   transform's own `<=` predicate regressed. This is the check that would actually fail on a
   real leakage bug, unlike a bare "no event's ts exceeds as_of_ts" assertion over the whole
   table (which is true of every non-leaking row *and* of a customer's ordinary future history,
   and therefore proves nothing about whether a value was computed from it).
2. **The explicit boundary pair.** A customer with one event at exactly `as_of_ts` and one at
   `as_of_ts` plus one microsecond: the first is reflected in the computed values, the second is
   not.
3. **The empty case.** A customer with zero events at `as_of_ts` gets every column set to its
   transform's declared `empty_default`.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from nextmove.config.loader import load_config
from nextmove.features.compute import compute_as_of, materialize_grid
from nextmove.features.definitions import FEATURE_TRANSFORMS
from nextmove.ingest.__main__ import _raw_record_stream
from nextmove.ingest.contracts import (
    CANONICAL_SORT_KEY,
    Event,
    OrderLineItem,
    OrderPlacedPayload,
)
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, ingest_events
from nextmove.simulator.run import run_simulation
from nextmove.storage import (
    Stage,
    Zone,
    resolve_table_path,
    write_part_file,
    write_table_from_parts,
)


class _CanonicalEventRow(BaseModel):
    """Minimal flattened row shape matching `nextmove.ingest.pipeline._CanonicalEventRow`
    field-for-field -- duplicated here rather than imported, since that class is private to the
    ingest package and this leakage suite is deliberately not coupled to ingest internals beyond
    the public canonical `events` table shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    ts: datetime
    type: str = Field(min_length=1)
    payload: str
    source: str = Field(min_length=1)


def _event_row(event: Event) -> _CanonicalEventRow:
    return _CanonicalEventRow(
        event_id=event.event_id,
        customer_id=event.customer_id,
        session_id=event.session_id,
        ts=event.ts,
        type=event.type.value,
        payload=event.payload.model_dump_json(),
        source=event.source,
    )


def _order_placed_event(customer_id: str, ts: datetime, order_id: str) -> Event:
    payload = OrderPlacedPayload(
        type="order_placed",
        order_id=order_id,
        line_items=[
            OrderLineItem(sku="sku-leak-test", quantity=1, unit_price_cents=1000, discount_cents=0)
        ],
        order_total_cents=1000,
    )
    return Event(
        event_id=f"leak-{order_id}",
        customer_id=customer_id,
        session_id=f"leak-session-{order_id}",
        ts=ts,
        type="order_placed",
        payload=payload,
        source="simulator",
    )


def _append_future_events(root: Path, events: list[Event]) -> None:
    """Merge `events` into `root`'s canonical `events` table, matching `ingest_events`'s own
    merge shape (existing table + new part, deduped and re-sorted by `write_table_from_parts`)."""
    resolved = load_config("tiny")
    new_part = write_part_file(
        [_event_row(e) for e in events],
        part_dir="leak_test_events",
        part_index=0,
        sort_key=CANONICAL_SORT_KEY,
        root=root,
        row_model=_CanonicalEventRow,
    )
    existing_path = resolve_table_path("events", Zone.CANONICAL, root=root)
    write_table_from_parts(
        [existing_path, new_part],
        table_name="events",
        zone=Zone.CANONICAL,
        sort_key=CANONICAL_SORT_KEY,
        resolved_config=resolved,
        producer_stage=Stage.INGEST,
        dedupe_on="event_id",
        root=root,
    )


@pytest.fixture(scope="module")
def tiny_pipeline_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("leakage_tiny_baseline")
    resolved = load_config("tiny")
    run_simulation(resolved, out_root=root)
    ingest_events(_raw_record_stream(root, VALIDATION_BATCH_SIZE), resolved, out_root=root)
    return root


class TestWholeGridMutationProof:
    def test_future_events_do_not_change_any_materialized_feature_value(
        self, tiny_pipeline_root: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        resolved = load_config("tiny")

        baseline_root = tiny_pipeline_root
        baseline_grid_path = materialize_grid(resolved, out_root=baseline_root)

        mutated_root = tmp_path_factory.mktemp("leakage_tiny_mutated")
        shutil.copytree(baseline_root, mutated_root, dirs_exist_ok=True)
        # Remove any feature_grid the baseline run may have left in the copy so the mutated run
        # starts from a clean features/ directory, exactly like the baseline did.
        mutated_feature_grid = mutated_root / "features" / "feature_grid.parquet"
        if mutated_feature_grid.exists():
            mutated_feature_grid.unlink()

        far_future = datetime(2099, 1, 1, tzinfo=UTC)
        future_events = [
            _order_placed_event("0", far_future, "leak-order-a"),
            _order_placed_event("1", far_future + timedelta(days=1), "leak-order-b"),
        ]
        _append_future_events(mutated_root, future_events)

        mutated_grid_path = materialize_grid(resolved, out_root=mutated_root)

        import hashlib

        baseline_digest = hashlib.sha256(baseline_grid_path.read_bytes()).hexdigest()
        mutated_digest = hashlib.sha256(mutated_grid_path.read_bytes()).hexdigest()

        if baseline_digest == mutated_digest:
            return

        import pyarrow.parquet as pq

        baseline_rows = pq.ParquetFile(baseline_grid_path).read().to_pylist()
        mutated_rows = pq.ParquetFile(mutated_grid_path).read().to_pylist()
        violations = [(b, m) for b, m in zip(baseline_rows, mutated_rows, strict=True) if b != m]
        pytest.fail(
            f"{len(violations)} snapshot(s) changed after appending events dated {far_future} "
            f"-- a decade after every as_of_ts in this grid -- which is only possible if a "
            f"transform read an event postdating its as_of_ts. First violating pair: "
            f"{violations[0] if violations else None}"
        )


class TestExplicitBoundaryPair:
    def test_event_at_exactly_as_of_ts_is_included_and_one_microsecond_later_is_excluded(
        self, tmp_path: Path
    ) -> None:
        resolved = load_config("tiny")
        boundary_ts = datetime(2024, 6, 1, tzinfo=UTC)
        one_us_later = boundary_ts + timedelta(microseconds=1)

        root = tmp_path / "boundary_pair"
        events = [
            _order_placed_event("boundary-customer", boundary_ts, "at-boundary"),
            _order_placed_event("boundary-customer", one_us_later, "after-boundary"),
        ]
        _write_events_from_scratch(root, resolved, events)

        at_boundary = compute_as_of(["boundary-customer"], boundary_ts, resolved, out_root=root)
        row_at_boundary = at_boundary.to_pylist()[0]
        assert row_at_boundary["rfm_frequency_count"] == 1, (
            "the event timestamped exactly at as_of_ts was not counted -- the ASOF boundary "
            "must be inclusive"
        )

        just_before = boundary_ts - timedelta(microseconds=1)
        before_one_us = compute_as_of(["boundary-customer"], just_before, resolved, out_root=root)
        row_before = before_one_us.to_pylist()[0]
        assert row_before["rfm_frequency_count"] == 0, (
            "an as_of_ts one microsecond before the event already counted it -- the boundary is "
            "not exclusive on the other side"
        )

        after_second_event = compute_as_of(
            ["boundary-customer"], one_us_later, resolved, out_root=root
        )
        row_after = after_second_event.to_pylist()[0]
        assert row_after["rfm_frequency_count"] == 2, (
            "an as_of_ts exactly at the second event's ts did not count it"
        )


def _write_events_from_scratch(root: Path, resolved, events: list[Event]) -> None:
    part = write_part_file(
        [_event_row(e) for e in events],
        part_dir="scratch_events",
        part_index=0,
        sort_key=CANONICAL_SORT_KEY,
        root=root,
        row_model=_CanonicalEventRow,
    )
    write_table_from_parts(
        [part],
        table_name="events",
        zone=Zone.CANONICAL,
        sort_key=CANONICAL_SORT_KEY,
        resolved_config=resolved,
        producer_stage=Stage.INGEST,
        dedupe_on="event_id",
        root=root,
    )


class TestEmptyCase:
    def test_customer_with_zero_events_gets_every_declared_empty_default(
        self, tmp_path: Path
    ) -> None:
        resolved = load_config("tiny")
        root = tmp_path / "empty_customer"
        # One event for a *different* customer, so the events table exists and is non-empty,
        # but "empty-customer" itself has zero qualifying events at any as_of_ts.
        _write_events_from_scratch(
            root,
            resolved,
            [_order_placed_event("someone-else", datetime(2024, 1, 1, tzinfo=UTC), "unrelated")],
        )

        result = compute_as_of(
            ["empty-customer"], datetime(2024, 6, 1, tzinfo=UTC), resolved, out_root=root
        )
        row = result.to_pylist()[0]

        for name, transform in FEATURE_TRANSFORMS.items():
            actual = row[transform.output_column]
            expected = transform.empty_default
            assert actual == expected, (
                f"{name} ({transform.output_column}): expected declared empty_default "
                f"{expected!r}, got {actual!r}"
            )
