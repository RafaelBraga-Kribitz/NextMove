"""Byte-identical two-run proof over the full `ci`-profile pipeline (ENG-04, phase success
criterion 1). Extends plan 01-06's storage-layer determinism harness
(`tests/golden/test_deterministic_write.py`) to the full simulate -> ingest -> features
pipeline, run as a whole rather than one storage call at a time.

Two independent output trees are obtained by passing `--out` to each of the three stage CLI
modules directly, never via `dvc repro` (which always writes to the default `DATA_ROOT` by
design -- two pipeline invocations would land in the same tree and the second would overwrite
the first, making the comparison vacuous). `DATA_ROOT` is anchored to the storage module's own
file location rather than the working directory (`nextmove.storage.paths`'s module docstring),
which is what keeps the two-roots assertion and the environment-independence assertion below
two genuinely independent experiments rather than the same one written twice.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml

import nextmove.features.__main__ as features_cli
import nextmove.ingest.__main__ as ingest_cli
import nextmove.simulator.__main__ as simulator_cli
from nextmove.config.loader import ResolvedConfig, deep_merge, load_config
from nextmove.features.compute import materialize_grid
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, ingest_events
from nextmove.simulator.run import run_simulation
from nextmove.storage import DATA_ROOT, Zone, connect, resolve_table_path

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(REPO_ROOT / "src")
CONFIG_DIR = REPO_ROOT / "config"

#: The nine data tables plus the three lineage fragments -- discovered by walking the output
#: root rather than hardcoded elsewhere, but pinned here as the *expected* set so a stage that
#: silently stops writing a table (or a leaked staging file that silently inflates the set)
#: fails loudly instead of the comparison quietly covering fewer files than it claims.
EXPECTED_RELATIVE_FILES = frozenset(
    {
        "raw/campaigns.parquet",
        "raw/catalog.parquet",
        "raw/events_raw.parquet",
        "raw/inventory_snapshots.parquet",
        "ground_truth/customer_traits.parquet",
        "ground_truth/ground_truth_uplift.parquet",
        "canonical/events.parquet",
        "canonical/rejects.parquet",
        "features/feature_grid.parquet",
        "lineage/simulate.parquet",
        "lineage/ingest.parquet",
        "lineage/features.parquet",
    }
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discover_files(root: Path) -> dict[str, Path]:
    """Every `*.parquet` file under `root`, keyed by its root-relative posix path. Excludes
    anything under a `_staging` directory -- a leaked part file must fail the *count*
    assertion for what it is, not silently inflate the discovered set."""
    found: dict[str, Path] = {}
    if not root.exists():
        return found
    for path in root.rglob("*.parquet"):
        if "_staging" in path.parts:
            continue
        found[path.relative_to(root).as_posix()] = path
    return found


def _digests(root: Path) -> dict[str, str]:
    return {rel: _sha256_file(path) for rel, path in _discover_files(root).items()}


def _run_pipeline_cli(profile: str, out_root: Path) -> None:
    """Run the three stage CLI modules in process, each forwarding `--out out_root` --
    the dual-root mechanism `tests/golden/test_deterministic_write.py`'s HIGH-6 fixtures use at
    the storage layer, applied here to the whole pipeline."""
    args = ["--profile", profile, "--out", str(out_root)]
    assert simulator_cli.main(args) == 0
    assert ingest_cli.main(args) == 0
    assert features_cli.main(args) == 0


def _raw_record_stream(out_root: Path, batch_size: int):
    """Mirrors `nextmove.ingest.__main__._raw_record_stream` exactly, for callers driving
    `ingest_events` directly against a `ResolvedConfig` the CLI's own `load_config(args.profile)`
    call could not have produced (a temporary, mutated config tree)."""
    events_path = resolve_table_path("events_raw", Zone.RAW, root=out_root)
    con = connect(root=out_root)
    try:
        result = con.execute(f"SELECT * FROM read_parquet({str(events_path)!r})")
        reader = result.to_arrow_reader(batch_size)
        for record_batch in reader:
            for row in record_batch.to_pylist():
                row = dict(row)
                row["payload"] = json.loads(row["payload"])
                yield row
    finally:
        con.close()


def _run_pipeline_for_config(resolved: ResolvedConfig, out_root: Path) -> None:
    """The library-level equivalent of `_run_pipeline_cli`, for a `ResolvedConfig` obtained
    from a temporary config tree the CLI's hardcoded default config directory cannot reach."""
    run_simulation(resolved, out_root=out_root)
    ingest_events(_raw_record_stream(out_root, VALIDATION_BATCH_SIZE), resolved, out_root=out_root)
    materialize_grid(resolved, out_root=out_root)


def _copy_config_tree(dest: Path) -> Path:
    import shutil

    shutil.copytree(CONFIG_DIR, dest)
    return dest


def _apply_yaml_override(path: Path, override: dict) -> None:
    data = yaml.safe_load(path.read_text()) or {}
    merged = deep_merge(data, override)
    path.write_text(yaml.safe_dump(merged, sort_keys=False))


_PIPELINE_SCRIPT = """
import sys
sys.path.insert(0, {src!r})
from nextmove.simulator.__main__ import main as simulate_main
from nextmove.ingest.__main__ import main as ingest_main
from nextmove.features.__main__ import main as features_main
args = ["--profile", {profile!r}, "--out", {root!r}]
assert simulate_main(args) == 0, "simulate failed"
assert ingest_main(args) == 0, "ingest failed"
assert features_main(args) == 0, "features failed"
"""


def _run_pipeline_subprocess(profile: str, out_root: Path, *, hash_seed: str, cwd: Path) -> None:
    script = _PIPELINE_SCRIPT.format(src=SRC_DIR, profile=profile, root=str(out_root))
    # Inherits the rest of the parent environment rather than a minimal one: the full package
    # import graph (pandera -> typeguard -> asyncio.windows_events) needs the OS's own
    # environment (e.g. SystemRoot) to initialize on Windows. Only PYTHONHASHSEED is the
    # deliberately varied axis here; that is the property this test exercises.
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"


# --------------------------------------------------------------------------------------
# Headline claim: two ci-profile runs into two independent output trees are byte-identical.
# --------------------------------------------------------------------------------------


def test_ci_profile_byte_identical_across_two_output_roots(tmp_path):
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"

    data_root_before = set(DATA_ROOT.rglob("*")) if DATA_ROOT.exists() else set()

    _run_pipeline_cli("ci", root_a)
    _run_pipeline_cli("ci", root_b)

    files_a = _discover_files(root_a)
    files_b = _discover_files(root_b)

    assert set(files_a) == EXPECTED_RELATIVE_FILES, (
        f"root_a discovered {set(files_a)} != expected {EXPECTED_RELATIVE_FILES}"
    )
    assert set(files_b) == EXPECTED_RELATIVE_FILES, (
        f"root_b discovered {set(files_b)} != expected {EXPECTED_RELATIVE_FILES}"
    )

    mismatched = sorted(
        rel
        for rel in EXPECTED_RELATIVE_FILES
        if _sha256_file(files_a[rel]) != _sha256_file(files_b[rel])
    )
    assert not mismatched, (
        f"the following files were not byte-identical across the two runs: {mismatched}"
    )

    # Neither root holds a file belonging to the other.
    for path in files_a.values():
        assert root_b not in path.parents
    for path in files_b.values():
        assert root_a not in path.parents

    # The repository's own data/ tree is untouched by this test.
    data_root_after = set(DATA_ROOT.rglob("*")) if DATA_ROOT.exists() else set()
    assert data_root_before == data_root_after

    # No leaked staging directory or staging file in either root's discovered set.
    for rel in files_a:
        assert "_staging" not in rel
    for rel in files_b:
        assert "_staging" not in rel
    assert not (root_a / "_staging").exists()
    assert not (root_b / "_staging").exists()


# --------------------------------------------------------------------------------------
# Adjacency: equal seeds never diverge, different seeds never collide.
# --------------------------------------------------------------------------------------


def test_seed_adjacency_equal_seeds_match_different_seed_diverges(tmp_path):
    root_same_a = tmp_path / "same_a"
    root_same_b = tmp_path / "same_b"
    _run_pipeline_cli("ci", root_same_a)
    _run_pipeline_cli("ci", root_same_b)
    assert _digests(root_same_a) == _digests(root_same_b)

    config_dir = _copy_config_tree(tmp_path / "cfg_diff_seed")
    _apply_yaml_override(config_dir / "simulator.yaml", {"simulator": {"seeds": {"world": 999999}}})
    resolved_diff = load_config("ci", config_dir=config_dir)
    root_diff = tmp_path / "diff_seed"
    _run_pipeline_for_config(resolved_diff, root_diff)

    digests_baseline = _digests(root_same_a)
    digests_diff = _digests(root_diff)
    assert digests_baseline != digests_diff, "changing the world seed produced identical bytes"
    assert any(digests_baseline[rel] != digests_diff[rel] for rel in EXPECTED_RELATIVE_FILES)


# --------------------------------------------------------------------------------------
# Empty: a zero-row table still carries the full schema and is byte-identical across runs.
# --------------------------------------------------------------------------------------


def test_zero_customers_produces_full_schema_zero_row_tables(tmp_path):
    """`n_customers` and `horizon_days` are both schema-constrained to be strictly positive
    (`Field(gt=0)`), so a literal zero-customer world is not a valid config. Zeroing both
    organic session probability and campaign send probability instead produces a world with
    real customers who never generate a single event -- the horizon-scaled `events_raw` table,
    and everything downstream of it, land with zero rows and the full schema."""
    config_dir_a = _copy_config_tree(tmp_path / "cfg_zero_a")
    config_dir_b = _copy_config_tree(tmp_path / "cfg_zero_b")
    zero_overlay = {
        "simulator": {
            "n_customers": 5,
            "horizon_days": 3,
            "engagement": {"base_session_probability": 0.0},
            "campaigns": {"send_probability_per_eligible_day": 0.0},
        }
    }
    for config_dir in (config_dir_a, config_dir_b):
        (config_dir / "profiles" / "zero.yaml").write_text(yaml.safe_dump(zero_overlay))

    resolved_a = load_config("zero", config_dir=config_dir_a)
    resolved_b = load_config("zero", config_dir=config_dir_b)
    root_a = tmp_path / "zero_a"
    root_b = tmp_path / "zero_b"
    _run_pipeline_for_config(resolved_a, root_a)
    _run_pipeline_for_config(resolved_b, root_b)

    zero_row_tables = {
        "raw/events_raw.parquet",
        "canonical/events.parquet",
        "canonical/rejects.parquet",
        "features/feature_grid.parquet",
    }
    for rel in zero_row_tables:
        path_a = root_a / rel
        path_b = root_b / rel
        assert path_a.is_file(), f"{rel} missing from zero-customer run"
        table_a = pq.read_table(path_a)
        table_b = pq.read_table(path_b)
        assert table_a.num_rows == 0, f"{rel} expected zero rows, got {table_a.num_rows}"
        assert table_a.schema.equals(table_b.schema, check_metadata=False)
        assert _sha256_file(path_a) == _sha256_file(path_b), f"{rel} not byte-identical"


# --------------------------------------------------------------------------------------
# Environment independence: differing PYTHONHASHSEED and working directory, still two
# distinct --out roots -- a different experiment from the plain two-roots test above.
# --------------------------------------------------------------------------------------


def test_environment_independence_hash_seed_and_working_directory(tmp_path):
    cwd_a = tmp_path / "env_a"
    cwd_b = tmp_path / "env_b"
    cwd_a.mkdir()
    cwd_b.mkdir()
    root_a = cwd_a / "out"
    root_b = cwd_b / "out"

    _run_pipeline_subprocess("ci", root_a, hash_seed="0", cwd=cwd_a)
    _run_pipeline_subprocess("ci", root_b, hash_seed="4242", cwd=cwd_b)

    digests_a = _digests(root_a)
    digests_b = _digests(root_b)
    assert set(digests_a) == EXPECTED_RELATIVE_FILES
    assert digests_a == digests_b


# --------------------------------------------------------------------------------------
# Interruption: a killed ingest leaves no partial table and no leftover temp file at the
# destination; a subsequent clean run reproduces the expected digests.
# --------------------------------------------------------------------------------------


def test_interrupted_ingest_leaves_no_partial_table(tmp_path):
    root = tmp_path / "interrupt_root"
    reference_root = tmp_path / "interrupt_reference"

    resolved = load_config("ci")
    run_simulation(resolved, out_root=root)
    run_simulation(resolved, out_root=reference_root)

    script = f"""
import sys
sys.path.insert(0, {SRC_DIR!r})
from nextmove.ingest.__main__ import main
raise SystemExit(main(["--profile", "ci", "--out", {str(root)!r}]))
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    still_running = proc.poll() is None
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

    # Whether or not the kill actually landed mid-write (still_running records the attempt),
    # the destination path must never hold a truncated/corrupt file: either the file is
    # absent, or it is a fully valid, readable Parquet file.
    canonical_dir = root / "canonical"
    for name in ("events.parquet", "rejects.parquet"):
        candidate = canonical_dir / name
        if candidate.is_file():
            pq.read_table(candidate)  # raises pyarrow.lib.ArrowInvalid on a truncated file

    lineage_dir = root / "lineage"
    for tree in (canonical_dir, lineage_dir):
        if tree.exists():
            leftover_tmp = [p for p in tree.iterdir() if p.suffix == ".tmp" or ".tmp" in p.name]
            assert not leftover_tmp, f"leftover temp file(s) in {tree}: {leftover_tmp}"

    # A subsequent clean run completes and reproduces the expected digests.
    ingest_events(_raw_record_stream(root, VALIDATION_BATCH_SIZE), resolved, out_root=root)
    materialize_grid(resolved, out_root=root)
    ingest_events(
        _raw_record_stream(reference_root, VALIDATION_BATCH_SIZE), resolved, out_root=reference_root
    )
    materialize_grid(resolved, out_root=reference_root)

    assert _digests(root) == _digests(reference_root)
    assert set(_digests(root)) == EXPECTED_RELATIVE_FILES
    # Note: `still_running` is intentionally not asserted -- whether the kill landed mid-write
    # is a timing property of the host machine, not a correctness property of the pipeline.
    # The properties above (no truncated file, no leftover temp file, correct clean rerun)
    # hold regardless of exactly when the signal arrived.
    del still_running


# --------------------------------------------------------------------------------------
# Stage isolation: re-running one stage alone leaves the other stages' lineage fragments
# byte-unchanged (runtime counterpart to the static dvc.yaml overlap check).
# --------------------------------------------------------------------------------------


def test_rerunning_features_alone_leaves_other_lineage_fragments_unchanged(tmp_path):
    root = tmp_path / "stage_isolation"
    _run_pipeline_cli("ci", root)

    simulate_fragment = root / "lineage" / "simulate.parquet"
    ingest_fragment = root / "lineage" / "ingest.parquet"
    features_fragment = root / "lineage" / "features.parquet"

    before_simulate = _sha256_file(simulate_fragment)
    before_ingest = _sha256_file(ingest_fragment)
    before_features = _sha256_file(features_fragment)

    assert features_cli.main(["--profile", "ci", "--out", str(root)]) == 0

    assert _sha256_file(simulate_fragment) == before_simulate
    assert _sha256_file(ingest_fragment) == before_ingest
    assert _sha256_file(features_fragment) == before_features
