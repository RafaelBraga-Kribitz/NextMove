"""Static structure of `.github/workflows/ci.yml` (plan 01-11, review HIGH-10; gap closure
G-01-2, plan 01-13).

Checked here rather than left to eyeballing the YAML: the miniature end-to-end and golden
steps this workflow adds exist and run after the pre-existing steps, the pre-existing lint/
import steps are untouched, the general test-suite step excludes the dedicated `peak_rss`
marker, and the peak-RSS step selects exactly the tests that carry that marker, captures
pytest's exit status rather than letting the shell abort before its gates, and cannot pass
while any selected assertion is skipped or the selected count drifts from what this file
expects -- the two stacked bugs diagnosed in `.planning/debug/ci-budget-marker-mismatch.md`
that let `-m slow` silently collect one unrelated test for five plans running.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
#: Lowercase because that is the name git actually tracks. Spelling it `Justfile` resolves
#: anyway on the case-insensitive Windows dev machine (`core.ignorecase=true`) and then raises
#: FileNotFoundError on the Linux runner -- the same Windows-passes/Linux-fails asymmetry the
#: path-separator normalization in `_collected_peak_rss_node_ids` below guards against.
JUSTFILE = REPO_ROOT / "justfile"

#: The six peak-process-RSS assertions across the three budget files that must carry the
#: `peak_rss` marker -- the exact set named in plan 01-13's interface_context, written with
#: forward slashes. A drift between this set and what `-m peak_rss` actually collects (either
#: direction) is caught by `test_peak_rss_marker_selects_exactly_the_intended_assertions`
#: below, on the Windows dev machine, before CI ever runs.
EXPECTED_PEAK_RSS_TESTS: frozenset[str] = frozenset(
    {
        "tests/integration/test_simulation_budget.py::TestPeakResidentMemory::"
        "test_demo_subprocess_peak_rss_under_budget",
        "tests/integration/test_simulation_budget.py::TestScaleInvariantGrowth::"
        "test_peak_rss_grows_less_than_customer_count_ratio",
        "tests/integration/test_ingest_budget.py::TestPeakResidentMemory::"
        "test_demo_subprocess_peak_rss_under_budget",
        "tests/integration/test_ingest_budget.py::TestScaleInvariantGrowth::"
        "test_peak_rss_grows_no_faster_than_the_batch_fill_ratio",
        "tests/integration/test_features_budget.py::TestPeakResidentMemory::"
        "test_demo_subprocess_peak_rss_under_budget",
        "tests/integration/test_features_budget.py::TestScaleInvariantGrowth::"
        "test_peak_rss_grows_less_than_customer_count_ratio",
    }
)


def _load_ci() -> dict:
    return yaml.safe_load(CI_YAML.read_text())


def _steps() -> list[dict]:
    data = _load_ci()
    return data["jobs"]["checks"]["steps"]


def _peak_rss_step() -> dict:
    return next(s for s in _steps() if "-m peak_rss" in s.get("run", ""))


def _justfile_recipe_body(name: str) -> str:
    """The indented body lines of a Justfile recipe named `name` (no arguments), e.g.
    `budget-rss`. Matches the exact `"{name}:"` header line so `budget` does not also match
    `budget-rss`."""
    lines = JUSTFILE.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"{name}:")
    body_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith(" ") or line.startswith("\t"):
            body_lines.append(line)
        else:
            break
    return "\n".join(body_lines)


def _collected_peak_rss_node_ids() -> frozenset[str]:
    """Runs pytest's own collector against the live `peak_rss` marker and returns exactly the
    node ids it selects. Collection imports the test modules but executes no fixture, so this
    costs seconds, not minutes.

    Deliberately passes no explicit `-q`: this repo's `pyproject.toml` already sets
    `addopts = "-q --strict-markers"`, and pytest 9.1's `--collect-only` switches from a
    one-node-id-per-line listing to a per-file count summary (no `::` in it at all) once
    verbosity is lowered a second time by a second `-q`. A single, addopts-supplied `-q` is
    the quietest level that still lists individual node ids -- the same reason the CI step and
    `just budget-rss` also carry no explicit `-q` of their own.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-m", "peak_rss"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"pytest --collect-only -m peak_rss exited {result.returncode}:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    # pytest emits OS-native path separators; normalize so this suite passes on both the
    # Windows dev machine and Linux CI.
    node_ids = (
        line.strip().replace("\\", "/") for line in result.stdout.splitlines() if "::" in line
    )
    return frozenset(node_ids)


def test_no_continue_on_error_anywhere():
    assert CI_YAML.read_text().count("continue-on-error") == 0


def test_preexisting_lint_and_import_steps_unchanged():
    steps = _steps()
    runs = [s.get("run", "") for s in steps]
    assert any(r.strip() == "uv run ruff check ." for r in runs)
    assert any(r.strip() == "uv run ruff format --check ." for r in runs)
    assert any(r.strip() == "uv run lint-imports" for r in runs)
    assert any(r.strip() == 'uv run pytest -q -m "not peak_rss"' for r in runs)


def test_end_to_end_and_golden_steps_present_after_test_suite():
    steps = _steps()
    names_or_runs = [s.get("run", "") for s in steps]

    pytest_index = next(
        i for i, r in enumerate(names_or_runs) if r.strip() == 'uv run pytest -q -m "not peak_rss"'
    )
    e2e_index = next(i for i, r in enumerate(names_or_runs) if "just reproduce" in r and "ci" in r)
    golden_index = next(
        i
        for i, r in enumerate(names_or_runs)
        if "pytest" in r and "tests/golden" in r and "-m slow" in r
    )
    assert e2e_index > pytest_index
    assert golden_index > pytest_index


def test_general_test_suite_step_excludes_peak_rss():
    steps = _steps()
    runs = [s.get("run", "") for s in steps]
    assert any(r.strip() == 'uv run pytest -q -m "not peak_rss"' for r in runs)


def test_peak_rss_marker_selects_exactly_the_intended_assertions():
    collected = _collected_peak_rss_node_ids()
    missing = EXPECTED_PEAK_RSS_TESTS - collected
    extra = collected - EXPECTED_PEAK_RSS_TESTS
    assert collected == EXPECTED_PEAK_RSS_TESTS, (
        "the peak_rss marker selection drifted from the expected set -- "
        f"missing (marker dropped from a test the CI gate depends on): {sorted(missing)}; "
        f"extra (a new RSS assertion needs adding to EXPECTED_PEAK_RSS_TESTS and to the CI "
        f"step's expected count): {sorted(extra)}"
    )


def test_peak_rss_step_selects_the_marker_and_names_the_expected_count():
    step = _peak_rss_step()
    run = step["run"]
    assert "test_simulation_budget.py" in run
    assert "test_ingest_budget.py" in run
    assert "test_features_budget.py" in run
    assert f"{len(EXPECTED_PEAK_RSS_TESTS)} passed" in run
    assert "skipped" in run
    assert "::error::" in run
    assert "continue-on-error" not in step


def test_peak_rss_step_evaluates_its_gates_even_when_pytest_fails():
    step = _peak_rss_step()
    run = step["run"]
    assert "|| status=$?" in run
    assert "exit $status" in run
    status_capture_index = run.index("|| status=$?")
    first_grep_index = run.index("grep")
    assert first_grep_index > status_capture_index, (
        "the gates must be downstream of a captured, non-fatal exit code, not upstream of it"
    )


def test_local_and_ci_peak_rss_selections_agree():
    ci_run = _peak_rss_step()["run"]
    budget_rss_body = _justfile_recipe_body("budget-rss")

    assert "-m peak_rss" in budget_rss_body
    for path in (
        "tests/integration/test_simulation_budget.py",
        "tests/integration/test_ingest_budget.py",
        "tests/integration/test_features_budget.py",
    ):
        assert path in ci_run
        assert path in budget_rss_body

    justfile_text = JUSTFILE.read_text()
    assert "slow or peak_rss" in justfile_text
