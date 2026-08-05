"""The data-path counterpart to SIM-02's import ban: the import contract stops `nextmove.features`
importing simulator code; this stops it *reading* the simulator's ground-truth answers off disk,
even though nothing in the import graph would forbid the file access itself.

Two independent checks, per the plan's must-haves -- either alone could be evaded (a static-only
check misses a computed path built at runtime; a dynamic-only check misses code that is present
but never exercised by the one profile a test happens to run), so both are required together.

**Patch scope, deliberately narrow.** The zone-recording patch below wraps only the
`materialize_grid` call itself, never the `run_simulation`/`ingest_events` setup that produces
its input: the simulator legitimately writes `Zone.GROUND_TRUTH` tables (`customer_traits`,
`ground_truth_uplift`) as part of an ordinary run, and a patch active during setup would record
that zone and make the "ground truth is absent" assertion fail for a reason that has nothing to
do with the features stage.
"""

from __future__ import annotations

import ast
from contextlib import contextmanager
from pathlib import Path

import pytest

from nextmove.config.loader import load_config
from nextmove.features.compute import materialize_grid
from nextmove.ingest.__main__ import _raw_record_stream
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, ingest_events
from nextmove.simulator.run import run_simulation
from nextmove.storage import Zone

_GROUND_TRUTH_ZONE_NAME = "GROUND_TRUTH"
_GROUND_TRUTH_DIR_NAME = Zone.GROUND_TRUTH.value  # "ground_truth"


def _feature_module_paths() -> list[Path]:
    features_dir = Path(__file__).resolve().parents[2] / "src" / "nextmove" / "features"
    return sorted(features_dir.glob("*.py"))


class TestStaticImportAndLiteralBan:
    def test_no_feature_module_references_the_ground_truth_zone(self) -> None:
        violations: list[str] = []
        for path in _feature_module_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == _GROUND_TRUTH_ZONE_NAME:
                    violations.append(f"{path.name}: attribute access .{node.attr}")
                if isinstance(node, ast.Constant) and node.value == _GROUND_TRUTH_DIR_NAME:
                    violations.append(f"{path.name}: string literal {node.value!r}")
        assert violations == [], f"ground-truth zone referenced in feature modules: {violations}"


# ---------------------------------------------------------------------------------------
# Dynamic check: record every (name, zone) the path resolver is asked for during a real
# materialize_grid run, and assert the recorded zone set equals exactly the four zones the
# features stage legitimately touches -- an equality, not a bare absence check, so a future
# change that adds a new zone fails loudly here rather than silently passing.
# ---------------------------------------------------------------------------------------


@contextmanager
def _recording_resolve_table_path_patched():
    """Patch every module-local binding of `resolve_table_path` that `materialize_grid`'s call
    graph can reach -- `nextmove.features.compute` (the on-demand/grid entry points),
    `nextmove.storage.repository` (`write_table`/`write_table_from_parts`/`read_table` resolve
    their own destinations), and `nextmove.storage.lineage` (`record_lineage` resolves its
    fragment path) -- since a `from module import name` binding is a separate reference the
    origin module's own patch does not reach. Yields the shared `calls` list; restores every
    patched name on exit regardless of how the `with` block exits."""
    import nextmove.features.compute as compute_module
    import nextmove.storage.lineage as lineage_module
    import nextmove.storage.repository as repository_module
    from nextmove.storage.paths import resolve_table_path as real_resolve_table_path

    calls: list[tuple[str, Zone]] = []

    def _recording_resolve_table_path(name: str, zone: Zone, root=None):
        calls.append((name, zone))
        return real_resolve_table_path(name, zone, root)

    originals = {
        compute_module: compute_module.resolve_table_path,
        repository_module: repository_module.resolve_table_path,
        lineage_module: lineage_module.resolve_table_path,
    }
    for module in originals:
        module.resolve_table_path = _recording_resolve_table_path
    try:
        yield calls
    finally:
        for module, original in originals.items():
            module.resolve_table_path = original


@pytest.fixture(scope="module")
def ingested_tiny_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Simulate and ingest the `tiny` profile once, entirely unpatched, so every test in this
    module can reuse the same canonical `events` table without re-paying setup cost -- and,
    more importantly, without the zone-recording patch ever being active while the simulator
    legitimately writes `Zone.GROUND_TRUTH`."""
    out_root = tmp_path_factory.mktemp("ground_truth_isolation")
    resolved = load_config("tiny")
    run_simulation(resolved, out_root=out_root)
    ingest_events(_raw_record_stream(out_root, VALIDATION_BATCH_SIZE), resolved, out_root=out_root)
    return out_root


class TestDynamicPathResolution:
    def test_materialize_grid_never_resolves_a_path_in_a_zone_outside_the_declared_four(
        self, ingested_tiny_root: Path
    ) -> None:
        resolved = load_config("tiny")
        with _recording_resolve_table_path_patched() as calls:
            materialize_grid(resolved, out_root=ingested_tiny_root)

        recorded_zones = {zone for _name, zone in calls}
        assert recorded_zones == {Zone.CANONICAL, Zone.RAW, Zone.FEATURES, Zone.LINEAGE}, (
            f"materialize_grid resolved zone(s) {recorded_zones}, expected exactly "
            "{Zone.CANONICAL, Zone.RAW, Zone.FEATURES, Zone.LINEAGE} -- a newly-added zone (or "
            "Zone.GROUND_TRUTH specifically) must be investigated, not silently accepted"
        )
        assert Zone.GROUND_TRUTH not in recorded_zones

    def test_the_only_lineage_path_resolved_is_the_features_fragment(
        self, ingested_tiny_root: Path
    ) -> None:
        resolved = load_config("tiny")
        with _recording_resolve_table_path_patched() as calls:
            materialize_grid(resolved, out_root=ingested_tiny_root)

        lineage_names = {name for name, zone in calls if zone is Zone.LINEAGE}
        assert lineage_names == {"features"}, (
            f"the features stage resolved lineage fragment(s) {lineage_names}, expected only "
            "'features' -- it must neither read nor write another stage's fragment"
        )


class TestGroundTruthDirNameConstant:
    def test_ground_truth_zone_dir_name_is_ground_truth(self) -> None:
        # Sanity pin: if paths.py's Zone.GROUND_TRUTH value ever changes, this suite's static
        # string-literal check above must be checking the *current* value, not a stale one.
        assert _GROUND_TRUTH_DIR_NAME == "ground_truth"
