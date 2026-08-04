"""Machine proof that the import-linter contracts (SIM-02, ENG-01) have teeth.

RESEARCH Pitfall 4 documents the failure mode this file guards against: a `forbidden`
contract that exits 0 not because the codebase is clean but because its source packages
were never real importable modules, so the contract silently checks nothing. Two
independent countermeasures live here:

1. `test_probe_contract_goes_red_on_a_known_violation` proves a forbidden contract of the
   exact shape used in production (`pyproject.toml` contract one) is capable of failing
   against a genuine violation, using a permanent fixture package that lives outside
   `src/nextmove/` so this test can never mutate production source.
2. `test_production_contract_is_non_vacuous` proves the *production* contract, run against
   the real repository, names all four forbidden source packages in its report rather than
   only returning exit code 0 — asserting on the exit code alone is exactly the Pitfall 4
   trap.

A third test (`test_no_forbidden_source_package_imports_pyarrow_or_duckdb`) gives a fast,
readable, file-and-line failure message for the storage boundary contract (ENG-01),
complementary to contract two's coarser pass/fail report.
"""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# The four packages SIM-02 forbids from importing nextmove.simulator.
FORBIDDEN_SOURCE_PACKAGES = (
    "nextmove.models",
    "nextmove.decisions",
    "nextmove.policies",
    "nextmove.features",
)

# The external I/O libraries ENG-01 confines to nextmove.storage.
FORBIDDEN_STORAGE_LIBRARIES = ("pyarrow", "duckdb")


def _lint_imports_executable() -> str:
    """Locate the `lint-imports` console script in the active (uv-managed) venv.

    There is no `python -m importlinter` entry point, so the console script must be
    resolved directly. `shutil.which` finds it via the venv's Scripts/bin directory,
    which is on PATH inside a `uv run` invocation; falling back to a path built from
    `sys.executable` covers interpreters invoked without that PATH entry.
    """
    found = shutil.which("lint-imports")
    if found:
        return found
    venv_bin = Path(sys.executable).parent
    candidate = venv_bin / ("lint-imports.exe" if os.name == "nt" else "lint-imports")
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError("could not locate the lint-imports console script")


@pytest.mark.slow
def test_probe_contract_goes_red_on_a_known_violation(repo_root: Path) -> None:
    """A forbidden contract shaped like production contract one must fail against a real
    violation. `probepkg.models` imports `probepkg.simulator` at module level (the
    deliberate violation); `lint-imports` run against the probe config must exit non-zero
    and the combined output must name both `probepkg.models` and `probepkg.simulator`,
    proving the contract shape is not vacuous — it can actually go red.
    """
    fixture_dir = repo_root / "tests" / "fixtures" / "contract_probe"
    config_path = fixture_dir / "setup.cfg"
    assert config_path.is_file()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(fixture_dir)
    result = subprocess.run(
        [_lint_imports_executable(), "--config", str(config_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode != 0, (
        f"probe contract must go red on a known violation; got exit "
        f"{result.returncode}\n{combined_output}"
    )
    assert "probepkg.models" in combined_output
    assert "probepkg.simulator" in combined_output


@pytest.mark.slow
def test_production_contract_is_non_vacuous(repo_root: Path) -> None:
    """The production contract must exit 0 AND its report must name all four forbidden
    source packages. Asserting only the exit code is precisely the Pitfall 4 trap: a
    contract whose source packages resolved to nothing would also exit 0.
    """
    result = subprocess.run(
        [_lint_imports_executable(), "--verbose"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"production import-linter contracts must pass on a clean tree; got exit "
        f"{result.returncode}\n{combined_output}"
    )
    for package in FORBIDDEN_SOURCE_PACKAGES:
        assert package in combined_output, (
            f"expected {package!r} to be named in lint-imports output "
            f"(non-vacuity proof); it was not found"
        )


def test_no_forbidden_source_package_imports_pyarrow_or_duckdb(repo_root: Path) -> None:
    """Walk every .py file under src/nextmove/ (excluding storage/) and assert none of
    them import pyarrow or duckdb directly. Complementary to contract two's coarser
    report: this gives a file-and-line failure message.
    """
    src_root = repo_root / "src" / "nextmove"
    storage_root = src_root / "storage"
    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        if storage_root in py_file.parents:
            continue
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_STORAGE_LIBRARIES:
                        violations.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    root = node.module.split(".")[0]
                    if root in FORBIDDEN_STORAGE_LIBRARIES:
                        location = f"{py_file.relative_to(repo_root)}:{node.lineno}"
                        violations.append(f"{location}: from {node.module} import ...")

    assert not violations, (
        "forbidden pyarrow/duckdb import(s) outside nextmove.storage:\n" + "\n".join(violations)
    )
