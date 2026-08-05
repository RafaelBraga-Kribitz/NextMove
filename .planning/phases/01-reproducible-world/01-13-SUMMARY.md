---
phase: 01-reproducible-world
plan: 13
subsystem: testing
tags: [pytest, ci, github-actions, justfile, memory-budget, eng-08]

# Dependency graph
requires:
  - phase: 01-reproducible-world (plans 01-06, 01-08, 01-09, 01-10, 01-11)
    provides: the six peak-process-RSS assertions and the CI/Justfile machinery this plan rewires
provides:
  - A dedicated `peak_rss` pytest marker carrying exactly the six RSS-dependent assertions across
    test_simulation_budget.py, test_ingest_budget.py, test_features_budget.py
  - A rewritten CI "Peak-RSS suite" step that selects those six by marker, cannot pass while any
    of them skips or the collected count drifts, and evaluates its gates even when pytest itself
    fails (captured exit status instead of a shell abort)
  - A `just budget-rss` recipe that reproduces the CI step's exact selection locally on Linux
  - A collection-based unit test (tests/unit/test_ci_workflow_structure.py) binding the marker
    set, the CI step's expected-count literal, and the Justfile recipe together, on the Windows
    dev machine, before CI runs
affects: [ci-workflow, memory-budget-suites]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "peak_rss pytest marker: selects only assertions that read resource.getrusage, distinct from
      slow (env-gated on-demand runs)"
    - "CI step exit-status capture pattern: `cmd || status=$?` then unconditional gate checks then
      `exit $status`, to keep skip/count gates reachable when the piped command fails under
      bash -eo pipefail"

key-files:
  created: []
  modified:
    - pyproject.toml
    - tests/integration/test_simulation_budget.py
    - tests/integration/test_ingest_budget.py
    - tests/integration/test_features_budget.py
    - .github/workflows/ci.yml
    - Justfile
    - tests/unit/test_ci_workflow_structure.py

key-decisions:
  - "Widened the demo wall-clock budget to 1200.0 in all three budget files' _PROFILE_BUDGETS
    (not only test_simulation_budget.py's, whose 600.0 was the one that actually failed on CI at
    638.4s) -- Task 1's own done-criteria required uniform 1200.0 across all three, and no test in
    the ingest/features files ever asserts that element anyway (both unpack and discard it), so
    this is consistent belt-and-braces margin rather than a functional fix in those two files."
  - "Dropped the explicit -q pytest 9.1 gained in the plan's literal CI/Justfile/test-helper
    invocations (`-m peak_rss -rs -q`, `--collect-only -q -m peak_rss`) -- this repo's
    pyproject.toml addopts already supplies one -q, and pytest 9.1.1 suppresses its own final
    summary line ('N passed'/'N skipped') and switches --collect-only from per-node-id lines to a
    per-file count summary once verbosity is lowered a second time. Every place that must read
    pytest's own text output (the CI step's two grep gates, the Justfile budget-rss recipe, and
    the new unit test's node-id collector) now carries no explicit -q of its own, relying solely
    on the single addopts-supplied level. Documented inline at each of the three call sites."

requirements-completed: [ENG-08]

coverage:
  - id: D1
    description: "peak_rss marker registered and applied to exactly the six RSS-dependent
      assertions; -m peak_rss collects them and nothing else"
    requirement: "ENG-08"
    verification:
      - kind: unit
        ref: "tests/unit/test_ci_workflow_structure.py#test_peak_rss_marker_selects_exactly_the_intended_assertions"
        status: pass
      - kind: other
        ref: "uv run python -m pytest --collect-only -m peak_rss | grep -c :: -> 6"
        status: pass
    human_judgment: false
  - id: D2
    description: "CI step selects -m peak_rss, captures pytest's exit status so its skip gate and
      a new collected-count gate both evaluate even when pytest fails, and the general test-suite
      step excludes peak_rss so each assertion runs exactly once per CI run"
    requirement: "ENG-08"
    verification:
      - kind: unit
        ref: "tests/unit/test_ci_workflow_structure.py#test_peak_rss_step_selects_the_marker_and_names_the_expected_count"
        status: pass
      - kind: unit
        ref: "tests/unit/test_ci_workflow_structure.py#test_peak_rss_step_evaluates_its_gates_even_when_pytest_fails"
        status: pass
      - kind: unit
        ref: "tests/unit/test_ci_workflow_structure.py#test_general_test_suite_step_excludes_peak_rss"
        status: pass
    human_judgment: true
    rationale: "The step's actual behavior on a real Linux runner (6 passed, no skips, job green)
      cannot be observed from this Windows dev machine -- the six assertions self-skip here
      (POSIX-only resource module). Structural correctness is proven by the unit tests above;
      the plan's own <human-check> requires a real Linux CI run to close UAT gap G-01-2, which
      this plan does not claim to close on its own."
  - id: D3
    description: "just budget-rss reproduces the CI step's exact selection; just budget covers
      slow or peak_rss so it still covers the whole ENG-08 story on demand"
    requirement: "ENG-08"
    verification:
      - kind: unit
        ref: "tests/unit/test_ci_workflow_structure.py#test_local_and_ci_peak_rss_selections_agree"
        status: pass
      - kind: other
        ref: "just --list | grep -q budget-rss"
        status: pass
    human_judgment: false

# Metrics
duration: ~55min
completed: 2026-08-05
status: complete
---

# Phase 01 Plan 13: CI peak-RSS gate closure Summary

**Dedicated `peak_rss` pytest marker plus a rewritten CI step that fails the job on any skipped or
missing peak-RSS assertion, closing the marker/filter mismatch that let `-m slow` collect one
unrelated, wall-clock-bound test for five plans running.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Registered `peak_rss` as a strict pytest marker and applied it to exactly the six
  peak-process-RSS assertions across the three budget files (Bug A from the debug session's
  root cause -- `.planning/debug/ci-budget-marker-mismatch.md`)
- Rewrote the CI "Memory budget suite" step into a "Peak-RSS suite" step: selects `-m peak_rss`,
  captures pytest's exit status (`|| status=$?` / `exit $status`) so its skip gate and a new
  collected-count gate both evaluate even when pytest itself fails -- closing the secondary
  masking effect where `bash -eo pipefail` aborted the script before the skip gate ever ran
- General "Test suite" CI step now filters `-m "not peak_rss"` so each RSS assertion runs exactly
  once per CI run, not once unmeasured there and once in the gated step
- `just budget-rss` reproduces the CI step's exact selection locally (self-skips on Windows,
  runnable on Linux); `just budget` widened to `-m "slow or peak_rss"` so it still covers the
  whole ENG-08 story on demand
- Widened the demo-profile wall-clock budget to 1200.0 (from 600.0/900.0) in all three files,
  belt-and-braces margin over the 638.4s observed on ubuntu-latest CI run 31015357302 (Bug B)
- Rewrote `tests/unit/test_ci_workflow_structure.py` to bind the marker set, the CI step's
  expected-count literal, and the Justfile recipe together via a real `pytest --collect-only`
  subprocess call, on the Windows dev machine, before CI runs

## Task Commits

Each task was committed atomically:

1. **Task 1: Register a peak_rss marker, apply it to the six RSS assertions, widen the demo wall
   clock** - `768a203` (test)
2. **Task 2: Rewire the CI step and the Justfile onto the marker, and make the skip gate
   reachable** - `ac929d8` (fix)
3. **Task 3: Bind the marker, the CI filter and the Justfile recipe together with a
   collection-based test** - `d17cdc0` (test)

**Plan metadata:** (this commit)

## Files Created/Modified
- `pyproject.toml` - registered `peak_rss` marker under `[tool.pytest.ini_options].markers`
- `tests/integration/test_simulation_budget.py` - `@pytest.mark.peak_rss` on two tests; demo
  wall-clock budget 600.0 -> 1200.0 with a comment citing the CI observation
- `tests/integration/test_ingest_budget.py` - `@pytest.mark.peak_rss` on two tests; demo
  wall-clock budget 900.0 -> 1200.0
- `tests/integration/test_features_budget.py` - `@pytest.mark.peak_rss` on two tests; demo
  wall-clock budget 900.0 -> 1200.0
- `.github/workflows/ci.yml` - "Test suite" step filters `-m "not peak_rss"`; "Memory budget
  suite" step replaced by "Peak-RSS suite" (marker selection, captured exit status, skip gate,
  collected-count gate, no explicit `-q`)
- `Justfile` - `budget` recipe filter widened to `-m "slow or peak_rss"`; new `budget-rss` recipe
  added directly after `budget`
- `tests/unit/test_ci_workflow_structure.py` - rewritten: `EXPECTED_PEAK_RSS_TESTS`,
  `_collected_peak_rss_node_ids()`, `_justfile_recipe_body()`, and five tests binding the marker
  set, the CI step, and the Justfile recipe together; `test_no_continue_on_error_anywhere`
  unchanged

## Decisions Made
- Widened the demo wall-clock element uniformly to 1200.0 in all three budget files rather than
  only test_simulation_budget.py's (the one that actually measured 638.4s > 600.0s on CI). The
  plan's Task 1 done-criteria required 1200.0 in all three files; the ingest/features files'
  demo entries were already at 900.0 (not the plan's assumed 600.0) and no test in either file
  actually reads that element for a wall-clock assertion (`TestBoundedAccumulation` and
  `TestPeakResidentMemory` both unpack and discard it), so this is consistent margin rather than
  a fix for an observed failure in those two files.
- Dropped the explicit `-q` the plan's literal action text specified for the CI step's pytest
  invocation, the `budget-rss` Justfile recipe, and the unit test's `_collected_peak_rss_node_ids`
  subprocess call. See Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dropped a redundant explicit `-q` that pytest 9.1.1 turns into silent output**
- **Found during:** Task 1 verification (running the plan's own `--collect-only -q -m peak_rss`
  verify command)
- **Issue:** This repo's `pyproject.toml` sets `addopts = "-q --strict-markers"`. Pytest 9.1.1
  (the version installed via `uv.lock`) treats a second `-q` on the command line as a further
  verbosity decrease: `--collect-only` switches from one-node-id-per-line output to a per-file
  count summary containing no `::` at all, and a normal test run suppresses its own final
  summary line (`"N passed"` / `"N skipped"`) entirely. The plan's action text specified `-m
  peak_rss -rs -q` for the CI step and `--collect-only -q -m peak_rss` for the new unit test's
  subprocess call -- both would have silently defeated the exact mechanisms (grep gates,
  node-id parsing) this plan exists to build, on this project's actual pytest version.
- **Fix:** Removed the explicit `-q` from the CI "Peak-RSS suite" step's pytest invocation, the
  `just budget-rss` recipe, and `_collected_peak_rss_node_ids()`'s subprocess call, relying
  solely on the single `-q` already supplied by `addopts`. Verified interactively: a single `-q`
  prints both the summary line and `-rs` skip reasons; a second `-q` prints neither. Documented
  the reasoning inline as a comment at all three call sites so a future contributor does not
  "helpfully" re-add it.
- **Files modified:** `.github/workflows/ci.yml`, `Justfile`, `tests/unit/test_ci_workflow_structure.py`
- **Verification:** `uv run python -m pytest --collect-only -m peak_rss | grep -c "::"` -> 6;
  `tests/unit/test_ci_workflow_structure.py::test_peak_rss_marker_selects_exactly_the_intended_assertions`
  passes (exercises the same subprocess call the CI-equivalent path uses)
- **Committed in:** `768a203` (Task 1 verify), `ac929d8` (Task 2 CI/Justfile), `d17cdc0` (Task 3
  unit test)

**2. [Rule 1 - Bug] Widened all three files' demo wall clock, not only the one the plan named**
- **Found during:** Task 1, reconciling the plan's action text ("all three files' ... from 600.0
  to 1200.0") against the actual pre-existing values (`test_ingest_budget.py` and
  `test_features_budget.py` were already at 900.0, not 600.0)
- **Issue:** The plan's action text asserted a factual premise ("demo = (512.0, 1536.0, 600.0)"
  duplicated verbatim across all three files) that did not match the code: only
  `test_simulation_budget.py`'s demo entry was 600.0.
- **Fix:** Followed the plan's Done criteria (authoritative: "the demo wall-clock element is
  1200.0 in all three files") rather than the inaccurate "from 600.0" premise -- widened
  `test_ingest_budget.py` and `test_features_budget.py`'s demo third elements from 900.0 to
  1200.0 as well, each with a comment noting no test in that file actually asserts the element.
- **Files modified:** `tests/integration/test_ingest_budget.py`, `tests/integration/test_features_budget.py`
- **Verification:** grep confirmed only the demo tuple's third element changed in each file; no
  other budget number touched
- **Committed in:** `768a203`

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs found while implementing/verifying)
**Impact on plan:** Both fixes were necessary for the plan's own stated mechanisms (grep-based
CI gates, collection-based unit test) to function on this project's actual pytest version and
actual pre-existing budget values. No scope creep beyond the plan's own file list.

## Issues Encountered
- An exploratory `pytest -m peak_rss -k test_demo_subprocess_peak_rss_under_budget -rs` run
  across all three budget files (used to characterize the `-q`-stacking bug above) took long
  enough on this Windows machine to exceed the interactive command timeout and was moved to a
  background task, because `test_ingest_budget.py`'s and `test_features_budget.py`'s
  `demo_*_subprocess_rss` fixtures both depend on the expensive in-process `demo_run_result`
  fixture chain before they can even reach their own fast internal `resource` import check. Not
  required for this plan's verification (the faster, dependency-free
  `test_simulation_budget.py` case already proved the `-q`/`-rs` behavior); left running
  unattended and not waited on.

## Next Phase Readiness
- The CI peak-RSS gate is structurally correct and unit-tested on this dev machine, but its
  actual behavior on Linux CI (6 passed, no skips, job green) is unobserved -- this is the
  plan's own `<human-check>` item and remains open until the next push to `origin/master` is
  inspected at https://github.com/RafaelBraga-Kribitz/NextMove/actions. Do not treat UAT gap
  G-01-2 as closed until that run is confirmed.
- STATE.md's existing "ENG-08 peak-RSS ... must be confirmed passing on Linux CI" blockers
  (plans 01-06/01-08/01-09/01-10/01-11) are still open for the same reason; this plan fixes the
  gate's mechanics, it does not itself supply a Linux CI observation.

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 7 files listed under Files Created/Modified plus the SUMMARY itself exist on disk; all 4
commit hashes (768a203, ac929d8, d17cdc0, 115d097) are present in `git log --oneline --all`.
