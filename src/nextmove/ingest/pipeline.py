"""Contract validation, the quarantine split, the DATA-03 semantic gates, and append-only
canonical landing -- all inside one function, `ingest_events` (DATA-02, DATA-03, D-20, D-21).

**Re-ingest semantics (two paths, stated explicitly -- MEDIUM-5).** A direct invocation
(`python -m nextmove.ingest` or `just ingest`) merges any pre-existing canonical `events`/
`rejects` table into the part set and deduplicates on `event_id`/`reject_id`, so a second
ingest of identical input leaves the canonical table byte-identical and appends no duplicate
row -- the append is genuinely idempotent and non-destructive. Under `dvc repro`, plan 01-11
declares `data/canonical/` as the `ingest` stage's `outs` with no `persist` flag, and DVC
removes a stage's non-persistent outs *before* the stage executes -- so the "already exists"
branch below never fires under `dvc repro`, and every pipeline run is a full
rematerialization of `data/canonical/` from `data/raw/`. The two semantics are safe to hold
at once only because they are byte-equal for identical input; plan 01-11 asserts that by
forcing a stage re-execution and comparing the canonical digest.

**Ordering is the whole point of this module (review HIGH-12).** The semantic gates
(`nextmove.ingest.semantic.run_semantic_gates`) run *inside* this function, per batch,
*before* the batch is flushed -- not after `ingest_events` returns. A row that fails a
semantic gate is diverted into the `rejects` part instead of the `events` part and therefore
never reaches the canonical table, and its rejection is counted in the single `IngestResult`
this function builds and returns -- the same result `evaluate_reject_rate` reads. Moving the
gates outside this function (or running them over the whole landed table afterward) would
silently break both properties: semantically invalid rows would sit in `events` *and*
`rejects` at once, and D-21's threshold could never fire on a semantic violation, because the
rate it reads would already be fixed before any gate ran. `gates_passed`/`gates_failed` are
populated by this same function for the identical reason: it is the only function that runs
a gate, so it is the only function that can honestly report the outcome.

**Bounding peak Python heap (ENG-08).** Each batch is validated, gated, and flushed to a
staging part file through `write_part_file`, then released -- mirroring plan 01-08 Task 3's
`_FlushBuffer` mechanism. Nothing accumulates across batches. The union with any pre-existing
canonical table, the `event_id`/`reject_id` deduplication and the global sort are performed
by `nextmove.storage.write_table_from_parts`, out of core through DuckDB, never by a
Python-side union of every batch's events.

**`_CanonicalEventRow` (executor interpretation, mirrors plan 01-08 Task 3's `EventRow`).**
`nextmove.storage`'s generic Pydantic-model-to-Arrow-schema deriver cannot handle
`Event.payload`'s 13-member discriminated union. Plan 01-08 solved this for the simulator's
raw landing with a flat row shape carrying `payload` as a JSON string; this module defines
its own row shape with the identical fields, rather than importing plan 01-08's `EventRow`
from `nextmove.simulator` -- the ingest package must stay adapter-agnostic and must never
depend on the simulator package it may one day ingest from a completely different producer.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nextmove.config.loader import ResolvedConfig
from nextmove.ingest.adapters import get_adapter
from nextmove.ingest.contracts import CANONICAL_SORT_KEY, CONTRACT_VERSION, Event
from nextmove.ingest.semantic import (
    PipelineStage,
    RejectRecord,
    SessionMonotonicityTracker,
    build_catalog_index,
    canonical_json,
    derive_reject_id,
    run_semantic_gates,
)
from nextmove.storage import (
    Stage,
    Zone,
    clear_staging,
    list_part_files,
    read_lineage,
    read_table,
    resolve_table_path,
    table_exists,
    write_part_file,
    write_table,
    write_table_from_parts,
)

__all__ = [
    "VALIDATION_BATCH_SIZE",
    "IngestResult",
    "PipelineStage",
    "RejectRecord",
    "ingest_events",
]

#: Working-set control only: it must not change which rows land, which are rejected, or the
#: resulting bytes -- a module-level constant, deliberately not a config key, for the same
#: reason plan 01-08's flush knobs are not (RESEARCH-adjacent: batch size changes the
#: working set, never the verdict).
VALIDATION_BATCH_SIZE = 50_000


class IngestResult(BaseModel):
    """The single result `ingest_events` builds and returns -- the only `IngestResult` any
    caller sees. Describes both validation stages, which is what makes
    `nextmove.ingest.quality.evaluate_reject_rate` a gate over the whole pipeline rather than
    over its first half."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows_in: int = Field(ge=0)
    rows_landed: int = Field(ge=0)
    rows_quarantined: int = Field(ge=0)
    rows_rejected_contract: int = Field(ge=0)
    rows_rejected_semantic: int = Field(ge=0)
    reject_rate: float = Field(ge=0.0)
    gates_passed: list[str]
    gates_failed: list[str]
    canonical_path: Path
    rejects_path: Path


class _CanonicalEventRow(BaseModel):
    """`Event`, flattened for the storage layer's generic schema deriver -- see the module
    docstring. `payload` is `event.payload.model_dump_json()`, a lossless JSON round-trip of
    the original typed payload, matching plan 01-08's `EventRow` shape field-for-field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    ts: datetime
    type: str = Field(min_length=1)
    payload: str
    source: str = Field(min_length=1)


def _event_to_row(event: Event) -> _CanonicalEventRow:
    return _CanonicalEventRow(
        event_id=event.event_id,
        customer_id=event.customer_id,
        session_id=event.session_id,
        ts=event.ts,
        type=event.type.value,
        payload=event.payload.model_dump_json(),
        source=event.source,
    )


def _batched(records: Iterable[Mapping[str, Any]], size: int) -> Iterable[list[Mapping[str, Any]]]:
    """Yield successive `size`-length lists drawn from `records`, without ever materializing
    `records` itself as a sequence. `itertools.islice` pulls only what the next batch needs,
    so an unbounded generator is never exhausted ahead of the caller consuming each batch."""
    iterator = iter(records)
    while True:
        batch = list(itertools.islice(iterator, size))
        if not batch:
            return
        yield batch


def _flatten_validation_error(exc: ValidationError) -> tuple[str, str | None]:
    """Flatten a `pydantic.ValidationError` into one reason string naming every offending
    field, and the first offending field's dotted path."""
    errors = exc.errors()
    first_path = ".".join(str(part) for part in errors[0]["loc"]) if errors else None
    reason = "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
        for error in errors
    )
    return reason or str(exc), (first_path or None)


def ingest_events(
    raw_records: Iterable[Mapping[str, Any]],
    resolved: ResolvedConfig,
    adapter_name: str = "simulator",
    out_root: Path | None = None,
    batch_size: int = VALIDATION_BATCH_SIZE,
) -> IngestResult:
    """Validate `raw_records` against the canonical `Event` contract, run the DATA-03
    semantic gates per batch, and land the result append-only in `data/canonical/`.

    Consumes `raw_records` as an iterator in batches of `batch_size`, never as a
    materialized sequence -- `list()`, `tuple()` and `len()` are never called on it. `out_root`
    is forwarded as `root` to every storage call, so a run directed at an alternate root never
    touches the repository's own `data/` tree, and the default root receives nothing when
    `out_root` is `None`.
    """
    adapter_cls = get_adapter(adapter_name)
    adapter = adapter_cls()

    catalog_table = read_table("catalog", Zone.RAW, root=out_root)
    catalog_index = build_catalog_index(catalog_table)
    tracker = SessionMonotonicityTracker(
        session_max_span_seconds=resolved.config.data_quality.session_max_span_seconds
    )

    gate_names = list(resolved.config.data_quality.semantic_gates)
    gate_violation_counts: dict[str, int] = dict.fromkeys(gate_names, 0)

    rows_in = 0
    rows_rejected_contract = 0
    rows_rejected_semantic = 0
    events_part_index = 0
    rejects_part_index = 0

    for batch_records in _batched(raw_records, batch_size):
        rows_in += len(batch_records)

        batch_events: list[Event] = []
        batch_rejects: list[RejectRecord] = []

        for record in batch_records:
            try:
                validated = adapter.to_canonical([record])
            except ValidationError as exc:
                reason, field_path = _flatten_validation_error(exc)
                raw_json = canonical_json(dict(record))
                batch_rejects.append(
                    RejectRecord(
                        reject_id=derive_reject_id(raw_json, reason, PipelineStage.CONTRACT),
                        raw_record=raw_json,
                        reason=reason,
                        field_path=field_path,
                        contract_version=CONTRACT_VERSION,
                        stage=PipelineStage.CONTRACT,
                        source=adapter_name,
                    )
                )
                rows_rejected_contract += 1
                continue
            batch_events.extend(validated)

        gate_results = run_semantic_gates(batch_events, catalog_index, tracker, resolved.config)

        semantically_rejected_ids: set[str] = set()
        for gate_result in gate_results:
            gate_violation_counts[gate_result.gate_name] += gate_result.violation_count
            for reject in gate_result.rejects:
                event_id = json.loads(reject.raw_record)["event_id"]
                if event_id in semantically_rejected_ids:
                    continue
                semantically_rejected_ids.add(event_id)
                batch_rejects.append(reject)
                rows_rejected_semantic += 1

        surviving_events = [e for e in batch_events if e.event_id not in semantically_rejected_ids]

        if surviving_events:
            write_part_file(
                [_event_to_row(e) for e in surviving_events],
                part_dir="events",
                part_index=events_part_index,
                sort_key=CANONICAL_SORT_KEY,
                root=out_root,
                row_model=_CanonicalEventRow,
            )
            events_part_index += 1
        if batch_rejects:
            write_part_file(
                batch_rejects,
                part_dir="rejects",
                part_index=rejects_part_index,
                sort_key=("reject_id",),
                root=out_root,
                row_model=RejectRecord,
            )
            rejects_part_index += 1

    # The raw source tables consulted by this run: `catalog` is always read (gates require
    # it); `events_raw` is included when it exists on disk (the CLI's real invocation path).
    # Unit tests calling `ingest_events` directly with hand-built `raw_records` have no
    # `events_raw.parquet` file, and that is fine -- lineage then names only the dependency
    # that genuinely exists (executor interpretation: `ingest_events`'s signature carries no
    # `input_paths` parameter, so this function resolves its own known raw sources).
    input_paths: list[Path] = [resolve_table_path("catalog", Zone.RAW, root=out_root)]
    events_raw_path = resolve_table_path("events_raw", Zone.RAW, root=out_root)
    if events_raw_path.is_file():
        input_paths.append(events_raw_path)

    events_parts = list_part_files("events", root=out_root)
    if table_exists("events", Zone.CANONICAL, root=out_root):
        events_parts = [resolve_table_path("events", Zone.CANONICAL, root=out_root), *events_parts]
    if events_parts:
        events_path = write_table_from_parts(
            events_parts,
            table_name="events",
            zone=Zone.CANONICAL,
            sort_key=CANONICAL_SORT_KEY,
            resolved_config=resolved,
            producer_stage=Stage.INGEST,
            input_paths=input_paths,
            dedupe_on="event_id",
            root=out_root,
        )
    else:
        events_path = write_table(
            [],
            table_name="events",
            zone=Zone.CANONICAL,
            sort_key=CANONICAL_SORT_KEY,
            resolved_config=resolved,
            producer_stage=Stage.INGEST,
            input_paths=input_paths,
            root=out_root,
            row_model=_CanonicalEventRow,
        )

    rejects_parts = list_part_files("rejects", root=out_root)
    if table_exists("rejects", Zone.CANONICAL, root=out_root):
        rejects_parts = [
            resolve_table_path("rejects", Zone.CANONICAL, root=out_root),
            *rejects_parts,
        ]
    if rejects_parts:
        rejects_path = write_table_from_parts(
            rejects_parts,
            table_name="rejects",
            zone=Zone.CANONICAL,
            sort_key=("reject_id",),
            resolved_config=resolved,
            producer_stage=Stage.INGEST,
            input_paths=input_paths,
            dedupe_on="reject_id",
            root=out_root,
        )
    else:
        rejects_path = write_table(
            [],
            table_name="rejects",
            zone=Zone.CANONICAL,
            sort_key=("reject_id",),
            resolved_config=resolved,
            producer_stage=Stage.INGEST,
            input_paths=input_paths,
            root=out_root,
            row_model=RejectRecord,
        )

    clear_staging(root=out_root)

    lineage_by_table = {record.table_name: record for record in read_lineage(root=out_root)}
    rows_landed = lineage_by_table["events"].row_count

    rows_quarantined = rows_rejected_contract + rows_rejected_semantic
    reject_rate = (rows_quarantined / rows_in) if rows_in else 0.0
    gates_failed = sorted(name for name, count in gate_violation_counts.items() if count > 0)
    gates_passed = sorted(name for name in gate_violation_counts if name not in gates_failed)

    return IngestResult(
        rows_in=rows_in,
        rows_landed=rows_landed,
        rows_quarantined=rows_quarantined,
        rows_rejected_contract=rows_rejected_contract,
        rows_rejected_semantic=rows_rejected_semantic,
        reject_rate=reject_rate,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        canonical_path=events_path,
        rejects_path=rejects_path,
    )
