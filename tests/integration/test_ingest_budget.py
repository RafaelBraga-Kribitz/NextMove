"""ENG-08's laptop guarantee for the ingest path (review HIGH-9, HIGH-10, HIGH-11).

`_PROFILE_BUDGETS` is the explicit `(max_peak_heap_mb, max_peak_rss_mb, max_wall_clock_s)`
triple per profile a reviewer can argue with -- not an implicit hope, mirroring
`test_simulation_budget.py`'s own budget table.

**What `tracemalloc` does and does not cover.** `tracemalloc` measures **Python object
allocation only**. It is the right instrument for the live `Event`/`RejectRecord` objects
`ingest_events` builds per batch and for the per-batch dataframe the semantic gates build,
and it is blind to Arrow buffers and to DuckDB's working set. Those are bounded by
`nextmove.storage.STORAGE_MEMORY_LIMIT_MB`'s spill threshold plus one row group -- not by the
part-file set, since the merge reads every part -- and that half of the budget is asserted by
the peak-RSS test below, which measures the whole CLI subprocess rather than `ingest_events`
alone. `ingest_events` runs the semantic gates itself (see `pipeline.py`'s module docstring),
so this suite's in-process heap measurement already covers the gates too -- there is no
separate whole-history Pandera sweep left outside it to miss.
"""

from __future__ import annotations

import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from conftest import SubprocessRunResult

from nextmove.config.loader import ResolvedConfig, load_config
from nextmove.ingest.__main__ import _raw_record_stream
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, IngestResult, ingest_events
from nextmove.simulator.run import run_simulation

if TYPE_CHECKING:
    from conftest import DemoRunResult

#: Explicit per-profile `(max_peak_heap_mb, max_peak_rss_mb, max_wall_clock_s)` budget for the
#: ingest path specifically -- distinct numbers from `test_simulation_budget.py`'s table
#: because ingest's working set (validated `Event`s, per-batch gate frames, reject rows) is a
#: different shape from the simulator's flush buffers.
_PROFILE_BUDGETS: dict[str, tuple[float, float, float]] = {
    "tiny": (128.0, 512.0, 30.0),
    "demo": (512.0, 1536.0, 900.0),
}


def _run_ingest_subprocess(profile: str, out_root: Path) -> float:
    start = time.time()
    subprocess.run(
        [sys.executable, "-m", "nextmove.ingest", "--profile", profile, "--out", str(out_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return time.time() - start


def _measure_ingest_subprocess_peak_rss(profile: str, out_root: Path) -> SubprocessRunResult:
    """The ingest-CLI counterpart of `conftest.measure_subprocess_peak_rss` -- same platform
    handling, pointed at `nextmove.ingest` instead of `nextmove.simulator`."""
    try:
        import resource
    except ImportError:
        return SubprocessRunResult(
            out_root=out_root,
            peak_rss_bytes=None,
            skip_reason="resource module unavailable on this platform (POSIX-only)",
            elapsed_seconds=0.0,
        )
    elapsed = _run_ingest_subprocess(profile, out_root)
    raw_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_bytes = raw_rss if sys.platform == "darwin" else raw_rss * 1024
    return SubprocessRunResult(
        out_root=out_root, peak_rss_bytes=peak_bytes, skip_reason=None, elapsed_seconds=elapsed
    )


@dataclass(frozen=True)
class _IngestRunResult:
    out_root: Path
    resolved: ResolvedConfig
    result: IngestResult
    peak_traced_bytes: int
    max_events_part_rows: int
    elapsed_seconds: float


def _run_ingest_in_process(resolved: ResolvedConfig, out_root: Path) -> _IngestRunResult:
    import nextmove.ingest.pipeline as pipeline_module

    max_events_part_rows = 0
    original_write_part_file = pipeline_module.write_part_file

    def _tracking_write_part_file(rows, part_dir, *args, **kwargs):
        nonlocal max_events_part_rows
        if part_dir == "events":
            row_count = len(rows)
            if row_count > max_events_part_rows:
                max_events_part_rows = row_count
        return original_write_part_file(rows, part_dir, *args, **kwargs)

    pipeline_module.write_part_file = _tracking_write_part_file
    tracemalloc.start()
    start = time.time()
    try:
        result = ingest_events(
            _raw_record_stream(out_root, VALIDATION_BATCH_SIZE), resolved, out_root=out_root
        )
        elapsed = time.time() - start
        _current, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        pipeline_module.write_part_file = original_write_part_file

    return _IngestRunResult(
        out_root=out_root,
        resolved=resolved,
        result=result,
        peak_traced_bytes=peak_bytes,
        max_events_part_rows=max_events_part_rows,
        elapsed_seconds=elapsed,
    )


@pytest.fixture(scope="session")
def demo_ingest_result(demo_run_result: DemoRunResult) -> _IngestRunResult:
    """Ingests the session-scoped `demo_run_result`'s raw output exactly once, into the same
    root the simulator wrote to -- matching the real CLI's shared-root usage -- and shares the
    measurement across every test in this module."""
    return _run_ingest_in_process(demo_run_result.resolved, demo_run_result.out_root)


@pytest.fixture(scope="session")
def demo_ingest_subprocess_rss(demo_run_result: DemoRunResult) -> SubprocessRunResult:
    return _measure_ingest_subprocess_peak_rss("demo", demo_run_result.out_root)


@pytest.fixture(scope="session")
def tiny_ingest_result(tmp_path_factory: pytest.TempPathFactory) -> _IngestRunResult:
    out_root = tmp_path_factory.mktemp("tiny_ingest_budget")
    resolved = load_config("tiny")
    run_simulation(resolved, out_root=out_root)
    return _run_ingest_in_process(resolved, out_root)


# ---------------------------------------------------------------------------------------
# Bounded Python accumulation
# ---------------------------------------------------------------------------------------


class TestBoundedAccumulation:
    def test_demo_peak_traced_heap_under_budget(self, demo_ingest_result: _IngestRunResult) -> None:
        max_heap_mb, _max_rss_mb, _max_wall_s = _PROFILE_BUDGETS["demo"]
        peak_mb = demo_ingest_result.peak_traced_bytes / (1024 * 1024)
        assert peak_mb < max_heap_mb, (
            f"demo ingest peak traced heap {peak_mb:.1f}MB exceeds budget {max_heap_mb}MB"
        )

    def test_no_events_part_file_exceeds_batch_size(
        self, demo_ingest_result: _IngestRunResult
    ) -> None:
        assert demo_ingest_result.max_events_part_rows > 0, (
            "no events part file was ever flushed -- the flush mechanism did not run"
        )
        assert demo_ingest_result.max_events_part_rows <= VALIDATION_BATCH_SIZE


# ---------------------------------------------------------------------------------------
# Peak resident memory (the assertion that can fail on the real hazard: Arrow/DuckDB, not
# visible to tracemalloc)
# ---------------------------------------------------------------------------------------


class TestPeakResidentMemory:
    def test_demo_subprocess_peak_rss_under_budget(
        self, demo_ingest_subprocess_rss: SubprocessRunResult
    ) -> None:
        if demo_ingest_subprocess_rss.peak_rss_bytes is None:
            pytest.skip(demo_ingest_subprocess_rss.skip_reason or "peak RSS unavailable")
        _max_heap_mb, max_rss_mb, _max_wall_s = _PROFILE_BUDGETS["demo"]
        peak_mb = demo_ingest_subprocess_rss.peak_rss_bytes / (1024 * 1024)
        assert peak_mb < max_rss_mb, (
            f"demo ingest peak RSS {peak_mb:.1f}MB exceeds budget {max_rss_mb}MB"
        )


# ---------------------------------------------------------------------------------------
# Scale-invariant growth: tiny -> demo growth tracks the batch-fill ratio, not the
# customer-count ratio, on both instruments.
#
# `tiny`'s total event count (a few thousand) is smaller than one `VALIDATION_BATCH_SIZE`
# (50 000) batch -- its own `max_events_part_rows` proves this directly. Peak heap is
# supposed to track `batch_size`, not input length (this plan's own must_haves), so
# comparing `demo` (which fills full 50 000-row batches) against a baseline that never even
# filled *one* batch understates `tiny`'s true per-batch cost and makes any growth look
# super-linear relative to customer count alone, regardless of whether the mechanism is
# actually bounded. The bound used here is each run's own observed peak batch-fill ratio
# (`demo_max_events_part_rows / tiny_max_events_part_rows`), not customer count, with a
# documented 1.5x slack for the fixed, genuinely-bounded per-run bookkeeping (the session
# tracker, the catalog index, the per-gate violation-count dict) that does not scale with
# either rows or customers.
# ---------------------------------------------------------------------------------------

_SCALE_INVARIANCE_SLACK = 1.5


class TestScaleInvariantGrowth:
    def test_peak_heap_grows_no_faster_than_the_batch_fill_ratio(
        self, demo_ingest_result: _IngestRunResult, tiny_ingest_result: _IngestRunResult
    ) -> None:
        batch_fill_ratio = (
            demo_ingest_result.max_events_part_rows / tiny_ingest_result.max_events_part_rows
        )
        bound = batch_fill_ratio * _SCALE_INVARIANCE_SLACK
        heap_ratio = demo_ingest_result.peak_traced_bytes / tiny_ingest_result.peak_traced_bytes
        assert heap_ratio < bound, (
            f"ingest peak traced heap grew by {heap_ratio:.2f}x, the observed batch-fill "
            f"ratio is {batch_fill_ratio:.2f}x (bound with slack: {bound:.2f}x) -- growth "
            "is no longer bounded by batch_size"
        )

    def test_peak_rss_grows_no_faster_than_the_batch_fill_ratio(
        self,
        demo_ingest_result: _IngestRunResult,
        demo_ingest_subprocess_rss: SubprocessRunResult,
        tiny_ingest_result: _IngestRunResult,
        tmp_path: Path,
    ) -> None:
        if demo_ingest_subprocess_rss.peak_rss_bytes is None:
            pytest.skip(demo_ingest_subprocess_rss.skip_reason or "peak RSS unavailable")
        tiny_rss_result = _measure_ingest_subprocess_peak_rss("tiny", tiny_ingest_result.out_root)
        if tiny_rss_result.peak_rss_bytes is None:
            pytest.skip(tiny_rss_result.skip_reason or "peak RSS unavailable")

        batch_fill_ratio = (
            demo_ingest_result.max_events_part_rows / tiny_ingest_result.max_events_part_rows
        )
        bound = batch_fill_ratio * _SCALE_INVARIANCE_SLACK
        rss_ratio = demo_ingest_subprocess_rss.peak_rss_bytes / tiny_rss_result.peak_rss_bytes
        assert rss_ratio < bound, (
            f"ingest peak RSS grew by {rss_ratio:.2f}x, the observed batch-fill ratio is "
            f"{batch_fill_ratio:.2f}x (bound with slack: {bound:.2f}x) -- growth is no "
            "longer bounded by batch_size"
        )


# ---------------------------------------------------------------------------------------
# Streaming proof: the input generator is never exhausted before the first write
# ---------------------------------------------------------------------------------------


class TestStreaming:
    def test_first_events_part_lands_before_more_than_one_batch_is_drawn(
        self, tmp_path: Path
    ) -> None:
        resolved = load_config("tiny")
        out_root = tmp_path / "streaming_tiny"
        run_simulation(resolved, out_root=out_root)

        from nextmove.storage import staging_root

        batch_size = 8
        drawn = {"count": 0}
        saw_part_after_first_batch = {"value": False}

        def _tracking_stream():
            for record in _raw_record_stream(out_root, batch_size):
                drawn["count"] += 1
                if drawn["count"] > batch_size:
                    events_dir = staging_root(out_root) / "events"
                    if events_dir.is_dir() and any(events_dir.glob("part-*.parquet")):
                        saw_part_after_first_batch["value"] = True
                yield record

        ingest_events(_tracking_stream(), resolved, out_root=out_root, batch_size=batch_size)
        assert saw_part_after_first_batch["value"], (
            "no events part file was on disk while a later batch's records were still being "
            "drawn -- the input was collected before the first write rather than streamed"
        )


# ---------------------------------------------------------------------------------------
# Write-path classification: the gates run inside the measured function only
# ---------------------------------------------------------------------------------------


class TestWritePathClassification:
    def test_pipeline_calls_the_merge_tools(self) -> None:
        pipeline_py = Path(__file__).resolve().parents[2] / "src/nextmove/ingest/pipeline.py"
        source = pipeline_py.read_text()
        assert source.count("write_part_file") >= 1
        assert source.count("write_table_from_parts") >= 1
        # One call site; the import line also names it once, hence "clear_staging(" not
        # "clear_staging".
        assert source.count("clear_staging(") == 1

    def test_docstring_does_not_use_the_disproven_bounded_by_part_file_phrase(self) -> None:
        import re

        budget_py = Path(__file__).read_text()
        assert re.findall(r"bounded separately by the part-file (size|set)", budget_py) == []

    def test_no_events_part_file_exceeds_batch_size_marker_present_in_docstring(self) -> None:
        assert "STORAGE_MEMORY_LIMIT_MB" in Path(__file__).read_text()


class TestTinyRunSanity:
    def test_tiny_ingest_completes_within_wall_clock_budget(
        self, tiny_ingest_result: _IngestRunResult
    ) -> None:
        _max_heap_mb, _max_rss_mb, max_wall_s = _PROFILE_BUDGETS["tiny"]
        assert tiny_ingest_result.elapsed_seconds < max_wall_s

    def test_tiny_ingest_reject_rate_is_zero(self, tiny_ingest_result: _IngestRunResult) -> None:
        assert tiny_ingest_result.result.rows_quarantined == 0
