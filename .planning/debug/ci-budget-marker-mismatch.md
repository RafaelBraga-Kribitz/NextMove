---
status: investigating
trigger: "UAT gap: Linux CI 'Memory budget suite' step (test 2 in 01-UAT.md) does not execute
  peak-process-RSS assertions and reports numbers under budget. Run
  https://github.com/RafaelBraga-Kribitz/NextMove/actions/runs/31015357302 -- Memory budget
  suite step: marker mismatch collects 1 test instead of 3, and that 1 test fails on wall-clock
  (638.4s > 600.0s) before ever reaching a peak-RSS assertion."
created: 2026-08-05T00:00:00Z
updated: 2026-08-05T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED (two independent, stacked bugs -- see Resolution)
test: Direct read of .github/workflows/ci.yml, all three budget test files, conftest.py,
  Justfile, pyproject.toml pytest markers config, and plan 01-11's own action text.
expecting: n/a -- goal is find_root_cause_only, diagnosis complete
next_action: Return ROOT CAUSE FOUND to caller (no fix -- diagnose-only mode)

## Symptoms

expected: |
  Configure a git remote for this repository and let `.github/workflows/ci.yml` run on Linux --
  in particular the "Memory budget suite" step, which fails the job if any peak-RSS assertion
  is skipped. The peak-process-RSS assertions in tests/integration/test_simulation_budget.py,
  test_ingest_budget.py and test_features_budget.py must execute and report numbers under their
  stated budgets.
actual: |
  Real CI run https://github.com/RafaelBraga-Kribitz/NextMove/actions/runs/31015357302 (Linux,
  ubuntu-latest). "Test suite" and "ci reproduce / golden" steps passed. "Memory budget suite"
  step has two stacked problems: (1) `-m slow` deselects all three
  `test_demo_subprocess_peak_rss_under_budget` tests (none carry `@pytest.mark.slow`), collecting
  only 1 unrelated test; (2) that 1 test fails on a wall-clock assertion (638.4s > 600.0s budget)
  before it ever reaches its own internal peak-RSS measurement, and the step's shell semantics
  cause its own skip-detection grep gate to never run either.
errors: |
  [demo budget] wall_clock=638.4s (budget 600.0s), peak_traced_heap=183.8MB (budget 512.0MB)
  AssertionError: demo wall clock 638.4s exceeds budget
reproduction: |
  Test 2 in .planning/phases/01-reproducible-world/01-UAT.md. CI run:
  https://github.com/RafaelBraga-Kribitz/NextMove/actions/runs/31015357302, "Memory budget
  suite" step. Locally equivalent to Justfile's `budget` recipe (CI itself passes
  NEXTMOVE_BUDGET_PROFILE=demo, not default):
    NEXTMOVE_RUN_DEFAULT_BUDGET=1 NEXTMOVE_BUDGET_PROFILE=demo uv run pytest \
      tests/integration/test_simulation_budget.py tests/integration/test_ingest_budget.py \
      tests/integration/test_features_budget.py -m slow -q
started: "Always broken -- no plan among 01-06/01-08/01-09/01-10/01-11 had ever actually
  executed this CI step before this session, since the repo had no git remote until now."

## Eliminated

(none -- both hypotheses tested were confirmed true on first read, not eliminated)

## Evidence

- timestamp: investigation-start
  checked: .github/workflows/ci.yml "Memory budget suite" step (lines 55-66)
  found: |
    Step invokes:
      NEXTMOVE_RUN_DEFAULT_BUDGET=1 NEXTMOVE_BUDGET_PROFILE=demo uv run pytest \
        tests/integration/test_simulation_budget.py \
        tests/integration/test_ingest_budget.py \
        tests/integration/test_features_budget.py \
        -m slow -rs -q | tee budget-output.txt
      if grep -Eq '[1-9][0-9]* skipped' budget-output.txt; then ...; exit 1; fi
    Only `set -o pipefail` is explicit; the step has no `shell:` override, so GitHub Actions'
    default Linux bash shell (`bash --noprofile --norc -eo pipefail {0}`) is already in effect,
    meaning `-e` is active for the whole script block.
  implication: If the piped pytest command exits non-zero, `set -e` aborts the script
    immediately -- the subsequent `if grep ...` skip-gate line never executes on that path.

- timestamp: investigation-continued
  checked: "grep for `pytest.mark.slow` and `def test_demo_subprocess_peak_rss_under_budget`
    across tests/integration/*.py"
  found: |
    test_simulation_budget.py:129   def test_demo_subprocess_peak_rss_under_budget(   [NOT marked slow]
    test_simulation_budget.py:427   @pytest.mark.slow                                  [only slow marker in file]
    test_simulation_budget.py:428   def test_default_profile_completes_within_its_stated_budget(
    test_ingest_budget.py:178       def test_demo_subprocess_peak_rss_under_budget(    [NOT marked slow]
    test_ingest_budget.py                                                              [zero @pytest.mark.slow in whole file]
    test_features_budget.py:197     def test_demo_subprocess_peak_rss_under_budget(    [NOT marked slow]
    test_features_budget.py                                                            [zero @pytest.mark.slow in whole file]
  implication: Across all three files, exactly ONE test carries `@pytest.mark.slow`:
    `test_default_profile_completes_within_its_stated_budget` in test_simulation_budget.py. The
    three named peak-RSS tests the UAT item names are entirely unmarked. `-m slow` therefore
    collects exactly 1 test for the whole step, not the intended 3 (or more).

- timestamp: investigation-continued
  checked: Full read of tests/integration/test_simulation_budget.py lines 421-462 (the one
    test `-m slow` actually collects)
  found: |
    @pytest.mark.slow
    def test_default_profile_completes_within_its_stated_budget(tmp_path):
        if os.environ.get("NEXTMOVE_RUN_DEFAULT_BUDGET") != "1": pytest.skip(...)
        profile = os.environ.get("NEXTMOVE_BUDGET_PROFILE", "default")
        max_heap_mb, max_rss_mb, max_wall_clock_s = _PROFILE_BUDGETS[profile]
        ...
        run_simulation(...)                                    # wall clock measured
        assert elapsed < max_wall_clock_s, ...                 # <- fails here first
        assert peak_heap_mb < max_heap_mb, ...
        rss_result = measure_subprocess_peak_rss(profile, ...)  # <- peak RSS only measured here
        if rss_result.peak_rss_bytes is None: pytest.skip(...)
        assert peak_rss_mb < max_rss_mb, ...
    _PROFILE_BUDGETS["demo"] = (512.0, 1536.0, 600.0)  # (heap_mb, rss_mb, wall_clock_s)
  implication: With CI's NEXTMOVE_BUDGET_PROFILE=demo, this test's own wall-clock budget is
    600.0s. Assertion order checks wall-clock BEFORE peak RSS. Actual CI run measured
    638.4s > 600.0s -> AssertionError raised at the wall-clock line, so `measure_subprocess_peak_rss`
    (and thus any peak-RSS assertion) is never reached in this run. This exactly reproduces the
    reported error text.

- timestamp: investigation-continued
  checked: tests/integration/conftest.py (session-scoped fixtures `demo_run_result`,
    `demo_subprocess_rss`, `measure_subprocess_peak_rss`)
  found: Neither `demo_run_result` nor `demo_subprocess_rss` fixtures are gated behind
    `NEXTMOVE_RUN_DEFAULT_BUDGET` or any other env var/marker -- they run unconditionally
    whenever a requesting test is collected. `test_demo_subprocess_peak_rss_under_budget` in
    each of the three files requests `demo_subprocess_rss` directly and is unmarked, so it is
    collected (and executes a full subprocess run) in a *plain* `pytest -q` invocation with no
    `-m` filter at all.
  implication: Confirms the symptom's side note -- the separate unfiltered "Test suite" CI step
    (`uv run pytest -q`, no `-m` filter) DOES exercise these three peak-RSS tests on Linux
    (explains its ~35 min runtime and 1 skip), but that step prints no budget numbers and has no
    skip-enforcing gate, so it does not satisfy the UAT item's requirement on its own.

- timestamp: investigation-continued
  checked: pyproject.toml pytest config; Justfile `budget` recipe (line 58-59)
  found: |
    pyproject.toml: addopts = "-q --strict-markers"; markers = ["slow: marks tests as slow", ...]
    Justfile: budget profile="default":
      NEXTMOVE_RUN_DEFAULT_BUDGET=1 NEXTMOVE_BUDGET_PROFILE={{profile}} uv run pytest \
        tests/integration/test_simulation_budget.py tests/integration/test_ingest_budget.py \
        tests/integration/test_features_budget.py -m slow -q
  implication: The Justfile's local `just budget` recipe has the exact same `-m slow` filter as
    CI's step -- this is not a CI-only misconfiguration, it is the shared, intended local/CI
    reproduction command, and it has the identical marker-mismatch bug locally too. `--strict-markers`
    confirms `slow` is a real registered marker (not a typo'd/unregistered one silently no-op'ing).

- timestamp: investigation-continued
  checked: .planning/phases/01-reproducible-world/01-11-PLAN.md lines 375-393 (the plan that
    wrote the CI "Memory budget suite" step) and 01-11-SUMMARY.md
  found: Plan 01-11's action text says to add "a memory-budget step running the three budget
    suites on the demo profile with -rs so skips are reported, then failing the job if any
    peak-RSS assertion was skipped" -- it assumes `-m slow` will select the peak-RSS tests
    written by earlier plans 01-08/01-09/01-10, but neither 01-11 nor the earlier plans ever
    added `@pytest.mark.slow` to those tests, and 01-11's own verification/acceptance criteria
    never actually run this new CI step (self-skips on the Windows dev machine, per
    conftest.py's `measure_subprocess_peak_rss` and STATE.md's own recorded blocker). The gap
    was structural (cross-plan coordination), not caught because the step was never executable
    locally to any of the 5 plans that touched it (01-06/01-08/01-09/01-10/01-11).
  implication: Root cause of the marker-mismatch bug is a cross-plan coordination gap: the plan
    that wrote the `-m slow` filter (01-11) never verified the tests it intended to select
    actually carried that marker, and no plan's own verification loop could catch it because the
    step it introduced was structurally unrunnable on the only dev machine available (Windows;
    `resource` module POSIX-only) until this session's first real Linux CI run.

## Resolution

root_cause: |
  TWO independent, stacked bugs in the "Memory budget suite" CI step (and its local `just budget`
  equivalent), not one bug in two guises:

  BUG A -- marker-tagging omission (structural/coordination gap): The CI step (and Justfile
  `budget` recipe) filters with `-m slow`, but of all tests in test_simulation_budget.py,
  test_ingest_budget.py and test_features_budget.py, only ONE test anywhere carries
  `@pytest.mark.slow`: `test_default_profile_completes_within_its_stated_budget` in
  test_simulation_budget.py. The three tests the UAT item actually names --
  `test_demo_subprocess_peak_rss_under_budget` in each of the three files -- were written by
  plans 01-08/01-09/01-10 with no `slow` marker at all (they run unconditionally in the plain,
  unfiltered `pytest -q` step instead). Plan 01-11 wrote the `-m slow`-filtered CI step assuming
  it would select these tests, but never added the marker to them, and could not catch the gap
  because the step was unrunnable on the Windows dev machine used by all 5 contributing plans.
  Net effect: `-m slow` collects exactly 1 test for this step, not the intended 3+.

  BUG B -- wall-clock budget too tight for this test path on CI hardware: The 1 test `-m slow`
  does collect is a generic, on-demand "run any profile end-to-end and check wall-clock + heap +
  RSS" test, originally designed for manual `just budget` runs at the `default` (50k-customer)
  profile. CI overrides it to the `demo` profile (`NEXTMOVE_BUDGET_PROFILE=demo`), whose stated
  wall-clock budget is 600.0s (`_PROFILE_BUDGETS["demo"]` in test_simulation_budget.py). The
  actual CI run took 638.4s -- a ~6% overrun, plausibly CI-hardware slowness relative to
  whatever machine calibrated 600.0s, or simply a budget set too tight with no margin. Because
  this test's assertion order checks wall-clock before peak RSS, the AssertionError fires before
  `measure_subprocess_peak_rss()` is ever called, so peak RSS is never measured in this failure.
  This is independent of Bug A: fixing only the marker (making the three real RSS tests
  collectible) would still leave this same wall-clock-bound test running and still likely
  failing on the same demo-profile/600s budget, since it stays part of the invoked file set and
  stays marked slow.

  SECONDARY FINDING (masking effect, not a separate root cause): The CI step's own
  "fail if any peak-RSS assertion was skipped" grep gate (`if grep -Eq '[1-9][0-9]* skipped' ...`)
  never actually evaluates on this failure path. GitHub Actions' default Linux `run:` shell is
  `bash -eo pipefail` and the step adds an explicit `set -o pipefail` on top; when the piped
  `pytest ... | tee budget-output.txt` command exits non-zero (pytest's own exit code, preserved
  through the pipe by pipefail), `-e` aborts the script immediately, before the subsequent `if
  grep ...` line runs. So the step currently fails with pytest's own AssertionError output, not
  with the step's custom "::error:: A peak-RSS assertion was skipped" message -- the skip-gate
  logic itself remains unverified/unexercised by this run, and would only ever fire on a run
  where pytest exits 0 with a skip present, not one where pytest itself fails first.

fix: [empty -- goal is find_root_cause_only, no fix applied]
verification: [empty -- goal is find_root_cause_only]
files_changed: []
</content>
