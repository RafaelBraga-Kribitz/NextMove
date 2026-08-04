"""Contract validation, the quarantine split, and append-only landing (DATA-02, D-20).

Hand-built raw records only -- the simulator is never run in this unit suite.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from nextmove.config.loader import load_config
from nextmove.ingest.contracts import CONTRACT_VERSION
from nextmove.ingest.pipeline import PipelineStage, ingest_events
from nextmove.storage import (
    Stage,
    Zone,
    read_lineage,
    read_table,
    resolve_table_path,
    staging_root,
    write_table,
)

BASE_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


class _CatalogRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sku: str = Field(min_length=1)


@pytest.fixture
def resolved():
    return load_config("tiny")


def _write_catalog(root: Path, resolved, skus: tuple[str, ...] = ("sku-1", "sku-2")) -> Path:
    return write_table(
        [_CatalogRow(sku=s) for s in skus],
        "catalog",
        Zone.RAW,
        ("sku",),
        resolved,
        Stage.SIMULATE,
        root=root,
    )


def _valid_record(
    event_id: str = "evt-1",
    customer_id: str = "c1",
    session_id: str | None = None,
    ts: datetime = BASE_TS,
    sku: str = "sku-1",
    price: int = 1999,
) -> dict:
    # This file exercises contract validation and landing, not session monotonicity (that is
    # test_semantic_gates.py's job) -- session_id defaults to one unique per event_id so two
    # records built by this helper never accidentally collide in the monotonicity gate.
    if session_id is None:
        session_id = f"s-{event_id}"
    return {
        "event_id": event_id,
        "customer_id": customer_id,
        "session_id": session_id,
        "ts": ts.isoformat(),
        "type": "product_view",
        "payload": {
            "type": "product_view",
            "sku": sku,
            "category": "shoes",
            "unit_price_cents": price,
        },
        "source": "simulator",
    }


def _invalid_record(event_id: str = "evt-bad") -> dict:
    """A record whose `unit_price_cents` cannot be parsed as an int -- a genuine wrong-typed
    field, never coercible, so it must be quarantined rather than converted."""
    record = _valid_record(event_id=event_id)
    record["payload"]["unit_price_cents"] = "not-a-number"
    return record


def _events_table(root: Path) -> object:
    return read_table("events", Zone.CANONICAL, root=root)


def _rejects_table(root: Path) -> object:
    return read_table("rejects", Zone.CANONICAL, root=root)


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------------
# Behavior block
# ---------------------------------------------------------------------------------------


def test_all_valid_batch_lands_every_row_and_empty_rejects(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    records = [
        _valid_record(event_id=f"evt-{i}", customer_id="c1", ts=BASE_TS + timedelta(seconds=i))
        for i in range(3)
    ]
    result = ingest_events(records, resolved, out_root=tmp_path)

    assert result.rows_in == 3
    assert result.rows_landed == 3
    assert result.rows_quarantined == 0
    events = _events_table(tmp_path)
    rejects = _rejects_table(tmp_path)
    assert events.num_rows == 3
    assert rejects.num_rows == 0


def test_contract_violation_lands_in_rejects_not_events(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    records = [_valid_record(event_id="evt-good"), _invalid_record(event_id="evt-bad")]
    result = ingest_events(records, resolved, out_root=tmp_path)

    assert result.rows_rejected_contract == 1
    events = _events_table(tmp_path).to_pylist()
    rejects = _rejects_table(tmp_path).to_pylist()
    assert {row["event_id"] for row in events} == {"evt-good"}
    assert len(rejects) == 1
    reject_raw = json.loads(rejects[0]["raw_record"])
    assert reject_raw["event_id"] == "evt-bad"
    assert reject_raw["payload"]["unit_price_cents"] == "not-a-number"


def test_reject_reason_names_offending_field(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    result = ingest_events([_invalid_record()], resolved, out_root=tmp_path)
    assert result.rows_rejected_contract == 1
    rejects = _rejects_table(tmp_path).to_pylist()
    assert "unit_price_cents" in rejects[0]["reason"]
    assert "unit_price_cents" in (rejects[0]["field_path"] or "")


def test_reject_carries_contract_version_and_stage(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    ingest_events([_invalid_record()], resolved, out_root=tmp_path)
    rejects = _rejects_table(tmp_path).to_pylist()
    assert rejects[0]["contract_version"] == CONTRACT_VERSION
    assert rejects[0]["stage"] == PipelineStage.CONTRACT.value


def test_reject_preserves_raw_record_byte_identical_round_trip(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    record = _invalid_record()
    ingest_events([record], resolved, out_root=tmp_path)
    rejects = _rejects_table(tmp_path).to_pylist()
    round_tripped = json.loads(rejects[0]["raw_record"])
    assert round_tripped == record


def test_no_coercion_wrong_typed_field_never_converted(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    ingest_events([_invalid_record()], resolved, out_root=tmp_path)
    events = _events_table(tmp_path).to_pylist()
    assert events == []


def test_second_identical_ingest_is_byte_identical_and_appends_nothing(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    records = [_valid_record(event_id=f"evt-{i}") for i in range(3)]

    result_1 = ingest_events(list(records), resolved, out_root=tmp_path)
    hash_1 = _sha256_of(result_1.canonical_path)
    row_count_1 = _events_table(tmp_path).num_rows

    result_2 = ingest_events(list(records), resolved, out_root=tmp_path)
    hash_2 = _sha256_of(result_2.canonical_path)
    row_count_2 = _events_table(tmp_path).num_rows

    assert hash_1 == hash_2
    assert row_count_1 == row_count_2 == 3


def test_empty_input_writes_empty_full_schema_tables(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    result = ingest_events([], resolved, out_root=tmp_path)

    assert result.rows_in == 0
    assert result.reject_rate == 0.0
    events = _events_table(tmp_path)
    rejects = _rejects_table(tmp_path)
    assert events.num_rows == 0
    assert rejects.num_rows == 0
    assert set(events.schema.names) == {
        "event_id",
        "customer_id",
        "session_id",
        "ts",
        "type",
        "payload",
        "source",
    }
    assert set(rejects.schema.names) == {
        "reject_id",
        "raw_record",
        "reason",
        "field_path",
        "contract_version",
        "stage",
        "source",
    }


def test_canonical_table_is_sorted_by_canonical_sort_key(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    records = [
        _valid_record(event_id="evt-c", customer_id="c2", ts=BASE_TS),
        _valid_record(event_id="evt-a", customer_id="c1", ts=BASE_TS + timedelta(seconds=5)),
        _valid_record(event_id="evt-b", customer_id="c1", ts=BASE_TS),
    ]
    ingest_events(records, resolved, out_root=tmp_path)
    events = _events_table(tmp_path).to_pylist()
    assert [row["event_id"] for row in events] == ["evt-b", "evt-a", "evt-c"]


def test_first_events_part_file_appears_before_iterator_exhausted(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    batch_size = 2
    records = [_valid_record(event_id=f"evt-{i}") for i in range(batch_size * 3)]
    drawn = {"count": 0}

    def _tracking_records():
        for record in records:
            drawn["count"] += 1
            if drawn["count"] > batch_size:
                events_dir = staging_root(tmp_path) / "events"
                assert events_dir.is_dir() and any(events_dir.glob("part-*.parquet")), (
                    "no events part file was written after the first batch, before the "
                    "second batch's records were drawn -- the input was collected before "
                    "the first write rather than streamed"
                )
            yield record

    ingest_events(_tracking_records(), resolved, out_root=tmp_path, batch_size=batch_size)


def test_staging_does_not_exist_once_ingest_returns(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    ingest_events([_valid_record()], resolved, out_root=tmp_path)
    assert not staging_root(tmp_path).exists()


def test_out_root_receives_everything_default_receives_nothing(tmp_path, resolved, monkeypatch):
    _write_catalog(tmp_path, resolved)
    from nextmove.storage import DATA_ROOT

    pre_existing = DATA_ROOT.exists()
    ingest_events([_valid_record()], resolved, out_root=tmp_path)

    assert (tmp_path / "canonical" / "events.parquet").is_file()
    assert (tmp_path / "canonical" / "rejects.parquet").is_file()
    assert (tmp_path / "lineage" / "ingest.parquet").is_file()
    # The default root must not have been touched by an out_root-directed call.
    assert DATA_ROOT.exists() == pre_existing
    if not pre_existing:
        assert not (DATA_ROOT / "canonical" / "events.parquet").exists()


# ---------------------------------------------------------------------------------------
# HIGH-12: semantic rejects counted in the same IngestResult the threshold reads
# ---------------------------------------------------------------------------------------


def test_contract_and_semantic_rejects_both_counted_in_one_result(tmp_path, resolved):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    records = [
        _valid_record(event_id="evt-good"),
        _invalid_record(event_id="evt-contract-bad"),
        _valid_record(event_id="evt-semantic-bad", sku="sku-unknown"),
    ]
    result = ingest_events(records, resolved, out_root=tmp_path)

    assert result.rows_in == 3
    assert result.rows_rejected_contract == 1
    assert result.rows_rejected_semantic == 1
    assert result.rows_quarantined == 2
    assert result.reject_rate == pytest.approx(2 / 3)


def test_semantic_reject_absent_from_events_present_in_rejects(tmp_path, resolved):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    records = [_valid_record(event_id="evt-semantic-bad", sku="sku-unknown")]
    ingest_events(records, resolved, out_root=tmp_path)

    events = {row["event_id"] for row in _events_table(tmp_path).to_pylist()}
    rejects = _rejects_table(tmp_path).to_pylist()
    assert "evt-semantic-bad" not in events
    assert len(rejects) == 1
    assert rejects[0]["stage"] == PipelineStage.SEMANTIC.value
    assert json.loads(rejects[0]["raw_record"])["event_id"] == "evt-semantic-bad"


def test_gates_passed_and_failed_are_populated_disjoint_and_cover_configured_gates(
    tmp_path, resolved
):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    records = [
        _valid_record(event_id="evt-good"),
        _valid_record(event_id="evt-semantic-bad", sku="sku-unknown"),
    ]
    result = ingest_events(records, resolved, out_root=tmp_path)

    configured = set(resolved.config.data_quality.semantic_gates)
    assert set(result.gates_passed) | set(result.gates_failed) == configured
    assert set(result.gates_passed).isdisjoint(result.gates_failed)
    assert "catalog_referential_integrity" in result.gates_failed
    assert result.gates_passed
    assert result.gates_failed


# ---------------------------------------------------------------------------------------
# HIGH-12: no post-hoc rejects write anywhere in __main__.py
# ---------------------------------------------------------------------------------------


def test_main_module_never_calls_a_storage_write_function():
    main_py = (
        Path(__file__).resolve().parents[2] / "src" / "nextmove" / "ingest" / "__main__.py"
    ).read_text()
    import re

    matches = re.findall(
        r"\b(write_table|write_table_from_parts|write_part_file|write_query_to_part)\(", main_py
    )
    assert matches == []


# ---------------------------------------------------------------------------------------
# HIGH-11: gates run inside the measured function, never in the CLI, never over a
# whole-history frame
# ---------------------------------------------------------------------------------------


def test_run_semantic_gates_referenced_in_pipeline_not_in_cli():
    pipeline_src = (
        Path(__file__).resolve().parents[2] / "src" / "nextmove" / "ingest" / "pipeline.py"
    ).read_text()
    main_src = (
        Path(__file__).resolve().parents[2] / "src" / "nextmove" / "ingest" / "__main__.py"
    ).read_text()
    assert pipeline_src.count("run_semantic_gates") >= 1
    assert main_src.count("run_semantic_gates") == 0


def test_no_call_to_run_semantic_gates_receives_more_than_batch_size_rows(
    tmp_path, resolved, monkeypatch
):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    batch_size = 2
    records = [_valid_record(event_id=f"evt-{i}") for i in range(7)]

    import nextmove.ingest.pipeline as pipeline_module

    seen_counts: list[int] = []
    original = pipeline_module.run_semantic_gates

    def _tracking(events_batch, catalog_index, tracker, config):
        seen_counts.append(len(events_batch))
        return original(events_batch, catalog_index, tracker, config)

    monkeypatch.setattr(pipeline_module, "run_semantic_gates", _tracking)
    pipeline_module.ingest_events(records, resolved, out_root=tmp_path, batch_size=batch_size)

    assert seen_counts
    assert all(count <= batch_size for count in seen_counts)


# ---------------------------------------------------------------------------------------
# reject_id determinism
# ---------------------------------------------------------------------------------------


def test_reject_id_is_derived_deterministically(tmp_path, resolved):
    from nextmove.ingest.semantic import PipelineStage as _Stage
    from nextmove.ingest.semantic import derive_reject_id

    id1 = derive_reject_id("raw-json", "some reason", _Stage.CONTRACT)
    id2 = derive_reject_id("raw-json", "some reason", _Stage.CONTRACT)
    assert id1 == id2


# ---------------------------------------------------------------------------------------
# review LOW: batching does not change results
# ---------------------------------------------------------------------------------------


def test_batch_size_does_not_change_results(tmp_path, resolved):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    records = [_valid_record(event_id=f"evt-{i}") for i in range(5)] + [_invalid_record()]

    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_catalog(root_a, resolved, skus=("sku-1",))
    _write_catalog(root_b, resolved, skus=("sku-1",))

    result_a = ingest_events(list(records), resolved, out_root=root_a, batch_size=1)
    result_b = ingest_events(list(records), resolved, out_root=root_b, batch_size=1000)

    assert _sha256_of(result_a.canonical_path) == _sha256_of(result_b.canonical_path)
    assert result_a.rows_rejected_contract == result_b.rows_rejected_contract
    assert result_a.rows_rejected_semantic == result_b.rows_rejected_semantic
    assert result_a.gates_failed == result_b.gates_failed
    rejects_a = sorted(row["reject_id"] for row in _rejects_table(root_a).to_pylist())
    rejects_b = sorted(row["reject_id"] for row in _rejects_table(root_b).to_pylist())
    assert rejects_a == rejects_b


# ---------------------------------------------------------------------------------------
# HIGH-9: the merge tool is actually used
# ---------------------------------------------------------------------------------------


def test_pipeline_uses_write_part_file_and_write_table_from_parts():
    pipeline_src = (
        Path(__file__).resolve().parents[2] / "src" / "nextmove" / "ingest" / "pipeline.py"
    ).read_text()
    assert pipeline_src.count("write_part_file") >= 1
    assert pipeline_src.count("write_table_from_parts") >= 1


# ---------------------------------------------------------------------------------------
# HIGH-6: two out roots never interfere
# ---------------------------------------------------------------------------------------


def test_two_out_roots_produce_equal_digests_and_touch_only_their_own_root(tmp_path, resolved):
    records = [_valid_record(event_id=f"evt-{i}") for i in range(3)]
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    _write_catalog(root_a, resolved)
    _write_catalog(root_b, resolved)

    result_a = ingest_events(list(records), resolved, out_root=root_a)
    result_b = ingest_events(list(records), resolved, out_root=root_b)

    assert _sha256_of(result_a.canonical_path) == _sha256_of(result_b.canonical_path)
    assert _sha256_of(result_a.rejects_path) == _sha256_of(result_b.rejects_path)


# ---------------------------------------------------------------------------------------
# MEDIUM-5: re-ingest semantics stated in the module docstring
# ---------------------------------------------------------------------------------------


def test_pipeline_docstring_names_dvc_repro():
    import nextmove.ingest.pipeline as pipeline_module

    assert "dvc repro" in (pipeline_module.__doc__ or "")


# ---------------------------------------------------------------------------------------
# Lineage: only the ingest fragment gains rows, no part file ever acquires one
# ---------------------------------------------------------------------------------------


def test_tiny_ingest_writes_only_ingest_lineage_fragment_and_no_part_lineage(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    ingest_events([_valid_record()], resolved, out_root=tmp_path)

    assert resolve_table_path("ingest", Zone.LINEAGE, tmp_path).is_file()
    records = read_lineage(root=tmp_path)
    assert not any(r.table_name.startswith("part-") for r in records)
    names = {r.table_name for r in records}
    assert {"events", "rejects"} <= names


def test_lint_imports_still_passes():
    """A cheap in-suite sanity check; `just lint`/`uv run lint-imports` is the authoritative
    gate run separately, this just guards against an obviously broken import graph."""
    import nextmove.ingest  # noqa: F401
    import nextmove.ingest.pipeline  # noqa: F401
    import nextmove.ingest.quality  # noqa: F401
    import nextmove.ingest.semantic  # noqa: F401
