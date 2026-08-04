"""Package inventory + importability assertions for src/nextmove/.

Guards ENG-01 (exactly the eleven named packages) and RESEARCH Pitfall 4 (every package
must be a real importable module, not an empty stub directory, or import-linter's
forbidden-import contract passes vacuously).
"""

import importlib
from pathlib import Path

# The eleven ENG-01 modular-monolith packages.
ENG_01_PACKAGES = {
    "simulator",
    "ingest",
    "features",
    "segmentation",
    "models",
    "rules",
    "decisions",
    "policies",
    "explain",
    "evaluate",
    "api",
}

# Cross-cutting infrastructure packages that sit below all eleven in the import graph.
INFRASTRUCTURE_PACKAGES = {"config", "storage"}

ALL_EXPECTED_PACKAGES = ENG_01_PACKAGES | INFRASTRUCTURE_PACKAGES


def _discovered_package_dirs(repo_root: Path) -> set[str]:
    src_nextmove = repo_root / "src" / "nextmove"
    return {
        child.name
        for child in src_nextmove.iterdir()
        if child.is_dir() and (child / "__init__.py").is_file()
    }


def test_package_inventory_is_exactly_thirteen(repo_root: Path) -> None:
    """The set of package directories under src/nextmove/ equals exactly the eleven
    ENG-01 packages plus the two infrastructure packages — thirteen total.

    Compared with `==` (not a subset check) so both an addition and a removal fail.
    """
    discovered = _discovered_package_dirs(repo_root)
    assert discovered == ALL_EXPECTED_PACKAGES
    assert len(ALL_EXPECTED_PACKAGES) == 13


def test_every_package_is_importable() -> None:
    """Every one of the thirteen packages must import cleanly in a fresh interpreter."""
    for package_name in sorted(ALL_EXPECTED_PACKAGES):
        module = importlib.import_module(f"nextmove.{package_name}")
        assert module is not None


def test_every_eng01_package_has_a_docstring() -> None:
    """Each of the eleven ENG-01 packages carries a non-empty module docstring stating
    its responsibility (and, for stubs, which phase populates it).
    """
    for package_name in sorted(ENG_01_PACKAGES):
        module = importlib.import_module(f"nextmove.{package_name}")
        assert module.__doc__ is not None
        assert module.__doc__.strip() != ""
