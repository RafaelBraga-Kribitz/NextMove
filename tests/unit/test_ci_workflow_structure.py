"""Static structure of `.github/workflows/ci.yml` (plan 01-11, review HIGH-10).

Checked here rather than left to eyeballing the YAML: the miniature end-to-end and golden
steps this plan adds exist and run after the pre-existing steps, the pre-existing lint/import/
pytest steps are untouched, and the memory-budget step exists, runs the `demo` profile, and is
not `continue-on-error` -- the property that keeps the RSS gate from vanishing by permanent
skip on this runner (D-16 makes Linux CI the enforcing platform for ENG-08).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci() -> dict:
    return yaml.safe_load(CI_YAML.read_text())


def _steps() -> list[dict]:
    data = _load_ci()
    return data["jobs"]["checks"]["steps"]


def test_no_continue_on_error_anywhere():
    assert CI_YAML.read_text().count("continue-on-error") == 0


def test_preexisting_steps_unchanged():
    steps = _steps()
    runs = [s.get("run", "") for s in steps]
    assert any(r.strip() == "uv run ruff check ." for r in runs)
    assert any(r.strip() == "uv run ruff format --check ." for r in runs)
    assert any(r.strip() == "uv run lint-imports" for r in runs)
    assert any(r.strip() == "uv run pytest -q" for r in runs)


def test_end_to_end_and_golden_steps_present_after_test_suite():
    steps = _steps()
    names_or_runs = [s.get("run", "") for s in steps]

    pytest_index = next(i for i, r in enumerate(names_or_runs) if r.strip() == "uv run pytest -q")
    e2e_index = next(i for i, r in enumerate(names_or_runs) if "just reproduce" in r and "ci" in r)
    golden_index = next(
        i
        for i, r in enumerate(names_or_runs)
        if "pytest" in r and "tests/golden" in r and "-m slow" in r
    )
    assert e2e_index > pytest_index
    assert golden_index > pytest_index


def test_memory_budget_step_exists_runs_demo_profile_and_is_not_continue_on_error():
    steps = _steps()
    budget_steps = [
        s
        for s in steps
        if "test_simulation_budget.py" in s.get("run", "")
        and "test_ingest_budget.py" in s.get("run", "")
        and "test_features_budget.py" in s.get("run", "")
    ]
    assert budget_steps, "expected a step running all three budget suites"
    step = budget_steps[0]
    assert "continue-on-error" not in step
    assert "NEXTMOVE_BUDGET_PROFILE=demo" in step["run"]
    assert "NEXTMOVE_RUN_DEFAULT_BUDGET=1" in step["run"]
    assert "skipped" in step["run"]
