"""Byte-identical write proof at the storage layer, independent of the simulator (ENG-04).

Exercises `nextmove.storage` against hand-built fixtures of ~50 synthetic rows. No simulator
exists yet -- RESEARCH's primary recommendation is to build the determinism harness on a
trivial fixture before the simulator's realism logic exists, so every later change is
validated against a working harness.
"""

import datetime as _dt
import hashlib
import random
import re
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import BaseModel

import nextmove.storage as st
import nextmove.storage._parquet as _parquet_module
import nextmove.storage.repository as repository_module
from nextmove.config.loader import load_config


class InventoryRow(BaseModel):
    """Composite-key fixture: (tick, sku) -- trailing column `sku` legitimately repeats
    across ticks."""

    tick: int
    sku: str
    qty: int


class CustomerDayRow(BaseModel):
    """Composite-key fixture: (customer_id, as_of_ts) -- trailing column `as_of_ts`
    legitimately repeats across customers."""

    customer_id: str
    as_of_ts: str
    value: float


class EventLikeRow(BaseModel):
    """Fixture carrying an idempotency key (`event_id`) distinct from the sort key, for
    cross-part deduplication tests."""

    event_id: str
    tick: int
    sku: str
    qty: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_rows(n_ticks: int = 5, n_skus: int = 10) -> list[InventoryRow]:
    """~50 rows by default: every (tick, sku) pair is unique, so several ties exist on the
    leading `tick` column."""
    rows = []
    for tick in range(n_ticks):
        for i in range(n_skus):
            rows.append(InventoryRow(tick=tick, sku=f"sku-{i:03d}", qty=(tick * n_skus + i) % 17))
    return rows


@pytest.fixture
def resolved_config():
    return load_config("tiny")


@pytest.fixture
def two_roots(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "root_a", tmp_path / "root_b"


# --------------------------------------------------------------------------------------
# Order-independence and stability
# --------------------------------------------------------------------------------------


def test_write_table_order_independent(tmp_path, resolved_config):
    rows = _fixture_rows()
    shuffled = list(rows)
    random.Random(1234).shuffle(shuffled)

    p1 = st.write_table(
        rows,
        "inv_a",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path / "r1",
    )
    p2 = st.write_table(
        shuffled,
        "inv_a",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path / "r2",
    )

    assert _sha256_file(p1) == _sha256_file(p2)


def test_write_table_stable_under_ties_on_leading_columns(tmp_path, resolved_config):
    rows = _fixture_rows()
    reversed_rows = list(reversed(rows))

    p1 = st.write_table(
        rows,
        "inv_b",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path / "r1",
    )
    p2 = st.write_table(
        reversed_rows,
        "inv_b",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path / "r2",
    )

    assert _sha256_file(p1) == _sha256_file(p2)


@pytest.mark.slow
def test_write_table_stable_across_hash_seeds(tmp_path, resolved_config):
    """Python randomizes string hashing per process; a design relying on incidental dict/set
    iteration order would produce different bytes under different PYTHONHASHSEED values."""
    script = """
import sys
from pathlib import Path
sys.path.insert(0, {src!r})
from nextmove.config.loader import load_config
from nextmove.storage.paths import Stage, Zone
import nextmove.storage as st
from pydantic import BaseModel

class InventoryRow(BaseModel):
    tick: int
    sku: str
    qty: int

rows = [
    InventoryRow(tick=t, sku=f"sku-{{i:03d}}", qty=(t * 10 + i) % 17)
    for t in range(5)
    for i in range(10)
]
rc = load_config("tiny")
p = st.write_table(
    rows, "inv", Zone.CANONICAL, ("tick", "sku"), rc, Stage.INGEST, root=Path({root!r})
)
import hashlib
h = hashlib.sha256(open(p, "rb").read()).hexdigest()
print(h)
"""
    src_dir = str(Path(__file__).resolve().parents[2] / "src")
    digests = []
    for seed, root_name in (("0", "seed0"), ("4242", "seed1")):
        root = tmp_path / root_name
        proc = subprocess.run(
            [sys.executable, "-c", script.format(src=src_dir, root=str(root))],
            env={"PYTHONHASHSEED": seed, "PATH": __import__("os").environ.get("PATH", "")},
            capture_output=True,
            text=True,
            check=True,
        )
        digests.append(proc.stdout.strip())
    assert digests[0] == digests[1]
    assert len(digests[0]) == 64


# --------------------------------------------------------------------------------------
# Zero rows
# --------------------------------------------------------------------------------------


def test_write_table_zero_rows_full_schema(tmp_path, resolved_config):
    rows = _fixture_rows()
    st.write_table(
        rows,
        "inv_full",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
    )
    p_empty = st.write_table(
        [],
        "inv_empty",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
        row_model=InventoryRow,
    )
    full_table = st.read_table("inv_full", st.Zone.CANONICAL, root=tmp_path)
    empty_table = st.read_table("inv_empty", st.Zone.CANONICAL, root=tmp_path)
    assert empty_table.num_rows == 0
    assert empty_table.schema.equals(full_table.schema, check_metadata=False)
    assert p_empty.is_file()


def test_write_table_empty_without_row_model_raises(tmp_path, resolved_config):
    with pytest.raises(ValueError, match="row_model"):
        st.write_table(
            [],
            "inv_bad",
            st.Zone.CANONICAL,
            ("tick", "sku"),
            resolved_config,
            st.Stage.INGEST,
            root=tmp_path,
        )


def test_write_table_from_parts_empty_raises_naming_table(tmp_path, resolved_config):
    with pytest.raises(ValueError, match="empty_target"):
        st.write_table_from_parts(
            [],
            "empty_target",
            st.Zone.CANONICAL,
            ("tick", "sku"),
            resolved_config,
            st.Stage.INGEST,
            root=tmp_path,
        )


# --------------------------------------------------------------------------------------
# Atomicity
# --------------------------------------------------------------------------------------


def test_write_table_atomic_on_conversion_error(tmp_path, resolved_config, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("injected conversion failure")

    monkeypatch.setattr(repository_module, "_rows_to_table", _boom)
    dest_dir = tmp_path / "canonical"
    with pytest.raises(RuntimeError, match="injected conversion failure"):
        st.write_table(
            _fixture_rows(),
            "inv_atomic",
            st.Zone.CANONICAL,
            ("tick", "sku"),
            resolved_config,
            st.Stage.INGEST,
            root=tmp_path,
        )
    assert not (dest_dir / "inv_atomic.parquet").exists()
    assert not dest_dir.exists() or list(dest_dir.glob("*.tmp")) == []


def test_write_table_atomic_on_write_error(tmp_path, resolved_config, monkeypatch):
    """Injects a failure inside the Parquet writer loop (after the writer has already been
    opened) and asserts no destination file and no stray temporary file remain."""
    calls = {"n": 0}
    real_write_table = pa.parquet.ParquetWriter.write_table

    def _flaky_write_table(self, table, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 1:
            raise RuntimeError("injected write failure")
        return real_write_table(self, table, **kwargs)

    monkeypatch.setattr(pa.parquet.ParquetWriter, "write_table", _flaky_write_table)
    dest_dir = tmp_path / "canonical"
    with pytest.raises(RuntimeError, match="injected write failure"):
        st.write_table(
            _fixture_rows(),
            "inv_atomic2",
            st.Zone.CANONICAL,
            ("tick", "sku"),
            resolved_config,
            st.Stage.INGEST,
            root=tmp_path,
        )
    assert not (dest_dir / "inv_atomic2.parquet").exists()
    assert not dest_dir.exists() or list(dest_dir.glob("*.tmp")) == []


# --------------------------------------------------------------------------------------
# Composite sort keys (HIGH-8)
# --------------------------------------------------------------------------------------


def test_composite_sort_key_tick_sku_repeating_trailing_column(tmp_path, resolved_config):
    rows = _fixture_rows()
    p = st.write_table(
        rows,
        "inv_composite",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
    )
    t = st.read_table("inv_composite", st.Zone.CANONICAL, root=tmp_path)
    ticks = t.column("tick").to_pylist()
    assert ticks == sorted(ticks)
    assert p.is_file()


def test_composite_sort_key_customer_as_of_ts_repeating_trailing_column(tmp_path, resolved_config):
    rows = [
        CustomerDayRow(customer_id=cid, as_of_ts=day, value=float(i))
        for i, (cid, day) in enumerate(
            (cid, day)
            for cid in ("c1", "c2", "c3", "c4", "c5")
            for day in ("2026-01-01", "2026-01-02")
        )
    ]
    st.write_table(
        rows,
        "feature_grid_fixture",
        st.Zone.FEATURES,
        ("customer_id", "as_of_ts"),
        resolved_config,
        st.Stage.FEATURES,
        root=tmp_path,
    )
    t = st.read_table("feature_grid_fixture", st.Zone.FEATURES, root=tmp_path)
    assert t.num_rows == len(rows)


def test_composite_sort_key_duplicate_whole_tuple_raises(tmp_path, resolved_config):
    rows = [InventoryRow(tick=1, sku="a", qty=1), InventoryRow(tick=1, sku="a", qty=2)]
    with pytest.raises(ValueError, match=r"\('tick', 'sku'\)"):
        st.write_table(
            rows,
            "inv_dup",
            st.Zone.CANONICAL,
            ("tick", "sku"),
            resolved_config,
            st.Stage.INGEST,
            root=tmp_path,
        )


# --------------------------------------------------------------------------------------
# Root addressability (HIGH-6)
# --------------------------------------------------------------------------------------


def test_two_roots_produce_equal_digests_and_stay_isolated(two_roots, resolved_config):
    root_a, root_b = two_roots
    rows = _fixture_rows()
    pa_path = st.write_table(
        rows,
        "inv_root",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root_a,
    )
    pb_path = st.write_table(
        rows,
        "inv_root",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root_b,
    )

    assert _sha256_file(pa_path) == _sha256_file(pb_path)
    assert (root_a / "lineage" / "ingest.parquet").is_file()
    assert (root_b / "lineage" / "ingest.parquet").is_file()
    assert not (st.DATA_ROOT / "canonical" / "inv_root.parquet").exists()


def test_two_roots_untouched_repo_data_root(two_roots, resolved_config):
    root_a, _root_b = two_roots
    before = set(st.DATA_ROOT.rglob("*")) if st.DATA_ROOT.exists() else set()
    st.write_table(
        _fixture_rows(),
        "inv_untouched",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root_a,
    )
    after = set(st.DATA_ROOT.rglob("*")) if st.DATA_ROOT.exists() else set()
    assert before == after


@pytest.mark.slow
def test_data_root_invariant_across_working_directories(tmp_path):
    script = "import nextmove.storage as st; print(st.DATA_ROOT)"
    cwd_a = tmp_path
    cwd_b = tmp_path.parent
    out_a = subprocess.run(
        [sys.executable, "-c", script], cwd=cwd_a, capture_output=True, text=True, check=True
    ).stdout.strip()
    out_b = subprocess.run(
        [sys.executable, "-c", script], cwd=cwd_b, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out_a == out_b


# --------------------------------------------------------------------------------------
# Staging reachability and isolation (HIGH-5)
# --------------------------------------------------------------------------------------


def test_staging_part_files_roundtrip_and_isolation(tmp_path, resolved_config):
    root = tmp_path
    # Touch every zone so clear_staging's "leaves every zone intact" claim is checkable --
    # a zone directory only exists once something has been written into it.
    for zone, stage in (
        (st.Zone.RAW, st.Stage.SIMULATE),
        (st.Zone.FEATURES, st.Stage.FEATURES),
        (st.Zone.GROUND_TRUTH, st.Stage.SIMULATE),
    ):
        st.write_table(
            [InventoryRow(tick=0, sku="seed", qty=0)],
            f"seed_{zone.value}",
            zone,
            ("tick", "sku"),
            resolved_config,
            stage,
            root=root,
        )

    lineage_before = root / "lineage"
    lineage_snapshot_before = sorted(lineage_before.rglob("*")) if lineage_before.exists() else []

    indices = list(range(10))
    random.Random(7).shuffle(indices)
    written_paths = []
    for idx in indices:
        rows = [InventoryRow(tick=idx, sku=f"sku-{idx:03d}", qty=idx)]
        written_paths.append(st.write_part_file(rows, "inv_parts", idx, ("tick", "sku"), root=root))

    listed = st.list_part_files("inv_parts", root=root)
    assert [p.name for p in listed] == [f"part-{i:06d}.parquet" for i in range(10)]

    lineage_snapshot_after = sorted(lineage_before.rglob("*")) if lineage_before.exists() else []
    assert lineage_snapshot_before == lineage_snapshot_after

    merged = st.write_table_from_parts(
        listed,
        "inv_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )
    all_rows = [InventoryRow(tick=i, sku=f"sku-{i:03d}", qty=i) for i in range(10)]
    single = st.write_table(
        all_rows,
        "inv_single",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )
    assert _sha256_file(merged) == _sha256_file(single)

    st.clear_staging(root=root)
    assert not (root / "_staging").exists()
    for zone in st.Zone:
        assert (root / zone.value).is_dir()


def test_resolve_staging_path_rejects_parent_traversal(tmp_path):
    with pytest.raises(ValueError, match="inv_parts"):
        st.resolve_staging_path("../inv_parts", 0, root=tmp_path)


def test_write_part_file_creates_no_lineage(tmp_path):
    st.write_part_file(
        [InventoryRow(tick=1, sku="a", qty=1)], "solo_part", 0, ("tick", "sku"), root=tmp_path
    )
    assert not (tmp_path / "lineage").exists()


# --------------------------------------------------------------------------------------
# Cross-part deduplication
# --------------------------------------------------------------------------------------


def test_dedupe_on_merge_matches_single_deduplicated_write(tmp_path, resolved_config):
    root = tmp_path
    part0 = st.write_part_file(
        [EventLikeRow(event_id="e1", tick=1, sku="a", qty=1)],
        "evt_parts",
        0,
        ("tick", "sku"),
        root=root,
    )
    part1 = st.write_part_file(
        [EventLikeRow(event_id="e2", tick=2, sku="b", qty=2)],
        "evt_parts",
        1,
        ("tick", "sku"),
        root=root,
    )
    part2 = st.write_part_file(
        [EventLikeRow(event_id="e1", tick=1, sku="a", qty=99)],
        "evt_parts",
        2,
        ("tick", "sku"),
        root=root,
    )

    merged = st.write_table_from_parts(
        [part0, part1, part2],
        "evt_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
        dedupe_on="event_id",
    )
    single = st.write_table(
        [
            EventLikeRow(event_id="e1", tick=1, sku="a", qty=1),
            EventLikeRow(event_id="e2", tick=2, sku="b", qty=2),
        ],
        "evt_single",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )
    assert _sha256_file(merged) == _sha256_file(single)
    t = st.read_table("evt_merged", st.Zone.CANONICAL, root=root)
    assert t.column("qty").to_pylist() == [1, 2]


# --------------------------------------------------------------------------------------
# Merge boundedness and out-of-core behavior (HIGH-10)
# --------------------------------------------------------------------------------------

MERGE_PEAK_RSS_BUDGET_MB = 2 * repository_module.STORAGE_MEMORY_LIMIT_MB + 256


@pytest.mark.slow
def test_merge_peak_rss_stays_under_budget(tmp_path):
    """Measures the merge's peak resident set in a **subprocess**, because `ru_maxrss` is a
    high-water mark and an in-process pytest that has already imported the world would
    report its own history rather than the merge's cost. Asserted on RSS rather than
    `tracemalloc`, because `tracemalloc` sees Python allocations only -- an Arrow
    concatenation or a DuckDB buffer is invisible to it, and that is exactly the hazard this
    budget exists to catch (three prior review cycles passed a `tracemalloc`-only budget over
    a design whose Arrow footprint was the whole table)."""
    try:
        import resource  # noqa: F401
    except ImportError:
        pytest.skip("resource module unavailable on this platform (no RSS reading)")

    script = f"""
import resource
import sys
from pathlib import Path
sys.path.insert(0, {str(Path(__file__).resolve().parents[2] / "src")!r})
from pydantic import BaseModel
import nextmove.storage as st
from nextmove.config.loader import load_config

class Row(BaseModel):
    tick: int
    sku: str
    payload: str

root = Path({str(tmp_path)!r})
rc = load_config("tiny")

# Each part is padded so the combined on-disk size comfortably exceeds STORAGE_MEMORY_LIMIT_MB.
padding = "x" * 2000
n_parts = 40
rows_per_part = 400
for part_idx in range(n_parts):
    rows = [
        Row(tick=part_idx, sku=f"sku-{{i:05d}}", payload=padding)
        for i in range(rows_per_part)
    ]
    st.write_part_file(rows, "big_parts", part_idx, ("tick", "sku"), root=root)

parts = st.list_part_files("big_parts", root=root)
st.write_table_from_parts(
    parts, "big_merged", st.Zone.CANONICAL, ("tick", "sku"), rc, st.Stage.INGEST, root=root
)
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    peak_kb_or_bytes = int(proc.stdout.strip().splitlines()[-1])
    peak_mb = (
        peak_kb_or_bytes / 1024 if sys.platform != "darwin" else peak_kb_or_bytes / (1024 * 1024)
    )
    assert peak_mb < MERGE_PEAK_RSS_BUDGET_MB, (
        f"peak RSS {peak_mb:.1f}MB exceeded budget {MERGE_PEAK_RSS_BUDGET_MB}MB"
    )


def test_merge_read_parquet_file_never_called_for_parts(tmp_path, resolved_config, monkeypatch):
    """The merge must not read a part file into Arrow at all -- it reads through DuckDB."""
    root = tmp_path
    parts = [
        st.write_part_file(
            [InventoryRow(tick=i, sku=f"sku-{i:03d}", qty=i)],
            "guard_parts",
            i,
            ("tick", "sku"),
            root=root,
        )
        for i in range(3)
    ]

    def _boom(path):
        raise AssertionError("write_table_from_parts must not call read_parquet_file on parts")

    monkeypatch.setattr(repository_module, "read_parquet_file", _boom)
    # record_lineage=False so the post-write row-count path (which uses ParquetFile metadata,
    # not read_parquet_file) is the only disk touch after the merge.
    st.write_table_from_parts(
        parts,
        "guard_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
        record_lineage=False,
    )


def test_merge_spill_invariance(tmp_path, resolved_config, monkeypatch):
    """A memory control that changes output bytes is a determinism defect wearing a
    performance fix's clothes."""
    root_low = tmp_path / "low"
    root_high = tmp_path / "high"
    rows = _fixture_rows()
    parts_low = [
        st.write_part_file([row], "spill_parts", i, ("tick", "sku"), root=root_low)
        for i, row in enumerate(rows)
    ]
    parts_high = [
        st.write_part_file([row], "spill_parts", i, ("tick", "sku"), root=root_high)
        for i, row in enumerate(rows)
    ]

    monkeypatch.setattr(repository_module, "STORAGE_MEMORY_LIMIT_MB", 1)
    p_low = st.write_table_from_parts(
        parts_low,
        "spill_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root_low,
    )
    monkeypatch.setattr(repository_module, "STORAGE_MEMORY_LIMIT_MB", 4096)
    p_high = st.write_table_from_parts(
        parts_high,
        "spill_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root_high,
    )
    assert _sha256_file(p_low) == _sha256_file(p_high)


def test_row_group_boundary_stability(tmp_path, resolved_config, monkeypatch):
    """Proves row-group boundaries are set by the pinned constant rather than by input
    chunking: writes the same rows through `write_table` and through
    `write_table_from_parts` split so a row-group boundary falls inside a part."""
    monkeypatch.setattr(_parquet_module, "PARQUET_ROW_GROUP_SIZE", 4)
    monkeypatch.setattr(repository_module, "PARQUET_ROW_GROUP_SIZE", 4)

    rows = [InventoryRow(tick=i // 3, sku=f"sku-{i % 3:03d}", qty=i) for i in range(20)]
    single = st.write_table(
        rows,
        "rg_single",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
    )

    # Split into parts of size 3, deliberately not aligned with the row-group size of 4.
    parts = []
    for i in range(0, len(rows), 3):
        chunk = rows[i : i + 3]
        parts.append(st.write_part_file(chunk, "rg_parts", i, ("tick", "sku"), root=tmp_path))
    merged = st.write_table_from_parts(
        parts,
        "rg_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
    )
    assert _sha256_file(single) == _sha256_file(merged)


def test_streaming_uniqueness_detects_duplicate_straddling_batches():
    schema = pa.schema([pa.field("tick", pa.int64()), pa.field("sku", pa.string())])
    batch1 = pa.record_batch({"tick": [1, 1], "sku": ["a", "b"]}, schema=schema)
    batch2 = pa.record_batch({"tick": [1, 2], "sku": ["b", "c"]}, schema=schema)
    reader = pa.RecordBatchReader.from_batches(schema, [batch1, batch2])
    import tempfile

    dest = Path(tempfile.mkdtemp()) / "dup.parquet"
    with pytest.raises(ValueError, match=r"\('tick', 'sku'\)"):
        _parquet_module.write_parquet_stream(reader, dest, ("tick", "sku"), {})
    assert not dest.exists()


# --------------------------------------------------------------------------------------
# Tight-memory dedupe merge shape (G-01-1 gap closure, UAT Test 1)
#
# Parameters tuned on this machine (2026-08-05): 20 parts x 20,000 rows (400,000 rows
# total) with a 400-byte payload column, merged with dedupe_on="event_id" differing from
# sort_key=("customer_id", "ts", "event_id") against a monkeypatched
# STORAGE_MEMORY_LIMIT_MB of 100. This reliably reproduces the DuckDB
# double-blocking-operator hazard documented in .planning/debug/ingest-oom-default-scale.md:
# the legacy single-statement (QUALIFY window + outer ORDER BY) shape fails in ~1.1s with
# "Out of Memory Error: failed to pin block of size 256.0 KiB (95.3 MiB/95.3 MiB used)" --
# the same error signature (differing only in the reported MiB figures) that aborted the
# real 24.7M-row ingest events merge at 512MB. Fixture generation takes ~1.3s and the
# two-stage (materialize-then-sort) shape completes in under 2s total; the whole new
# section's wall clock is well under the ~120s budget.
# --------------------------------------------------------------------------------------

_TIGHT_MEMORY_MERGE_LIMIT_MB = 100
_TIGHT_MEMORY_MERGE_N_PARTS = 20
_TIGHT_MEMORY_MERGE_ROWS_PER_PART = 20_000
_TIGHT_MEMORY_MERGE_PAYLOAD_WIDTH = 400

_MERGE_FIXTURE_BASE_TS = _dt.datetime(2024, 1, 1, tzinfo=_dt.UTC)


def _build_tight_memory_dedupe_fixture(
    tmp_path: Path, n_parts: int, rows_per_part: int, payload_width: int
) -> tuple[list[Path], int]:
    """Build `n_parts` Parquet part files directly via `pyarrow.parquet.write_table` --
    not `write_part_file`, which would pay Pydantic construction cost per row -- carrying
    exactly four columns in order: `event_id` (string), `customer_id` (string), `ts`
    (`pa.timestamp("us", tz="UTC")`, strictly increasing within a customer), and `payload`
    (string, a fixed-width padding blob).

    Introduces exactly one deliberate cross-part duplicate `event_id` at each part
    boundary -- the first row of every part after the first reuses the immediately
    preceding part's last row's `event_id` -- so the dedupe stage is genuinely exercised.
    Every surviving `(customer_id, ts, event_id)` triple stays unique because `event_id`
    alone is unique among the rows dedupe leaves behind. Returns the part paths and the
    expected post-dedupe row count.
    """
    schema = pa.schema(
        [
            pa.field("event_id", pa.string()),
            pa.field("customer_id", pa.string()),
            pa.field("ts", pa.timestamp("us", tz="UTC")),
            pa.field("payload", pa.string()),
        ]
    )
    padding = "p" * payload_width
    n_customers = max(1, rows_per_part // 4)
    customer_occurrence: dict[int, int] = {}
    part_dir = tmp_path / "tight_memory_dedupe_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    part_paths: list[Path] = []
    previous_last_event_id: str | None = None
    global_row_index = 0
    for part_idx in range(n_parts):
        event_ids: list[str] = []
        customer_ids: list[str] = []
        timestamps: list[_dt.datetime] = []
        for row_in_part in range(rows_per_part):
            customer_index = global_row_index % n_customers
            occurrence = customer_occurrence.get(customer_index, 0)
            customer_occurrence[customer_index] = occurrence + 1
            event_ids.append(f"evt-{part_idx:04d}-{row_in_part:06d}")
            customer_ids.append(f"cust-{customer_index:05d}")
            timestamps.append(
                _MERGE_FIXTURE_BASE_TS + _dt.timedelta(seconds=customer_index * 10_000 + occurrence)
            )
            global_row_index += 1
        if previous_last_event_id is not None:
            event_ids[0] = previous_last_event_id
        previous_last_event_id = event_ids[-1]
        table = pa.table(
            {
                "event_id": event_ids,
                "customer_id": customer_ids,
                "ts": timestamps,
                "payload": [padding] * rows_per_part,
            },
            schema=schema,
        )
        part_path = part_dir / f"part-{part_idx:06d}.parquet"
        pq.write_table(table, part_path)
        part_paths.append(part_path)
    expected_row_count = n_parts * rows_per_part - (n_parts - 1)
    return part_paths, expected_row_count


@pytest.mark.slow
def test_dedupe_merge_with_a_different_sort_key_completes_under_a_tight_memory_limit(
    tmp_path, resolved_config, monkeypatch
):
    """A dedupe merge whose `dedupe_on` ("event_id") differs from `sort_key`
    ("customer_id", "ts", "event_id") -- the ingest events merge's exact shape, and the
    only call site in the codebase with that shape -- must complete over a part set that
    comfortably exceeds a tight memory ceiling instead of raising DuckDB's "Out of Memory
    Error: failed to pin block" (G-01-1, .planning/debug/ingest-oom-default-scale.md).
    Fails on the unmodified single-statement implementation with that exact error; passes
    once the merge is split into a materialized dedupe stage and a separate sort stage.
    Deliberately does not read the merged table into Arrow -- at this fixture size that
    would itself allocate hundreds of megabytes and muddy what the test is measuring.
    """
    monkeypatch.setattr(repository_module, "STORAGE_MEMORY_LIMIT_MB", _TIGHT_MEMORY_MERGE_LIMIT_MB)
    part_paths, expected_row_count = _build_tight_memory_dedupe_fixture(
        tmp_path,
        _TIGHT_MEMORY_MERGE_N_PARTS,
        _TIGHT_MEMORY_MERGE_ROWS_PER_PART,
        _TIGHT_MEMORY_MERGE_PAYLOAD_WIDTH,
    )
    dest = st.write_table_from_parts(
        part_paths,
        "tight_memory_events",
        st.Zone.CANONICAL,
        ("customer_id", "ts", "event_id"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
        dedupe_on="event_id",
        record_lineage=False,
    )
    assert pq.ParquetFile(dest).metadata.num_rows == expected_row_count


@pytest.mark.slow
def test_the_single_query_dedupe_and_sort_shape_exhausts_the_same_budget(
    tmp_path, resolved_config, monkeypatch
):
    """Control for the test above. Proves the legacy single-statement shape -- one QUALIFY
    window operator chained directly into an outer ORDER BY in the same query -- really
    does exhaust the tight memory budget the fixed merge completes under, so the sibling
    test is proof the two-stage split actually fixes something rather than a tautology
    that would pass regardless of the merge's shape. If this control ever starts passing
    (the amplification stops reproducing at these parameters on whatever machine runs it),
    the correct response is to re-tune the `_TIGHT_MEMORY_MERGE_*` constants upward -- or,
    if DuckDB's own documented multiple-blocking-operator memory-accounting hazard has
    genuinely been resolved upstream, to record that explicitly. Never respond by deleting
    or weakening the sibling test: an unprovoked control means it proves nothing.
    """
    monkeypatch.setattr(repository_module, "STORAGE_MEMORY_LIMIT_MB", _TIGHT_MEMORY_MERGE_LIMIT_MB)
    part_paths, _expected_row_count = _build_tight_memory_dedupe_fixture(
        tmp_path,
        _TIGHT_MEMORY_MERGE_N_PARTS,
        _TIGHT_MEMORY_MERGE_ROWS_PER_PART,
        _TIGHT_MEMORY_MERGE_PAYLOAD_WIDTH,
    )
    part_list_sql = (
        "[" + ", ".join(repository_module._sql_quote(str(Path(p))) for p in part_paths) + "]"
    )
    order_by = repository_module._order_by_clause(("customer_id", "ts", "event_id"))
    legacy_sql = (
        f"SELECT * FROM read_parquet({part_list_sql}) "
        f'QUALIFY row_number() OVER (PARTITION BY "event_id" ORDER BY {order_by}) = 1 '
        f"ORDER BY {order_by}"
    )
    con = repository_module.connect(root=tmp_path)
    try:
        with pytest.raises(Exception) as excinfo:
            row_group_size = repository_module.PARQUET_ROW_GROUP_SIZE
            reader = con.execute(legacy_sql).to_arrow_reader(row_group_size)
            for _batch in reader:
                pass
        assert "Out of Memory Error" in str(excinfo.value)
    finally:
        con.close()


def test_a_dedupe_merge_never_executes_one_statement_that_both_dedupes_and_sorts(
    tmp_path, resolved_config, monkeypatch
):
    """Runtime guard (not a source-text read): a dedupe merge must execute more than one
    SQL statement, and no single executed statement may contain both a dedupe construct
    (`QUALIFY` or `row_number(`) and an `ORDER BY` outside its own window's `OVER` clause --
    stacking those two blocking operators in one statement is exactly the DuckDB
    memory-accounting hazard G-01-1 traces to. Each `OVER (...)` clause is blanked out
    before the assertion runs, because a window's own internal `ORDER BY` is legitimate
    and must not trip this check."""
    executed_sql: list[str] = []
    real_connect = repository_module.connect

    class _RecordingConnection:
        """Thin proxy recording every SQL string passed to `execute`, delegating
        `execute` and `close` (and everything else) to the real connection."""

        def __init__(self, real_con):
            self._real_con = real_con

        def execute(self, sql, *args, **kwargs):
            executed_sql.append(sql)
            return self._real_con.execute(sql, *args, **kwargs)

        def close(self):
            return self._real_con.close()

        def __getattr__(self, name):
            return getattr(self._real_con, name)

    def _connect_recording(*args, **kwargs):
        return _RecordingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(repository_module, "connect", _connect_recording)

    root = tmp_path
    part0 = st.write_part_file(
        [EventLikeRow(event_id="e1", tick=1, sku="a", qty=1)],
        "guard_dedupe_parts",
        0,
        ("tick", "sku"),
        root=root,
    )
    part1 = st.write_part_file(
        [EventLikeRow(event_id="e2", tick=2, sku="b", qty=2)],
        "guard_dedupe_parts",
        1,
        ("tick", "sku"),
        root=root,
    )
    part2 = st.write_part_file(
        [EventLikeRow(event_id="e1", tick=1, sku="a", qty=99)],
        "guard_dedupe_parts",
        2,
        ("tick", "sku"),
        root=root,
    )

    st.write_table_from_parts(
        [part0, part1, part2],
        "guard_dedupe_merged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
        dedupe_on="event_id",
        record_lineage=False,
    )

    assert len(executed_sql) >= 2, (
        f"expected a dedupe merge to execute at least two separate SQL statements, got "
        f"{len(executed_sql)}: {executed_sql!r}"
    )
    over_clause_re = re.compile(r"OVER\s*\([^()]*\)", re.IGNORECASE)
    for sql in executed_sql:
        blanked = over_clause_re.sub("OVER ( ... )", sql).upper()
        has_dedupe_construct = "QUALIFY" in blanked or "ROW_NUMBER(" in blanked
        has_outer_order_by = "ORDER BY" in blanked
        assert not (has_dedupe_construct and has_outer_order_by), (
            "statement both dedupes and sorts outside its OVER clause: " + repr(sql)
        )


# --------------------------------------------------------------------------------------
# Query-to-part streaming (HIGH-13)
# --------------------------------------------------------------------------------------


def test_write_query_to_part_streams_and_merges(tmp_path, resolved_config):
    root = tmp_path
    source = st.write_table(
        _fixture_rows(),
        "qsrc",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )

    part0 = st.write_query_to_part(
        "SELECT * FROM t WHERE tick < 3", "qparts", 0, ("tick", "sku"), root=root, t=source
    )
    part1 = st.write_query_to_part(
        "SELECT * FROM t WHERE tick >= 3", "qparts", 1, ("tick", "sku"), root=root, t=source
    )

    lineage_dir = root / "lineage"
    lineage_before = sorted(lineage_dir.rglob("*")) if lineage_dir.exists() else []

    st.write_table_from_parts(
        [part0, part1],
        "qmerged",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )

    lineage_after = sorted(lineage_dir.rglob("*")) if lineage_dir.exists() else []
    assert lineage_before == lineage_after  # no lineage row for either part

    direct = st.query("SELECT * FROM t ORDER BY tick, sku", root=root, t=source)
    merged_table = st.read_table("qmerged", st.Zone.CANONICAL, root=root)
    assert merged_table.equals(direct)


def test_write_query_to_part_rejects_reserved_sort_key_binding(tmp_path):
    with pytest.raises(ValueError, match="tick"):
        st.write_query_to_part(
            "SELECT 1", "qparts_bad", 0, ("tick",), root=tmp_path, tick=Path("nope.parquet")
        )


# --------------------------------------------------------------------------------------
# Extra metadata (MEDIUM-10)
# --------------------------------------------------------------------------------------


def test_extra_metadata_lands_alongside_closed_set(tmp_path, resolved_config):
    st.write_table(
        _fixture_rows(),
        "meta_tbl",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
        extra_metadata={"feature_set_version": "abc123"},
    )
    t = st.read_table("meta_tbl", st.Zone.CANONICAL, root=tmp_path)
    md = {k.decode(): v.decode() for k, v in t.schema.metadata.items()}
    assert md["feature_set_version"] == "abc123"
    for key in ("config_hash", "input_tables", "producer_stage", "contract_version"):
        assert key in md


def test_extra_metadata_cannot_override_closed_key(tmp_path, resolved_config):
    with pytest.raises(ValueError, match="config_hash"):
        st.write_table(
            _fixture_rows(),
            "meta_bad",
            st.Zone.CANONICAL,
            ("tick", "sku"),
            resolved_config,
            st.Stage.INGEST,
            root=tmp_path,
            extra_metadata={"config_hash": "forged"},
        )


# --------------------------------------------------------------------------------------
# Input table name derivation (LOW-6)
# --------------------------------------------------------------------------------------


def test_input_table_names_derived_from_path_stems_sorted(tmp_path, resolved_config):
    root = tmp_path
    events_path = st.write_table(
        _fixture_rows(),
        "events",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )
    catalog_path = st.write_table(
        _fixture_rows(),
        "catalog",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )
    st.write_table(
        _fixture_rows(),
        "derived",
        st.Zone.FEATURES,
        ("tick", "sku"),
        resolved_config,
        st.Stage.FEATURES,
        input_paths=[events_path, catalog_path],
        root=root,
    )
    t = st.read_table("derived", st.Zone.FEATURES, root=root)
    md = {k.decode(): v.decode() for k, v in t.schema.metadata.items()}
    import json as _json

    assert _json.loads(md["input_tables"]) == ["catalog", "events"]

    lineage = st.read_lineage(root=root)
    derived_record = next(r for r in lineage if r.table_name == "derived")
    assert derived_record.input_tables == ["catalog", "events"]


# --------------------------------------------------------------------------------------
# Query determinism
# --------------------------------------------------------------------------------------


def test_query_float_aggregate_stable_across_repetitions(tmp_path, resolved_config):
    root = tmp_path
    rows = [InventoryRow(tick=i % 5, sku=f"sku-{i:03d}", qty=i) for i in range(200)]
    path = st.write_table(
        rows,
        "agg_src",
        st.Zone.CANONICAL,
        ("tick", "sku"),
        resolved_config,
        st.Stage.INGEST,
        root=root,
    )

    values = set()
    for _ in range(10):
        result = st.query("SELECT stddev(qty) AS s, corr(tick, qty) AS c FROM t", root=root, t=path)
        d = result.to_pydict()
        values.add((round(d["s"][0], 12), round(d["c"][0], 12)))
    assert len(values) == 1
