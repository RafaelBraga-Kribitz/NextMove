"""ENG-08's laptop guarantee for the features stage (review HIGH-13) -- plus the behavioral
acceptance criteria for plan 01-10 Task 2 that have nowhere else to live, since the plan's file
list assigns this module and no separate unit-test file to Task 2.

`_PROFILE_BUDGETS` is the explicit `(max_peak_heap_mb, max_peak_rss_mb, max_wall_clock_s)` triple
per profile a reviewer can argue with, mirroring `test_simulation_budget.py`'s and
`test_ingest_budget.py`'s own tables.

**What `tracemalloc` does and does not cover.** `tracemalloc` measures **Python object
allocation only**. `materialize_grid`'s grid rows never become Python objects on this path at
all -- each chunk's ASOF result streams straight from DuckDB into a Parquet part file -- so this
number should be small and close to constant across profiles; if it grows with the row count, a
`to_pylist()`-shaped regression has reappeared and this is where it would show. The real hazard
ENG-08 names for a horizon-scale producer -- DuckDB's ASOF join and sort working set, and Arrow's
row-group buffers -- is invisible to `tracemalloc` and is covered instead by the peak-RSS test
below, which measures a real child-process subprocess via `resource.getrusage`.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from conftest import SubprocessRunResult

from nextmove.config.loader import ResolvedConfig, load_config
from nextmove.features.compute import (
    COMPUTE_AS_OF_MAX_CUSTOMERS,
    GRID_CHUNK_CUSTOMERS,
    compute_as_of,
    materialize_grid,
)
from nextmove.features.definitions import FEATURE_SET_VERSION
from nextmove.ingest.__main__ import _raw_record_stream
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, ingest_events
from nextmove.simulator.run import run_simulation
from nextmove.storage import Zone, read_lineage, resolve_table_path

if TYPE_CHECKING:
    from conftest import DemoRunResult

#: Explicit per-profile `(max_peak_heap_mb, max_peak_rss_mb, max_wall_clock_s)` budget for the
#: features stage -- distinct numbers from the simulator's/ingest's own tables because this
#: stage's working set (one grid chunk's ASOF join and sort, plus one streamed row group) is a
#: different shape again.
# demo's wall-clock element was widened to 1200.0 for consistency with
# test_simulation_budget.py's own demo entry, which ubuntu-latest CI run 31015357302 measured
# at 638.4s against an original 600.0s budget -- no test in this file actually asserts this
# element (both TestBoundedAccumulation and TestPeakResidentMemory unpack and discard it), so
# this is belt-and-braces margin rather than a fix for an observed failure here.
_PROFILE_BUDGETS: dict[str, tuple[float, float, float]] = {
    "tiny": (128.0, 512.0, 60.0),
    "demo": (512.0, 2048.0, 1200.0),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_ingest_in_process(resolved: ResolvedConfig, out_root: Path) -> None:
    ingest_events(_raw_record_stream(out_root, VALIDATION_BATCH_SIZE), resolved, out_root=out_root)


def _run_features_subprocess(profile: str, out_root: Path) -> float:
    start = time.time()
    subprocess.run(
        [sys.executable, "-m", "nextmove.features", "--profile", profile, "--out", str(out_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return time.time() - start


def _measure_features_subprocess_peak_rss(profile: str, out_root: Path) -> SubprocessRunResult:
    """The features-CLI counterpart of `conftest.measure_subprocess_peak_rss` -- same platform
    handling, pointed at `nextmove.features` and reusing an already-ingested `out_root`."""
    try:
        import resource
    except ImportError:
        return SubprocessRunResult(
            out_root=out_root,
            peak_rss_bytes=None,
            skip_reason="resource module unavailable on this platform (POSIX-only)",
            elapsed_seconds=0.0,
        )
    elapsed = _run_features_subprocess(profile, out_root)
    raw_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_bytes = raw_rss if sys.platform == "darwin" else raw_rss * 1024
    return SubprocessRunResult(
        out_root=out_root, peak_rss_bytes=peak_bytes, skip_reason=None, elapsed_seconds=elapsed
    )


@dataclass(frozen=True)
class _FeaturesRunResult:
    out_root: Path
    resolved: ResolvedConfig
    feature_grid_path: Path
    peak_traced_bytes: int
    max_part_rows: int
    elapsed_seconds: float


def _run_materialize_grid_in_process(
    resolved: ResolvedConfig, out_root: Path, chunk_customers: int = GRID_CHUNK_CUSTOMERS
) -> _FeaturesRunResult:
    import nextmove.features.compute as compute_module

    max_part_rows = 0
    original_write_query_to_part = compute_module.write_query_to_part

    def _tracking_write_query_to_part(sql, part_dir, part_index, sort_key, root=None, **bindings):
        nonlocal max_part_rows
        part_path = original_write_query_to_part(
            sql, part_dir, part_index, sort_key, root=root, **bindings
        )
        if part_dir == "feature_grid":
            import pyarrow.parquet as pq

            row_count = pq.ParquetFile(part_path).metadata.num_rows
            if row_count > max_part_rows:
                max_part_rows = row_count
        return part_path

    compute_module.write_query_to_part = _tracking_write_query_to_part
    tracemalloc.start()
    start = time.time()
    try:
        dest = materialize_grid(resolved, out_root=out_root, chunk_customers=chunk_customers)
        elapsed = time.time() - start
        _current, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        compute_module.write_query_to_part = original_write_query_to_part

    return _FeaturesRunResult(
        out_root=out_root,
        resolved=resolved,
        feature_grid_path=dest,
        peak_traced_bytes=peak_bytes,
        max_part_rows=max_part_rows,
        elapsed_seconds=elapsed,
    )


@pytest.fixture(scope="session")
def demo_features_result(demo_run_result: DemoRunResult) -> _FeaturesRunResult:
    """Ingests, then materializes the feature grid over, the session-scoped `demo_run_result`'s
    raw output -- into the same root, matching the real pipeline's shared-root usage."""
    _run_ingest_in_process(demo_run_result.resolved, demo_run_result.out_root)
    return _run_materialize_grid_in_process(demo_run_result.resolved, demo_run_result.out_root)


@pytest.fixture(scope="session")
def demo_features_subprocess_rss(demo_features_result: _FeaturesRunResult) -> SubprocessRunResult:
    return _measure_features_subprocess_peak_rss("demo", demo_features_result.out_root)


@pytest.fixture(scope="session")
def tiny_features_result(tmp_path_factory: pytest.TempPathFactory) -> _FeaturesRunResult:
    out_root = tmp_path_factory.mktemp("tiny_features_budget")
    resolved = load_config("tiny")
    run_simulation(resolved, out_root=out_root)
    _run_ingest_in_process(resolved, out_root)
    return _run_materialize_grid_in_process(resolved, out_root)


# ---------------------------------------------------------------------------------------
# Bounded Python accumulation
# ---------------------------------------------------------------------------------------


class TestBoundedAccumulation:
    def test_demo_peak_traced_heap_under_budget(
        self, demo_features_result: _FeaturesRunResult
    ) -> None:
        max_heap_mb, _max_rss_mb, _max_wall_s = _PROFILE_BUDGETS["demo"]
        peak_mb = demo_features_result.peak_traced_bytes / (1024 * 1024)
        assert peak_mb < max_heap_mb, (
            f"demo features peak traced heap {peak_mb:.1f}MB exceeds budget {max_heap_mb}MB"
        )


# ---------------------------------------------------------------------------------------
# Peak resident memory (the assertion that can fail on the real hazard: DuckDB's ASOF join and
# sort working set, invisible to tracemalloc)
# ---------------------------------------------------------------------------------------


class TestPeakResidentMemory:
    @pytest.mark.peak_rss
    def test_demo_subprocess_peak_rss_under_budget(
        self, demo_features_subprocess_rss: SubprocessRunResult
    ) -> None:
        if demo_features_subprocess_rss.peak_rss_bytes is None:
            pytest.skip(demo_features_subprocess_rss.skip_reason or "peak RSS unavailable")
        _max_heap_mb, max_rss_mb, _max_wall_s = _PROFILE_BUDGETS["demo"]
        peak_mb = demo_features_subprocess_rss.peak_rss_bytes / (1024 * 1024)
        assert peak_mb < max_rss_mb, (
            f"demo features peak RSS {peak_mb:.1f}MB exceeds budget {max_rss_mb}MB"
        )


# ---------------------------------------------------------------------------------------
# Scale-invariant growth: with a fixed chunk_customers, tiny -> demo growth is expected to be
# near-flat on both instruments, since the same number of customers is in flight at both scales.
# ---------------------------------------------------------------------------------------


class TestScaleInvariantGrowth:
    def test_peak_heap_grows_less_than_customer_count_ratio(
        self, demo_features_result: _FeaturesRunResult, tiny_features_result: _FeaturesRunResult
    ) -> None:
        customer_ratio = (
            demo_features_result.resolved.config.simulator.n_customers
            / tiny_features_result.resolved.config.simulator.n_customers
        )
        heap_ratio = demo_features_result.peak_traced_bytes / tiny_features_result.peak_traced_bytes
        assert heap_ratio < customer_ratio, (
            f"features peak traced heap grew by {heap_ratio:.2f}x, customer count grew by "
            f"{customer_ratio:.2f}x -- growth is no longer sub-linear"
        )

    @pytest.mark.peak_rss
    def test_peak_rss_grows_less_than_customer_count_ratio(
        self,
        demo_features_result: _FeaturesRunResult,
        demo_features_subprocess_rss: SubprocessRunResult,
        tiny_features_result: _FeaturesRunResult,
    ) -> None:
        if demo_features_subprocess_rss.peak_rss_bytes is None:
            pytest.skip(demo_features_subprocess_rss.skip_reason or "peak RSS unavailable")
        tiny_rss_result = _measure_features_subprocess_peak_rss(
            "tiny", tiny_features_result.out_root
        )
        if tiny_rss_result.peak_rss_bytes is None:
            pytest.skip(tiny_rss_result.skip_reason or "peak RSS unavailable")

        customer_ratio = (
            demo_features_result.resolved.config.simulator.n_customers
            / tiny_features_result.resolved.config.simulator.n_customers
        )
        rss_ratio = demo_features_subprocess_rss.peak_rss_bytes / tiny_rss_result.peak_rss_bytes
        assert rss_ratio < customer_ratio, (
            f"features peak RSS grew by {rss_ratio:.2f}x, customer count grew by "
            f"{customer_ratio:.2f}x -- growth is no longer sub-linear"
        )


# ---------------------------------------------------------------------------------------
# The grid really is chunked, and chunking is a working-set control only.
# ---------------------------------------------------------------------------------------


class TestChunking:
    def test_demo_writes_more_than_one_part_file_with_a_small_chunk_size(
        self, demo_features_result: _FeaturesRunResult
    ) -> None:
        """Reuses the already-ingested `demo_features_result.out_root` rather than paying for a
        second demo-scale simulate+ingest; re-materializing with a small `chunk_customers` is
        chunk-invariant (see `test_chunk_size_does_not_change_output_bytes`), so overwriting the
        session fixture's `feature_grid.parquet` in place is safe for tests that run after this
        one."""
        import nextmove.features.compute as compute_module

        part_dirs_seen: list[int] = []
        original = compute_module.write_query_to_part

        def _counting(sql, part_dir, part_index, sort_key, root=None, **bindings):
            if part_dir == "feature_grid":
                part_dirs_seen.append(part_index)
            return original(sql, part_dir, part_index, sort_key, root=root, **bindings)

        compute_module.write_query_to_part = _counting
        try:
            chunk_customers = 500
            materialize_grid(
                demo_features_result.resolved,
                out_root=demo_features_result.out_root,
                chunk_customers=chunk_customers,
            )
        finally:
            compute_module.write_query_to_part = original

        assert len(part_dirs_seen) > 1, (
            "materialize_grid wrote only one feature_grid part file with chunk_customers=500 "
            "over a 2000-customer population -- the chunk loop is not actually chunking"
        )

    def test_no_part_exceeds_chunk_customers_times_horizon_days(
        self, tiny_features_result: _FeaturesRunResult
    ) -> None:
        horizon_days = tiny_features_result.resolved.config.simulator.horizon_days
        ceiling = GRID_CHUNK_CUSTOMERS * horizon_days
        assert tiny_features_result.max_part_rows > 0
        assert tiny_features_result.max_part_rows <= ceiling

    def test_chunk_size_does_not_change_output_bytes(self, tmp_path: Path) -> None:
        resolved = load_config("tiny")
        root_small_chunk = tmp_path / "chunk_small"
        root_large_chunk = tmp_path / "chunk_large"
        run_simulation(resolved, out_root=root_small_chunk)
        run_simulation(resolved, out_root=root_large_chunk)
        _run_ingest_in_process(resolved, root_small_chunk)
        _run_ingest_in_process(resolved, root_large_chunk)

        small = _run_materialize_grid_in_process(resolved, root_small_chunk, chunk_customers=1)
        large = _run_materialize_grid_in_process(
            resolved, root_large_chunk, chunk_customers=resolved.config.simulator.n_customers + 1
        )
        assert _sha256(small.feature_grid_path) == _sha256(large.feature_grid_path)


# ---------------------------------------------------------------------------------------
# The on-demand path cannot become the bulk path.
# ---------------------------------------------------------------------------------------


class TestOnDemandCeiling:
    def test_compute_as_of_refuses_over_the_limit(
        self, tiny_features_result: _FeaturesRunResult
    ) -> None:
        too_many = [str(i) for i in range(COMPUTE_AS_OF_MAX_CUSTOMERS + 1)]
        with pytest.raises(ValueError, match="COMPUTE_AS_OF_MAX_CUSTOMERS"):
            compute_as_of(
                too_many,
                datetime.now(UTC),
                tiny_features_result.resolved,
                out_root=tiny_features_result.out_root,
            )

    def test_compute_as_of_rejects_naive_as_of_ts(
        self, tiny_features_result: _FeaturesRunResult
    ) -> None:
        with pytest.raises(ValueError, match="as_of_ts"):
            compute_as_of(
                ["1"],
                datetime.now(),  # noqa: DTZ005 -- deliberately naive, exercising the guard
                tiny_features_result.resolved,
                out_root=tiny_features_result.out_root,
            )


# ---------------------------------------------------------------------------------------
# One definition, two call sites: compute_as_of and materialize_grid agree exactly.
# ---------------------------------------------------------------------------------------


class TestSharedDefinition:
    def test_compute_as_of_matches_materialize_grid_for_a_shared_key(
        self, tiny_features_result: _FeaturesRunResult
    ) -> None:
        import pyarrow.parquet as pq

        grid_table = pq.ParquetFile(tiny_features_result.feature_grid_path).read()
        row = grid_table.slice(0, 1).to_pylist()[0]
        # as_of_ts round-trips from Parquet as an already tz-aware datetime (the grid column is
        # TIMESTAMPTZ) -- .replace(tzinfo=...) would overwrite the offset rather than convert it.
        as_of_ts = row["as_of_ts"]

        on_demand = compute_as_of(
            [row["customer_id"]],
            as_of_ts,
            tiny_features_result.resolved,
            out_root=tiny_features_result.out_root,
        )
        on_demand_row = on_demand.to_pylist()[0]

        for column in grid_table.schema.names:
            assert on_demand_row[column] == row[column], column

    def test_both_functions_call_build_asof_sql(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        assert source.count("_build_asof_sql(") >= 3  # def + 2 call sites


# ---------------------------------------------------------------------------------------
# Zero active customers: the write_table empty-set fallback fires with the full schema.
# ---------------------------------------------------------------------------------------


class TestZeroActiveCustomers:
    def test_zero_events_still_writes_full_schema(self, tmp_path: Path) -> None:
        from datetime import datetime as dt

        from pydantic import BaseModel, ConfigDict, Field

        from nextmove.ingest.contracts import CANONICAL_SORT_KEY
        from nextmove.storage import Stage, write_table

        class _EmptyEventRow(BaseModel):
            model_config = ConfigDict(extra="forbid", frozen=True)
            event_id: str = Field(min_length=1)
            customer_id: str = Field(min_length=1)
            session_id: str = Field(min_length=1)
            ts: dt
            type: str = Field(min_length=1)
            payload: str
            source: str = Field(min_length=1)

        resolved = load_config("tiny")
        out_root = tmp_path / "zero_active_customers"
        write_table(
            [],
            "events",
            Zone.CANONICAL,
            CANONICAL_SORT_KEY,
            resolved,
            Stage.INGEST,
            root=out_root,
            row_model=_EmptyEventRow,
        )

        dest = materialize_grid(resolved, out_root=out_root)
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(dest)
        assert parquet_file.metadata.num_rows == 0
        assert "rfm_recency_days" in parquet_file.schema_arrow.names
        assert "customer_id" in parquet_file.schema_arrow.names
        assert "as_of_ts" in parquet_file.schema_arrow.names


# ---------------------------------------------------------------------------------------
# The version stamp lands in the file's own Parquet metadata (MEDIUM-10).
# ---------------------------------------------------------------------------------------


class TestVersionStamp:
    def test_feature_set_version_is_stamped_in_parquet_metadata(
        self, tiny_features_result: _FeaturesRunResult
    ) -> None:
        import pyarrow.parquet as pq

        metadata = pq.ParquetFile(tiny_features_result.feature_grid_path).metadata.metadata
        assert metadata[b"feature_set_version"].decode() == FEATURE_SET_VERSION
        for key in (b"config_hash", b"input_tables", b"producer_stage", b"contract_version"):
            assert key in metadata


# ---------------------------------------------------------------------------------------
# HIGH-6: root isolation -- two roots produce equal digests and neither touches the other or
# the repository's own data/ tree.
# ---------------------------------------------------------------------------------------


class TestOutRootIsolation:
    def test_two_out_roots_produce_equal_digests(self, tmp_path: Path) -> None:
        resolved = load_config("tiny")
        root_a = tmp_path / "root_a"
        root_b = tmp_path / "root_b"
        run_simulation(resolved, out_root=root_a)
        run_simulation(resolved, out_root=root_b)
        _run_ingest_in_process(resolved, root_a)
        _run_ingest_in_process(resolved, root_b)

        dest_a = materialize_grid(resolved, out_root=root_a)
        dest_b = materialize_grid(resolved, out_root=root_b)

        assert _sha256(dest_a) == _sha256(dest_b)
        for root in (root_a, root_b):
            assert (root / "features" / "feature_grid.parquet").is_file()
            assert (root / "lineage" / "features.parquet").is_file()

        from nextmove.storage import DATA_ROOT

        assert root_a != DATA_ROOT
        assert root_b != DATA_ROOT

    def test_only_feature_grid_lives_under_features_zone(self, tmp_path: Path) -> None:
        resolved = load_config("tiny")
        out_root = tmp_path / "only_feature_grid"
        run_simulation(resolved, out_root=out_root)
        _run_ingest_in_process(resolved, out_root)
        materialize_grid(resolved, out_root=out_root)

        features_dir = out_root / "features"
        assert [p.name for p in features_dir.iterdir()] == ["feature_grid.parquet"]

    def test_features_stage_does_not_write_into_canonical(self, tmp_path: Path) -> None:
        """(HIGH-3) The features stage's declared DVC dependency is data/canonical/; writing
        into it would make the stage invalidate its own input on every run."""
        resolved = load_config("tiny")
        out_root = tmp_path / "no_canonical_write"
        run_simulation(resolved, out_root=out_root)
        _run_ingest_in_process(resolved, out_root)

        before = {
            name: _sha256(resolve_table_path(name, Zone.CANONICAL, root=out_root))
            for name in ("events", "rejects")
        }
        before_ingest_lineage = _sha256(resolve_table_path("ingest", Zone.LINEAGE, root=out_root))

        materialize_grid(resolved, out_root=out_root)

        after = {
            name: _sha256(resolve_table_path(name, Zone.CANONICAL, root=out_root))
            for name in ("events", "rejects")
        }
        after_ingest_lineage = _sha256(resolve_table_path("ingest", Zone.LINEAGE, root=out_root))

        assert before == after
        assert before_ingest_lineage == after_ingest_lineage
        assert resolve_table_path("features", Zone.LINEAGE, root=out_root).is_file()


class TestCliRedirection:
    def test_cli_with_out_flag_reads_and_writes_only_under_that_directory(
        self, tmp_path: Path
    ) -> None:
        from nextmove.storage import DATA_ROOT

        resolved = load_config("tiny")
        out_dir = tmp_path / "cli_out"
        run_simulation(resolved, out_root=out_dir)
        _run_ingest_in_process(resolved, out_dir)

        # The default data root may already hold artifacts from a prior legitimate run
        # (e.g. `just reproduce`), so "does not exist" is not a usable assertion here.
        # Snapshot it instead and require this --out run to leave it byte-for-byte alone.
        sentinel = DATA_ROOT / "features" / "feature_grid.parquet"
        before = sentinel.stat().st_mtime_ns if sentinel.exists() else None

        result = subprocess.run(
            [sys.executable, "-m", "nextmove.features", "--profile", "tiny", "--out", str(out_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "feature_set_version=" in result.stdout
        assert (out_dir / "features" / "feature_grid.parquet").is_file()

        after = sentinel.stat().st_mtime_ns if sentinel.exists() else None
        assert before == after, f"--out run wrote to the default data root at {sentinel}"


# ---------------------------------------------------------------------------------------
# Write-path classification and import-boundary literal proofs (grep-equivalent, via source
# inspection so the checks travel with the test suite rather than living only in a plan).
# ---------------------------------------------------------------------------------------


class TestWritePathClassification:
    def test_compute_module_uses_the_streaming_merge_tools(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        assert source.count("write_query_to_part") >= 1
        assert source.count("write_table_from_parts") >= 1
        assert "ASOF" in source
        assert "ORDER BY" in source

    def test_materialize_grid_body_never_converts_a_grid_result_to_python(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        tree = ast.parse(source)
        forbidden = {"to_pylist", "to_pandas", "to_pydict"}
        (materialize_grid_node,) = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "materialize_grid"
        ]
        found = [
            sub.attr
            for sub in ast.walk(materialize_grid_node)
            if isinstance(sub, ast.Attribute) and sub.attr in forbidden
        ]
        assert found == [], f"materialize_grid's body converts a grid result via {found}"

    def test_active_customer_ids_is_the_one_legitimate_conversion_site(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        tree = ast.parse(source)
        (helper_node,) = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_active_customer_ids"
        ]
        found = [
            sub.attr
            for sub in ast.walk(helper_node)
            if isinstance(sub, ast.Attribute)
            and sub.attr in {"to_pylist", "to_pandas", "to_pydict"}
        ]
        assert found == ["to_pylist"]

    def test_no_pyarrow_or_type_checking_import_in_compute_module(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        for line in source.splitlines():
            stripped = line.strip()
            assert not (
                (stripped.startswith("from") or stripped.startswith("import"))
                and "pyarrow" in stripped
            ), line
            assert not (
                (stripped.startswith("from") or stripped.startswith("import"))
                and "TYPE_CHECKING" in stripped
            ), line

    def test_table_alias_imported_from_storage_and_annotation_resolves(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        tree = ast.parse(source)
        storage_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "nextmove.storage"
        ]
        assert any("Table" in {alias.name for alias in node.names} for node in storage_imports)

        import inspect

        import nextmove.features.compute as compute_module

        annotation = inspect.signature(compute_module.compute_as_of).return_annotation
        assert annotation in ("Table", compute_module.Table)


class TestLineageMetadata:
    def test_materialize_grid_records_events_as_an_input(
        self, tiny_features_result: _FeaturesRunResult
    ) -> None:
        records = {
            record.table_name: record for record in read_lineage(root=tiny_features_result.out_root)
        }
        assert "events" in records["feature_grid"].input_tables

    def test_resolved_config_object_passed_not_a_hash_string(self) -> None:
        source = Path("src/nextmove/features/compute.py").read_text()
        assert "resolved_config=resolved," in source


class TestJustRecipe:
    def test_justfile_declares_a_features_recipe(self) -> None:
        justfile_text = Path("justfile").read_text()
        assert "features profile=" in justfile_text
        assert "nextmove.features --profile" in justfile_text
