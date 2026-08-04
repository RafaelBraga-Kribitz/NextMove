"""The three DATA-03 semantic gates: non-negative price, monotonic session timestamps, and
catalog referential integrity -- each evaluated **per batch**, never over a whole-history
frame (ENG-08, review HIGH-11).

**Where `PipelineStage` and `RejectRecord` live (executor interpretation).** `pipeline.py`
(Task 1) is this plan's stated owner of `PipelineStage`/`RejectRecord`/`IngestResult`, and
`pipeline.py` needs `run_semantic_gates`, `build_catalog_index`, `CatalogIndex` and
`SessionMonotonicityTracker` from this module -- so `pipeline.py` imports from `semantic.py`.
`GateResult.rejects` is a `list[RejectRecord]`, so this module also needs the `RejectRecord`
shape. Two modules each needing a symbol from the other is a circular import, and Python's
import system cannot resolve that safely regardless of which module a caller imports first
(a test importing `nextmove.ingest.semantic` directly, before anything has imported
`nextmove.ingest.pipeline`, would hit "cannot import name from partially initialized module").
`PipelineStage` and `RejectRecord` are therefore physically defined here, in the leaf module
with no dependency back on `pipeline.py`, and `pipeline.py` imports and re-exports them --
`from nextmove.ingest.pipeline import RejectRecord, PipelineStage` still works for any
caller, and the import graph stays one-directional (`pipeline -> semantic`, never the
reverse). Recorded here and in the plan's SUMMARY as an executor interpretation of an
underspecified mechanism, the same pattern `nextmove.storage` itself recorded for `row_model=`.

**Why one gate is not expressed as a Pandera schema.** `non_negative_price` and
`catalog_referential_integrity` are naturally vectorizable: build one melted frame per batch
(one row per monetary field, or per sku reference) and run a Pandera `Column` check with
`lazy=True`, which collects every violation in the batch in one pass and reports each one's
row index. `monotonic_session_timestamps` is different in kind -- RESEARCH's own planner
notes call it "the only genuinely cross-row one" -- because its verdict depends on
`SessionMonotonicityTracker`'s carried state from the *previous* batch, and Pandera's
`validate` call is stateless per invocation. Forcing that carry through a Pandera `Check`
closure would work mechanically but would hide the actual state-mutating logic inside a
validation callback where it is harder to read and test. This gate is therefore implemented
directly against the batch's session/timestamp values, and its verdict is still routed
through one shared Pandera schema (`_VIOLATION_SCHEMA`, `lazy=True`) purely so every gate's
final pass/fail determination goes through the same one Pandera call, matching RESEARCH's
recommendation for the rest of this module.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import pandas as pd
import pandera.pandas as pa
from pandera import Check
from pydantic import BaseModel, ConfigDict, Field

from nextmove.ingest.contracts import CONTRACT_VERSION, Event, EventType

if TYPE_CHECKING:
    from nextmove.config.models import Config

# Fixed, hardcoded namespace for reject-id derivation (uuid.uuid5), distinct from
# `contracts.EVENT_ID_NAMESPACE` because reject ids and event ids are different id spaces.
# Never regenerate this value -- every reject id derived from it changes if it does.
REJECT_ID_NAMESPACE = uuid.UUID("b8f6a6a0-2e9f-4a7a-9b2d-6b7c0f9a3e11")


class PipelineStage(StrEnum):
    """Which stage of the ingest pipeline produced a `RejectRecord`."""

    CONTRACT = "contract"
    SEMANTIC = "semantic"
    LINEAGE = "lineage"


class RejectRecord(BaseModel):
    """One quarantined row: the offending record verbatim, the reason, the contract version
    and the stage that rejected it (D-20)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reject_id: str = Field(min_length=1)
    raw_record: str
    reason: str = Field(min_length=1)
    field_path: str | None = None
    contract_version: str
    stage: PipelineStage
    source: str = Field(min_length=1)


def canonical_json(obj: Any) -> str:
    """Sorted-key, separator-tight JSON -- the same canonicalization
    `nextmove.config.loader.config_hash` uses -- so a raw record's serialized form is
    reproducible across runs and round-trips byte-identically for JSON-native inputs.
    `default=str` covers a `datetime` slipping through from a real Parquet-sourced record;
    hand-built test records use plain JSON-native types and never hit that branch."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def derive_reject_id(raw_record_json: str, reason: str, stage: PipelineStage) -> str:
    """Derive a deterministic reject id from a reject's own identifying tuple, using the same
    `uuid5` approach `nextmove.ingest.contracts.derive_event_id` uses -- never a random
    generator, so two runs over identical input produce identical reject ids."""
    canonical = "|".join([raw_record_json, reason, str(stage.value)])
    return str(uuid.uuid5(REJECT_ID_NAMESPACE, canonical))


class GateResult(BaseModel):
    """One gate's verdict for one batch: whether it passed, how many rows it violated, and
    the resulting reject rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_name: str
    passed: bool
    violation_count: int = Field(ge=0)
    rejects: list[RejectRecord]


class CatalogIndex(BaseModel):
    """The sku membership set the referential-integrity gate tests against. Built once, from
    a sorted catalog column, before the batch loop -- its size is bounded by `n_skus`, a
    configuration value, never by the event history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skus: frozenset[str]


def build_catalog_index(catalog_rows: Any) -> CatalogIndex:
    """Build a `CatalogIndex` from a `catalog` table's rows -- accepts a `pyarrow.Table`
    (via its `column`/`to_pylist` surface, duck-typed so this module never imports pyarrow
    directly) or any iterable of mappings carrying a `sku` field."""
    if hasattr(catalog_rows, "column"):
        sku_values: Iterable[Any] = catalog_rows.column("sku").to_pylist()
    else:
        sku_values = [row["sku"] for row in catalog_rows]
    return CatalogIndex(skus=frozenset(sorted(str(v) for v in sku_values)))


class SessionMonotonicityTracker:
    """The one bounded cross-batch carry the monotonicity gate needs: a `session_id ->
    last_ts` mapping, evicted below a per-batch watermark. Retained entries track sessions
    *active within `session_max_span_seconds`* rather than every session ever seen -- at
    default scale (one-day span) that is on the order of a few thousand entries, a few
    hundred kilobytes, not a number that grows with the horizon.
    """

    def __init__(self, session_max_span_seconds: int) -> None:
        if session_max_span_seconds <= 0:
            raise ValueError("session_max_span_seconds must be greater than zero")
        self.session_max_span_seconds = session_max_span_seconds
        self._last_ts: dict[str, datetime] = {}
        self._watermark: datetime | None = None

    def __len__(self) -> int:
        return len(self._last_ts)

    def observe(self, session_id: str, ts: datetime) -> tuple[bool, str | None]:
        """Check `ts` against `session_id`'s carried last timestamp from a previous batch,
        without mutating state. A session with no carried entry passes trivially *unless*
        `ts` precedes the current eviction watermark -- that combination means either the
        input is not time-ordered or the session's entry was evicted and it has now
        reappeared, and both are real data-quality problems worth quarantining rather than
        silently passing."""
        prev = self._last_ts.get(session_id)
        if prev is None:
            if self._watermark is not None and ts < self._watermark:
                gap = self._watermark - ts
                return False, (
                    f"session {session_id!r} reappeared at ts={ts.isoformat()}, which is "
                    f"before the current eviction watermark {self._watermark.isoformat()} "
                    f"(gap={gap}, configured span={self.session_max_span_seconds}s) -- "
                    "either the input is not time-ordered or the session exceeds the "
                    "configured span"
                )
            return True, None
        if ts > prev:
            return True, None
        return False, (
            f"session {session_id!r} timestamp {ts.isoformat()} does not strictly advance "
            f"past its carried previous timestamp {prev.isoformat()}"
        )

    def update(self, session_id: str, ts: datetime) -> None:
        """Record `ts` as `session_id`'s last-seen timestamp, keeping the maximum across
        repeated calls within one batch."""
        prev = self._last_ts.get(session_id)
        self._last_ts[session_id] = ts if prev is None else max(prev, ts)

    def evict_before(self, watermark_ts: datetime) -> None:
        """Drop every entry whose last timestamp precedes `watermark_ts`, and advance the
        tracker's own watermark monotonically (never backwards, even if called with an
        earlier value than a prior call)."""
        self._watermark = (
            watermark_ts if self._watermark is None else max(self._watermark, watermark_ts)
        )
        stale = [sid for sid, ts in self._last_ts.items() if ts < watermark_ts]
        for sid in stale:
            del self._last_ts[sid]


# ------------------------------------------------------------------------------------------
# Shared "route the verdict through one Pandera schema, lazily" helper
# ------------------------------------------------------------------------------------------

_VIOLATION_SCHEMA = pa.DataFrameSchema({"_violation": pa.Column(bool, checks=Check.eq(False))})


def _validate_no_violations(violation_flags: list[bool]) -> None:
    """Run `violation_flags` (one bool per row, True = violates) through the shared
    zero-violation Pandera schema with `lazy=True`, so every gate's pass/fail determination
    is made by one lazily-validated Pandera call rather than a bare Python `if`. A no-op for
    an empty batch."""
    if not violation_flags:
        return
    frame = pd.DataFrame({"_violation": violation_flags})
    try:
        _VIOLATION_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors:
        pass


def _build_reject(event: Event, gate_name: str, detail: str) -> RejectRecord:
    raw_json = canonical_json(event.model_dump(mode="json"))
    reason = f"semantic gate {gate_name!r} failed: {detail}"
    return RejectRecord(
        reject_id=derive_reject_id(raw_json, reason, PipelineStage.SEMANTIC),
        raw_record=raw_json,
        reason=reason,
        field_path=None,
        contract_version=CONTRACT_VERSION,
        stage=PipelineStage.SEMANTIC,
        source=event.source,
    )


# ------------------------------------------------------------------------------------------
# Gate 1: non_negative_price
# ------------------------------------------------------------------------------------------

#: Which payload fields, per event type, carry a monetary (integer cents) value.
_PRICE_FIELDS: dict[EventType, tuple[str, ...]] = {
    EventType.PRODUCT_VIEW: ("unit_price_cents",),
    EventType.ADD_TO_CART: ("unit_price_cents",),
    EventType.CART_ABANDON: ("cart_value_cents",),
    EventType.ORDER_PLACED: ("order_total_cents",),
}


def _price_rows(events_batch: list[Event]) -> list[tuple[int, str, int]]:
    rows: list[tuple[int, str, int]] = []
    for idx, event in enumerate(events_batch):
        for field in _PRICE_FIELDS.get(event.type, ()):
            rows.append((idx, field, getattr(event.payload, field)))
        if event.type is EventType.ORDER_PLACED:
            for i, item in enumerate(event.payload.line_items):
                rows.append((idx, f"line_items[{i}].unit_price_cents", item.unit_price_cents))
                rows.append((idx, f"line_items[{i}].discount_cents", item.discount_cents))
    return rows


def non_negative_price(
    events_batch: list[Event],
    catalog_index: CatalogIndex,
    tracker: SessionMonotonicityTracker,
) -> GateResult:
    """Every monetary field across every payload type must be >= 0. Zero is legal (a free
    gift line, a fully-discounted item); minus one cent is not."""
    rows = _price_rows(events_batch)
    if not rows:
        return GateResult(
            gate_name="non_negative_price", passed=True, violation_count=0, rejects=[]
        )

    frame = pd.DataFrame(rows, columns=["idx", "field_path", "value"])
    schema = pa.DataFrameSchema({"value": pa.Column(int, checks=Check.ge(0))})

    violations: dict[int, list[str]] = {}
    try:
        schema.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for _, failure in exc.failure_cases.iterrows():
            row_index = int(failure["index"])
            idx = int(frame.loc[row_index, "idx"])
            field_path = frame.loc[row_index, "field_path"]
            value = frame.loc[row_index, "value"]
            violations.setdefault(idx, []).append(f"{field_path}={value}")

    _validate_no_violations([idx in violations for idx in range(len(events_batch))])

    if not violations:
        return GateResult(
            gate_name="non_negative_price", passed=True, violation_count=0, rejects=[]
        )
    rejects = [
        _build_reject(events_batch[idx], "non_negative_price", "; ".join(details))
        for idx, details in sorted(violations.items())
    ]
    return GateResult(
        gate_name="non_negative_price",
        passed=False,
        violation_count=len(rejects),
        rejects=rejects,
    )


# ------------------------------------------------------------------------------------------
# Gate 2: catalog_referential_integrity
# ------------------------------------------------------------------------------------------

_SKU_PAYLOAD_TYPES: tuple[EventType, ...] = (
    EventType.PRODUCT_VIEW,
    EventType.ADD_TO_CART,
    EventType.CART_REMOVE,
    EventType.DWELL,
)


def _sku_rows(events_batch: list[Event]) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for idx, event in enumerate(events_batch):
        if event.type in _SKU_PAYLOAD_TYPES:
            rows.append((idx, "sku", event.payload.sku))
        elif event.type is EventType.ORDER_PLACED:
            for i, item in enumerate(event.payload.line_items):
                rows.append((idx, f"line_items[{i}].sku", item.sku))
    return rows


def catalog_referential_integrity(
    events_batch: list[Event],
    catalog_index: CatalogIndex,
    tracker: SessionMonotonicityTracker,
) -> GateResult:
    """Every sku referenced by any payload in the batch must be present in `catalog_index`.
    A batch with no sku-bearing events passes trivially, regardless of catalog contents."""
    rows = _sku_rows(events_batch)
    if not rows:
        return GateResult(
            gate_name="catalog_referential_integrity", passed=True, violation_count=0, rejects=[]
        )

    frame = pd.DataFrame(rows, columns=["idx", "field_path", "sku"])
    schema = pa.DataFrameSchema({"sku": pa.Column(str, checks=Check.isin(catalog_index.skus))})

    violations: dict[int, list[str]] = {}
    try:
        schema.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for _, failure in exc.failure_cases.iterrows():
            row_index = int(failure["index"])
            idx = int(frame.loc[row_index, "idx"])
            field_path = frame.loc[row_index, "field_path"]
            sku = frame.loc[row_index, "sku"]
            violations.setdefault(idx, []).append(f"{field_path}={sku!r} not present in catalog")

    _validate_no_violations([idx in violations for idx in range(len(events_batch))])

    if not violations:
        return GateResult(
            gate_name="catalog_referential_integrity", passed=True, violation_count=0, rejects=[]
        )
    rejects = [
        _build_reject(events_batch[idx], "catalog_referential_integrity", "; ".join(details))
        for idx, details in sorted(violations.items())
    ]
    return GateResult(
        gate_name="catalog_referential_integrity",
        passed=False,
        violation_count=len(rejects),
        rejects=rejects,
    )


# ------------------------------------------------------------------------------------------
# Gate 3: monotonic_session_timestamps (the one genuinely cross-row / cross-batch gate)
# ------------------------------------------------------------------------------------------


def monotonic_session_timestamps(
    events_batch: list[Event],
    catalog_index: CatalogIndex,
    tracker: SessionMonotonicityTracker,
) -> GateResult:
    """Within the batch, timestamps must strictly increase within each session; a session
    continuing from an earlier batch is compared against `tracker`'s carried last timestamp
    rather than treated as new. Two events sharing a session and a timestamp are a
    violation, not a tie -- within one session the ordering is causal. A single-event
    session trivially passes."""
    if not events_batch:
        return GateResult(
            gate_name="monotonic_session_timestamps", passed=True, violation_count=0, rejects=[]
        )

    frame = pd.DataFrame(
        {
            "idx": range(len(events_batch)),
            "session_id": [e.session_id for e in events_batch],
            "ts": pd.to_datetime([e.ts for e in events_batch], utc=True),
        }
    )
    sorted_frame = frame.sort_values(["session_id", "ts"], kind="stable")

    violations: dict[int, str] = {}

    # Cross-batch continuity: each session's first-in-batch row is compared against the
    # tracker's carried last timestamp from a previous batch.
    first_rows = sorted_frame.groupby("session_id", sort=False, as_index=False).first()
    for _, row in first_rows.iterrows():
        passed, reason = tracker.observe(row["session_id"], row["ts"].to_pydatetime())
        if not passed:
            violations[int(row["idx"])] = reason or "monotonicity violation"

    # Within-batch: strictly increasing per session.
    for _session_id, group in sorted_frame.groupby("session_id", sort=False):
        prev_ts = None
        for _, row in group.iterrows():
            ts = row["ts"]
            if prev_ts is not None and ts <= prev_ts:
                idx = int(row["idx"])
                violations.setdefault(
                    idx,
                    f"session {row['session_id']!r} timestamp does not strictly increase "
                    f"within the batch (previous={prev_ts}, this={ts})",
                )
            prev_ts = ts

    # Carry each session's last-in-batch timestamp forward for the next batch, then evict
    # below this batch's watermark (its minimum timestamp minus the configured span).
    last_rows = sorted_frame.groupby("session_id", sort=False, as_index=False).last()
    for _, row in last_rows.iterrows():
        tracker.update(row["session_id"], row["ts"].to_pydatetime())
    watermark = frame["ts"].min().to_pydatetime() - timedelta(
        seconds=tracker.session_max_span_seconds
    )
    tracker.evict_before(watermark)

    _validate_no_violations([idx in violations for idx in range(len(events_batch))])

    if not violations:
        return GateResult(
            gate_name="monotonic_session_timestamps", passed=True, violation_count=0, rejects=[]
        )
    rejects = [
        _build_reject(events_batch[idx], "monotonic_session_timestamps", reason)
        for idx, reason in sorted(violations.items())
    ]
    return GateResult(
        gate_name="monotonic_session_timestamps",
        passed=False,
        violation_count=len(rejects),
        rejects=rejects,
    )


SEMANTIC_GATES: dict[
    str, Callable[[list[Event], CatalogIndex, SessionMonotonicityTracker], GateResult]
] = {
    "non_negative_price": non_negative_price,
    "monotonic_session_timestamps": monotonic_session_timestamps,
    "catalog_referential_integrity": catalog_referential_integrity,
}


def run_semantic_gates(
    events_batch: list[Event],
    catalog_index: CatalogIndex,
    tracker: SessionMonotonicityTracker,
    config: Config,
) -> list[GateResult]:
    """Run exactly the gates named in `config.data_quality.semantic_gates`, in that declared
    order -- never dict iteration order. Raises `KeyError` naming any configured gate with no
    implementation."""
    results: list[GateResult] = []
    for name in config.data_quality.semantic_gates:
        gate_fn = SEMANTIC_GATES.get(name)
        if gate_fn is None:
            raise KeyError(
                f"configured semantic gate {name!r} has no implementation; available gates: "
                f"{sorted(SEMANTIC_GATES)}"
            )
        results.append(gate_fn(events_batch, catalog_index, tracker))
    return results
