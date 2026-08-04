"""D-21's reject-rate threshold, D-22's one-line summary, and the ingest CLI (review HIGH-12).

Exercises `ingest_events` + `evaluate_reject_rate` together over hand-built batches sized to
land on either side of the configured threshold, plus one end-to-end run through the real
`nextmove.simulator` -> `nextmove.ingest` CLI pair at the `tiny` profile.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from nextmove.config.loader import ResolvedConfig, config_hash, load_config
from nextmove.ingest.pipeline import PipelineStage, ingest_events
from nextmove.ingest.quality import RejectRateExceeded, evaluate_reject_rate, format_dq_summary
from nextmove.storage import Stage, Zone, read_table, write_table

BASE_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


class _CatalogRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sku: str = Field(min_length=1)


@pytest.fixture
def resolved() -> ResolvedConfig:
    return load_config("tiny")


def _write_catalog(
    root: Path, resolved: ResolvedConfig, skus: tuple[str, ...] = ("sku-1",)
) -> None:
    write_table(
        [_CatalogRow(sku=s) for s in skus],
        "catalog",
        Zone.RAW,
        ("sku",),
        resolved,
        Stage.SIMULATE,
        root=root,
    )


def _valid_record(event_id: str, sku: str = "sku-1") -> dict:
    return {
        "event_id": event_id,
        "customer_id": f"c-{event_id}",
        "session_id": f"s-{event_id}",
        "ts": BASE_TS.isoformat(),
        "type": "product_view",
        "payload": {
            "type": "product_view",
            "sku": sku,
            "category": "shoes",
            "unit_price_cents": 1999,
        },
        "source": "simulator",
    }


def _resolved_with_max_reject_rate(
    resolved: ResolvedConfig, max_reject_rate: float
) -> ResolvedConfig:
    new_dq = resolved.config.data_quality.model_copy(update={"max_reject_rate": max_reject_rate})
    new_config = resolved.config.model_copy(update={"data_quality": new_dq})
    return ResolvedConfig(
        config=new_config,
        config_hash=config_hash(new_config),
        profile=resolved.profile,
        source_files=resolved.source_files,
    )


# ---------------------------------------------------------------------------------------
# Threshold boundary
# ---------------------------------------------------------------------------------------


def test_rate_exactly_equal_to_threshold_passes(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    # 1 semantic reject out of 4 rows = 0.25 reject rate.
    resolved = _resolved_with_max_reject_rate(resolved, 0.25)
    records = [_valid_record(f"e{i}") for i in range(3)] + [_valid_record("bad", sku="unknown")]
    result = ingest_events(records, resolved, out_root=tmp_path)
    assert result.reject_rate == pytest.approx(0.25)
    evaluate_reject_rate(result, resolved.config.data_quality)  # must not raise


def test_rate_one_step_above_threshold_raises(tmp_path, resolved):
    _write_catalog(tmp_path, resolved)
    resolved = _resolved_with_max_reject_rate(resolved, 0.20)
    records = [_valid_record(f"e{i}") for i in range(3)] + [_valid_record("bad", sku="unknown")]
    result = ingest_events(records, resolved, out_root=tmp_path)
    assert result.reject_rate == pytest.approx(0.25)
    with pytest.raises(RejectRateExceeded):
        evaluate_reject_rate(result, resolved.config.data_quality)


# ---------------------------------------------------------------------------------------
# HIGH-12: D-21 can fire on semantic violations alone
# ---------------------------------------------------------------------------------------


def test_semantic_only_violations_trip_the_threshold(tmp_path, resolved):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    resolved = _resolved_with_max_reject_rate(resolved, 0.001)
    # Every record is contract-valid; the only violations are semantic (unknown sku).
    records = [_valid_record(f"bad-{i}", sku="sku-unknown") for i in range(3)] + [
        _valid_record("good")
    ]
    result = ingest_events(records, resolved, out_root=tmp_path)
    assert result.rows_rejected_contract == 0
    assert result.rows_rejected_semantic == 3

    with pytest.raises(RejectRateExceeded) as exc_info:
        evaluate_reject_rate(result, resolved.config.data_quality)
    assert exc_info.value.rows_rejected_contract == 0
    assert exc_info.value.rows_rejected_semantic == 3


def test_semantically_rejected_rows_absent_from_events_present_in_rejects(tmp_path, resolved):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    records = [_valid_record("bad", sku="sku-unknown"), _valid_record("good")]
    ingest_events(records, resolved, out_root=tmp_path)

    events_table = read_table("events", Zone.CANONICAL, root=tmp_path)
    events = {row["event_id"] for row in events_table.to_pylist()}
    rejects = read_table("rejects", Zone.CANONICAL, root=tmp_path).to_pylist()
    assert "bad" not in events
    assert "good" in events
    semantic_rejects = [r for r in rejects if r["stage"] == PipelineStage.SEMANTIC.value]
    assert any(json.loads(r["raw_record"])["event_id"] == "bad" for r in semantic_rejects)


def test_summary_line_names_failed_gate_and_shows_per_stage_counts(tmp_path, resolved):
    _write_catalog(tmp_path, resolved, skus=("sku-1",))
    records = [_valid_record("bad", sku="sku-unknown"), _valid_record("good")]
    result = ingest_events(records, resolved, out_root=tmp_path)
    summary = format_dq_summary(result)
    assert "catalog_referential_integrity" in summary
    assert "contract=0" in summary
    assert "semantic=1" in summary


def test_tiny_simulator_only_run_quarantines_nothing(tmp_path, resolved):
    from nextmove.simulator.run import run_simulation

    run_simulation(resolved, out_root=tmp_path)
    from nextmove.ingest.__main__ import _raw_record_stream
    from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE

    result = ingest_events(
        _raw_record_stream(tmp_path, VALIDATION_BATCH_SIZE), resolved, out_root=tmp_path
    )
    assert result.rows_quarantined == 0
    assert result.rows_rejected_contract == 0
    assert result.rows_rejected_semantic == 0
    configured = set(resolved.config.data_quality.semantic_gates)
    assert set(result.gates_passed) == configured
    assert result.gates_failed == []


def test_format_dq_summary_signature_is_exactly_result():
    assert tuple(inspect.signature(format_dq_summary).parameters) == ("result",)


# ---------------------------------------------------------------------------------------
# End-to-end CLI: simulate -> ingest at the tiny profile
# ---------------------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cli_simulate_then_ingest_tiny_exits_zero_and_prints_one_summary_line(tmp_path):
    out_root = tmp_path / "cli_tiny"
    sim = subprocess.run(
        [sys.executable, "-m", "nextmove.simulator", "--profile", "tiny", "--out", str(out_root)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert sim.returncode == 0, sim.stderr

    ingest = subprocess.run(
        [sys.executable, "-m", "nextmove.ingest", "--profile", "tiny", "--out", str(out_root)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert ingest.returncode == 0, ingest.stderr
    summary_lines = [line for line in ingest.stdout.splitlines() if line.startswith("rows_in=")]
    assert len(summary_lines) == 1
    line = summary_lines[0]
    assert "rows_in=" in line
    assert "rows_quarantined=" in line
    assert "reject_rate=" in line
    assert "gates_passed=" in line
    assert "gates_failed=" in line

    assert (out_root / "canonical" / "events.parquet").is_file()
    assert (out_root / "canonical" / "rejects.parquet").is_file()
    rejects = read_table("rejects", Zone.CANONICAL, root=out_root)
    assert rejects.num_rows == 0


def test_cli_exits_non_zero_when_threshold_is_impossible(tmp_path, monkeypatch):
    """Proves the gate is wired to the exit code, in-process: monkeypatches the CLI's own
    `load_config` to return a `ResolvedConfig` with an impossible (negative-only-passable)
    threshold, then calls the real `main()` -- no subprocess, no on-disk config mutation."""
    out_root = tmp_path / "cli_tiny_impossible"
    resolved = load_config("tiny")
    resolved = _resolved_with_max_reject_rate(resolved, -1.0)

    from nextmove.simulator.run import run_simulation

    run_simulation(resolved, out_root=out_root)

    import nextmove.ingest.__main__ as main_module

    monkeypatch.setattr(main_module, "load_config", lambda profile: resolved)
    exit_code = main_module.main(["--profile", "tiny", "--out", str(out_root)])
    assert exit_code != 0


def test_justfile_declares_an_ingest_recipe():
    justfile_text = (_REPO_ROOT / "justfile").read_text()
    assert "\ningest profile=" in justfile_text
    assert "python -m nextmove.ingest" in justfile_text
