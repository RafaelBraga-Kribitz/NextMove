"""End-to-end proof that a YAML edit changes pipeline output with no code edit (phase success
criterion 5's second half, ENG-03). Runs the `tiny` profile end to end as a baseline, then
mutates exactly one YAML value at a time into a temporary config tree and re-runs, asserting
both the output digest and the config hash change -- and that no file under `src/` was touched
in the process, so the "no code edit" half of the claim is checked, not merely asserted in
prose.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from nextmove.config.loader import load_config
from nextmove.features.compute import materialize_grid
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, ingest_events
from nextmove.simulator.run import run_simulation
from nextmove.storage import Zone, connect, resolve_table_path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_config_tree(dest: Path) -> Path:
    shutil.copytree(CONFIG_DIR, dest)
    return dest


def _mutate_yaml_file(path: Path, mutate) -> None:
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _raw_record_stream(out_root: Path, batch_size: int):
    import json as _json

    events_path = resolve_table_path("events_raw", Zone.RAW, root=out_root)
    con = connect(root=out_root)
    try:
        result = con.execute(f"SELECT * FROM read_parquet({str(events_path)!r})")
        reader = result.to_arrow_reader(batch_size)
        for record_batch in reader:
            for row in record_batch.to_pylist():
                row = dict(row)
                row["payload"] = _json.loads(row["payload"])
                yield row
    finally:
        con.close()


def _run_pipeline(resolved, out_root: Path) -> None:
    run_simulation(resolved, out_root=out_root)
    ingest_events(_raw_record_stream(out_root, VALIDATION_BATCH_SIZE), resolved, out_root=out_root)
    materialize_grid(resolved, out_root=out_root)


def _feature_grid_digest(root: Path) -> str:
    return _sha256_file(root / "features" / "feature_grid.parquet")


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    root = tmp_path_factory.mktemp("baseline")
    resolved = load_config("tiny")
    _run_pipeline(resolved, root)
    return resolved.config_hash, _feature_grid_digest(root)


def _mutate_seasonality(data: dict) -> None:
    multipliers = data["simulator"]["seasonality"]["monthly_multipliers"]
    multipliers[11] = 0.5 if multipliers[11] != 0.5 else 0.4


def _mutate_trait_parameter(data: dict) -> None:
    params = data["simulator"]["latent_traits"]["price_sensitivity"]["params"]
    params["alpha"] = 9.0 if params["alpha"] != 9.0 else 8.5


def _mutate_feature_list_entry(data: dict) -> None:
    entry = data["features"]["features"][1]
    assert entry["name"] == "rfm_frequency"
    entry["params"]["window_days"] = 30 if entry["params"]["window_days"] != 30 else 45


_SCENARIOS = [
    ("seasonality_multiplier", "simulator.yaml", _mutate_seasonality),
    ("trait_parameter", "simulator.yaml", _mutate_trait_parameter),
    ("feature_list_entry", "features.yaml", _mutate_feature_list_entry),
]


@pytest.mark.parametrize("name,domain_file,mutate", _SCENARIOS, ids=[s[0] for s in _SCENARIOS])
def test_yaml_edit_changes_output_digest_and_config_hash(
    tmp_path, baseline, name, domain_file, mutate
):
    baseline_hash, baseline_digest = baseline

    config_dir = _copy_config_tree(tmp_path / f"cfg_{name}")
    _mutate_yaml_file(config_dir / domain_file, mutate)

    resolved = load_config("tiny", config_dir=config_dir)
    root = tmp_path / f"out_{name}"
    _run_pipeline(resolved, root)

    assert resolved.config_hash != baseline_hash, f"{name}: config hash did not change"
    assert _feature_grid_digest(root) != baseline_digest, f"{name}: output digest did not change"


def test_no_source_file_modified_by_this_suite():
    result = subprocess.run(
        ["git", "status", "--porcelain", "src"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "", f"src/ was modified: {result.stdout}"
