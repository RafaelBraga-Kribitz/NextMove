"""Structural correctness of `dvc.yaml` (plan 01-11, review HIGH-3 / HIGH-7 / MEDIUM-9).

Checked statically against the committed `dvc.yaml`: stage names match `Stage`'s three
members, no two stages' outs overlap, no stage depends on its own out, no lineage fragment is
any stage's dep, the two required producer -> consumer edges are present, no `persist` flag and
no `remote` appear anywhere, and every stage declares both `src/nextmove/storage` and
`src/nextmove/config` among its deps (MEDIUM-9 -- a change confined to either package must
invalidate every stage, not only `simulate`).

One test is a runtime proof rather than a static one: touching a file under
`src/nextmove/storage/` and asserting `dvc status` reports all three stages -- not only
`simulate` -- as having changed deps. It mutates and restores a real tracked source file and
re-runs the real pipeline to leave `dvc.lock` consistent afterward, so it is marked `slow` and
is not part of the default fast suite.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from nextmove.storage.paths import Stage

REPO_ROOT = Path(__file__).resolve().parents[2]
DVC_YAML = REPO_ROOT / "dvc.yaml"


def _load_dvc_yaml() -> dict:
    return yaml.safe_load(DVC_YAML.read_text())


def _normalize(path: str) -> str:
    return str(path).strip("/").replace("\\", "/")


def _is_equal_or_parent(candidate: str, other: str) -> bool:
    """True if `other` equals `candidate`, or `other` is a path under `candidate`."""
    c = _normalize(candidate)
    o = _normalize(other)
    return o == c or o.startswith(c + "/")


def _out_names(outs: list) -> list[str]:
    names = []
    for entry in outs:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict):
            names.extend(entry.keys())
    return names


def _stage_paths(data: dict) -> dict[str, dict[str, list[str]]]:
    return {
        name: {
            "deps": [_normalize(d) for d in stage.get("deps", [])],
            "outs": [_normalize(o) for o in _out_names(stage.get("outs", []))],
        }
        for name, stage in data["stages"].items()
    }


def test_stage_names_match_stage_enum():
    data = _load_dvc_yaml()
    assert set(data["stages"]) == {s.value for s in Stage}


def test_no_remote_declared():
    assert "remote" not in DVC_YAML.read_text()


def test_no_persist_flag():
    assert "persist" not in DVC_YAML.read_text()


def test_all_stages_depend_on_storage_and_config():
    stages = _stage_paths(_load_dvc_yaml())
    for name, info in stages.items():
        assert "src/nextmove/storage" in info["deps"], f"{name} is missing the storage dep"
        assert "src/nextmove/config" in info["deps"], f"{name} is missing the config dep"


def test_no_stage_output_overlap_and_required_producer_consumer_edges():
    stages = _stage_paths(_load_dvc_yaml())

    # (a) outs-vs-outs disjointness: no path is equal to or a parent of a path declared in a
    # *different* stage's outs.
    for name_a, info_a in stages.items():
        for out_a in info_a["outs"]:
            for name_b, info_b in stages.items():
                if name_a == name_b:
                    continue
                for out_b in info_b["outs"]:
                    assert not _is_equal_or_parent(out_a, out_b), (
                        f"{name_a}'s out {out_a!r} overlaps {name_b}'s out {out_b!r}"
                    )

    # (b) no stage declares in its own deps a path equal to or under one of its own outs.
    for name, info in stages.items():
        for dep in info["deps"]:
            for out in info["outs"]:
                assert not _is_equal_or_parent(out, dep), (
                    f"{name} depends on its own out {out!r} via dep {dep!r}"
                )

    # (c) no lineage fragment path appears in any stage's deps.
    for name, info in stages.items():
        for dep in info["deps"]:
            assert not dep.startswith("data/lineage"), f"{name} declares lineage dep {dep!r}"

    # (d) at least two producer -> consumer edges exist (positive requirement: forbidding these
    # would make every correct DVC DAG fail this check).
    edges = 0
    for name_a, info_a in stages.items():
        for out_a in info_a["outs"]:
            for name_b, info_b in stages.items():
                if name_a != name_b and out_a in info_b["deps"]:
                    edges += 1
    assert edges >= 2, "expected at least two producer->consumer edges in the declared DAG"
    assert "data/raw" in stages["simulate"]["outs"]
    assert "data/raw" in stages["ingest"]["deps"]
    assert "data/canonical" in stages["ingest"]["outs"]
    assert "data/canonical" in stages["features"]["deps"]


def _set_dvc_profile(profile: str) -> None:
    text = DVC_YAML.read_text()
    lines = [
        (f"  - profile: {profile}" if line.strip().startswith("- profile:") else line)
        for line in text.splitlines()
    ]
    DVC_YAML.write_text("\n".join(lines) + "\n")


@pytest.mark.slow
def test_storage_change_marks_all_three_stages_stale():
    """Runtime counterpart to the static dep-coverage check: touching
    `src/nextmove/storage/paths.py` must mark `simulate`, `ingest` *and* `features` stale, not
    only `simulate` -- proving the MEDIUM-9 deps actually do something, not merely that they are
    declared. Pins `dvc.yaml`'s profile var to `tiny` for the duration (this test must not run
    the `default`-profile pipeline), and restores both the profile var and the source file, then
    re-runs the real pipeline, in `finally` -- so this test leaves `dvc.yaml` and `dvc.lock`
    consistent with the working tree regardless of outcome.
    """
    target = REPO_ROOT / "src" / "nextmove" / "storage" / "paths.py"
    original_source = target.read_text()
    original_dvc_yaml = DVC_YAML.read_text()
    try:
        _set_dvc_profile("tiny")
        subprocess.run(
            ["uv", "run", "dvc", "repro", "simulate", "ingest", "features"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        target.write_text(
            original_source + "\n# test_storage_change_marks_all_three_stages_stale\n"
        )
        result = subprocess.run(
            ["uv", "run", "dvc", "status"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        for stage_name in ("simulate", "ingest", "features"):
            assert stage_name in output, (
                f"expected {stage_name!r} to be reported stale by `dvc status`; got:\n{output}"
            )
    finally:
        target.write_text(original_source)
        subprocess.run(
            ["uv", "run", "dvc", "repro", "simulate", "ingest", "features"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        DVC_YAML.write_text(original_dvc_yaml)
