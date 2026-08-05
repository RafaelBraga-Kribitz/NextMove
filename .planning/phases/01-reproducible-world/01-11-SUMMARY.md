---
phase: 01-reproducible-world
plan: 11
subsystem: infra
tags: [dvc, pytest, ci, reproducibility, simulator-docs]

requires:
  - phase: 01-reproducible-world (plans 01-01..01-10)
    provides: config loader, simulator, ingest pipeline, features layer, storage/lineage
      layer, and the CLI entry points (`__main__.py`) each stage plan built
provides:
  - dvc.yaml wiring simulate/ingest/features into one DAG with disjoint outs and full
    storage/config staleness coverage
  - the real `just reproduce`/`make reproduce` command (D-14)
  - `python -m nextmove.storage <table>` lineage-chain CLI (DATA-04)
  - a golden two-root byte-identical reproducibility suite (ENG-04)
  - a config-drives-behaviour suite proving a YAML edit changes output with no code edit
  - CI steps for the miniature end-to-end run, the golden suite, and a memory-budget gate
    that fails on any skipped peak-RSS assertion
  - docs/SIMULATOR_ASSUMPTIONS.md and its structural floor check
affects: [phase-verification, phase-2-planning, gsd-secure-phase]

tech-stack:
  added: []
  patterns:
    - "dvc.yaml vars are patched in place by the justfile recipe before `dvc repro`, since
      this dvc version has no CLI override for `vars:` outside `dvc exp run`"
    - "golden/config-mutation tests call run_simulation/ingest_events/materialize_grid
      directly (mirroring each CLI's own logic) rather than through argparse, because the
      CLIs hardcode the default config directory and cannot be pointed at a temporary,
      mutated config tree"

key-files:
  created:
    - dvc.yaml
    - src/nextmove/storage/__main__.py
    - tests/integration/test_dvc_pipeline_structure.py
    - tests/golden/test_reproducibility.py
    - tests/integration/test_config_drives_behavior.py
    - tests/unit/test_ci_workflow_structure.py
    - docs/SIMULATOR_ASSUMPTIONS.md
    - tests/unit/test_simulator_assumptions_doc.py
  modified:
    - justfile
    - .github/workflows/ci.yml

key-decisions:
  - "dvc.yaml's committed vars.profile default is `default` (the full production-scale
    profile), matching phase success criterion 1's literal 'regenerates the full simulated
    history' claim for a bare `just reproduce`/`make reproduce` invocation"
  - "just reproduce sed-patches dvc.yaml's vars.profile line in place before calling
    `dvc repro`, because this dvc version (3.67.1) has no CLI flag to override a `vars:`
    value outside `dvc exp run` (which creates a separate experiment ref, not this repo's
    own dvc.lock)"
  - "Added tests/integration/test_dvc_pipeline_structure.py and
    tests/unit/test_ci_workflow_structure.py -- not in the plan's file list -- as the
    permanent home for the plan's own static/structural acceptance criteria (dvc.yaml
    non-overlap rules, MEDIUM-9 dep coverage, CI step ordering and continue-on-error
    absence), which otherwise had no committed test artifact"
  - "The zero-row-table proof cannot use n_customers=0 (schema-constrained gt=0); it zeros
    engagement.base_session_probability and campaigns.send_probability_per_eligible_day
    instead, producing real customers who generate zero events"

requirements-completed: [ENG-04, ENG-08, ENG-09, SIM-03]

coverage:
  - id: D1
    description: "dvc.yaml declares simulate/ingest/features with disjoint outs, no
      self-dependency, no lineage-fragment deps, the two required producer->consumer
      edges, and full storage/config dep coverage on all three stages"
    requirement: "ENG-09"
    verification:
      - kind: integration
        ref: "tests/integration/test_dvc_pipeline_structure.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "just reproduce / make reproduce runs the full DVC pipeline end to end;
      a forced re-execution proves the canonical rematerialize path is byte-equal to the
      append-only direct-invocation path"
    requirement: "ENG-08"
    verification:
      - kind: integration
        ref: "manual run: just reproduce profile=\"tiny\" (see Verification Record below)"
        status: pass
    human_judgment: false
  - id: D3
    description: "python -m nextmove.storage <table> prints the full lineage chain"
    requirement: "ENG-09"
    verification:
      - kind: integration
        ref: "manual run: uv run python -m nextmove.storage feature_grid"
        status: pass
    human_judgment: false
  - id: D4
    description: "Two ci-profile runs into two independent --out roots are byte-identical
      across all twelve tables; equal seeds match, a different seed diverges; a zero-event
      world produces full-schema zero-row tables; differing PYTHONHASHSEED/cwd still
      converge; an interrupted ingest leaves no truncated table; re-running one stage
      leaves other stages' lineage fragments unchanged"
    requirement: "ENG-04"
    verification:
      - kind: integration
        ref: "tests/golden/test_reproducibility.py (6 tests, run with -m slow)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Mutating a seasonality multiplier, a latent-trait parameter, or a
      features.yaml list entry each changes the output digest and the config hash with no
      src/ file touched"
    requirement: "ENG-03 (end to end, phase success criterion 5)"
    verification:
      - kind: integration
        ref: "tests/integration/test_config_drives_behavior.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "CI runs the ci-profile end-to-end, the golden suite, and a memory-budget
      step that fails the job if any peak-RSS assertion is skipped"
    requirement: "ENG-08"
    verification:
      - kind: unit
        ref: "tests/unit/test_ci_workflow_structure.py"
        status: pass
      - kind: other
        ref: "peak-RSS numbers are not obtainable on this Windows dev machine (resource
          module unavailable); must be confirmed on Linux CI, same open item carried
          from plans 01-06/01-08/01-09/01-10"
        status: unknown
    human_judgment: true
    rationale: "The memory-budget numbers this deliverable's ENG-08 claim ultimately rests
      on have never been measured on this dev machine across five plans now; only Linux CI
      can produce them. A human must confirm the first green CI run before treating ENG-08
      as fully proven end to end."
  - id: D7
    description: "docs/SIMULATOR_ASSUMPTIONS.md documents every generative assumption tied
      to its config key, and a floor check keeps it from silently going stale"
    requirement: "SIM-03"
    verification:
      - kind: unit
        ref: "tests/unit/test_simulator_assumptions_doc.py (9 tests)"
        status: pass
    human_judgment: false

duration: ~2h (approximate; PLAN_START_EPOCH was not captured at session start)
completed: 2026-08-05
status: complete
---

# Phase 1 Plan 11: Wire the DVC pipeline, prove reproducibility, document the simulator Summary

**Three DVC stages (simulate/ingest/features) wired into one DAG behind `just reproduce`, a
byte-identical two-root golden suite over the `ci` profile, a config-drives-behaviour proof, CI
extended with an end-to-end run and a peer-RSS gate, and `docs/SIMULATOR_ASSUMPTIONS.md` with
its structural floor check.**

## Performance

- **Duration:** ~2h (approximate — the mandatory `PLAN_START_EPOCH` capture step was missed at
  session start; commit timestamps span 2026-08-05T04:16:58+02:00 to 04:38:02+02:00 for the
  three task commits, with substantial investigation/verification time before the first commit)
- **Completed:** 2026-08-05
- **Tasks:** 3 of 3
- **Files modified/created:** 12 (2 modified: `justfile`, `.github/workflows/ci.yml`; 10
  created: `dvc.yaml`, `src/nextmove/storage/__main__.py`, `docs/SIMULATOR_ASSUMPTIONS.md`,
  and 7 test files including 2 not in the plan's original file list)

## Accomplishments

- `dvc.yaml` declares `simulate` → `ingest` → `features` with disjoint outs, no
  self-dependency, no lineage fragment as any dep, both required producer→consumer edges, and
  every stage depending on `src/nextmove/storage/` and `src/nextmove/config/` (MEDIUM-9) —
  verified both statically (`tests/integration/test_dvc_pipeline_structure.py`) and at runtime
  (touching `storage/paths.py` marks all three stages stale via `dvc status`)
- `just reproduce`/`make reproduce` is the real, working one-command pipeline; a second and
  third run with unchanged inputs are genuine no-ops with a byte-identical `dvc.lock`; a forced
  `dvc repro --force` re-execution reproduces byte-identical canonical tables, proving the
  rematerialize and append-only paths agree
- `python -m nextmove.storage <table> [--root]` prints a full lineage chain (DATA-04)
- `tests/golden/test_reproducibility.py`: 6 tests proving byte-identical two-root `ci`-profile
  reruns across all twelve tables, seed adjacency, zero-row full-schema tables, environment
  (hash-seed + cwd) independence, interrupted-run safety, and stage-isolation of lineage
  fragments — all passing (`-m slow`, ~112s)
- `tests/integration/test_config_drives_behavior.py`: 4 tests proving a seasonality
  multiplier, a trait parameter, and a features.yaml list entry each change output digest and
  config hash with zero `src/` modification — all passing
- `.github/workflows/ci.yml` appends the `ci`-profile end-to-end step, the golden suite step,
  and a memory-budget step that fails the job on any skipped peak-RSS assertion, with a
  dedicated structural test (`tests/unit/test_ci_workflow_structure.py`) proving the ordering
  and the absence of `continue-on-error`
- `docs/SIMULATOR_ASSUMPTIONS.md` (251 non-blank lines) documents every generative assumption
  — latent traits, seasonality, inventory/restock calibration, campaigns, organic behaviour,
  micro-events, the `response_multiplier` formula, the fatigue loophole, determinism, and
  known limitations including the `ground_truth_uplift` sampling cadence — with a 9-test floor
  check (`tests/unit/test_simulator_assumptions_doc.py`)

## Task Commits

1. **Task 1: Wire the DVC pipeline stages and the reproduce interface** - `2417147` (feat)
2. **Task 2: Prove byte-identical reruns and config-driven behaviour, and extend CI** -
   `f2cc792` (test)
3. **Task 3: Write SIMULATOR_ASSUMPTIONS.md and its structural floor check** - `6685263` (docs)

**Plan metadata:** (this commit, immediately following)

## Files Created/Modified

- `dvc.yaml` - three-stage DAG (simulate/ingest/features), `vars.profile` default `default`
- `justfile` - `reproduce` body replaced (sed-patches `dvc.yaml`'s profile var, then
  `dvc repro`); `budget` widened to all three stage budget suites; new `lineage`/`clean`
  recipes (13 recipes total)
- `src/nextmove/storage/__main__.py` - lineage-chain CLI
- `tests/integration/test_dvc_pipeline_structure.py` - static + one runtime structural proof
  for `dvc.yaml` (not in plan's original file list — added per Rule 2, see Deviations)
- `tests/golden/test_reproducibility.py` - the byte-identical two-root golden suite
- `tests/integration/test_config_drives_behavior.py` - the config-drives-behaviour suite
- `.github/workflows/ci.yml` - appended three steps after the existing `pytest -q` step
- `tests/unit/test_ci_workflow_structure.py` - static CI-workflow structure proof (not in
  plan's original file list — added per Rule 2, see Deviations)
- `docs/SIMULATOR_ASSUMPTIONS.md` - the assumption log
- `tests/unit/test_simulator_assumptions_doc.py` - the floor check

## Verification Record

**`just --list` (final, 13 recipes):**
```
default, setup, fmt, lint, test, ci, simulate, budget, ingest, features, reproduce, lineage,
clean
```

**`dvc.yaml` stage-to-outs / stage-to-deps (verbatim, see the committed file for full
comments):**
```
simulate: deps=[config, src/nextmove/simulator, src/nextmove/config, src/nextmove/storage]
          outs=[data/raw, data/ground_truth, data/lineage/simulate.parquet]
ingest:   deps=[data/raw, src/nextmove/ingest, src/nextmove/storage, src/nextmove/config,
                config/data_quality.yaml]
          outs=[data/canonical, data/lineage/ingest.parquet]
features: deps=[data/canonical, src/nextmove/features, src/nextmove/storage,
                src/nextmove/config, config/features.yaml]
          outs=[data/features, data/lineage/features.parquet]
```

**Twelve file digests from a `ci`-profile golden run** (sha256, one of the two runs the golden
suite proves byte-identical — captured here as a reference point for future regression):
```
e843977bc2643d9299d96f5d05a2549b0eec27e67728663522ae36fef481527a  canonical/events.parquet
bc9713e3bc84f00d9528d39d5b8b5f65e6b341a331c556c8a7de9aeb4a82e744  canonical/rejects.parquet
f424fdcbbd970a59484bac96d70b124d09cb081a00f4e6a344ab3ecaca8c8456  features/feature_grid.parquet
cf95911aa71761dadd76730c622433211753c6d4ec48390b1a549cc663918b69  ground_truth/customer_traits.parquet
ec75fc5979039e17090b104a4d07cf48a63de7dc1a9c579df868c7e86bcf3072  ground_truth/ground_truth_uplift.parquet
3ea03e93a64814329792a52740ca5b3ef8a5ac26f81fd1a15cf24761f2a31f5b  lineage/features.parquet
2d7827ac376ef15188a32b2a319bb469448a2103f3091f4dbab98802d02fc0cc  lineage/ingest.parquet
cf88dc1133bd3f3e96f93bf2983fec7cc1e08a086f7c249bd817ae73dcb2cec7  lineage/simulate.parquet
dba211d42444b7b3025e51c150ea4a33e410cee9c2cb4791ca0430035903bab7  raw/campaigns.parquet
a395199fbbc5d75922a5b32611226cf94fb85f16c644cee6e80222de852e87c8  raw/catalog.parquet
54db8fe8dafc0a374914423f4d33eece43f3fbec6e5c9b3d8154038e9279820d  raw/events_raw.parquet
532e060889801a39c87edd0706f48bd0fbd0c81ddb98180c1c0131c51c81cc41  raw/inventory_snapshots.parquet
```
(config_hash for this run: `a0fe0236b82d68bff177bc94bc7668e8cc9f83411c480807a8fc91451f312508`,
`ci` profile, 60 ticks, 23,682 events, 29,160 feature_grid rows.)

**Canonical digests before/after a forced `dvc repro --force` re-execution (`tiny` profile,
proving rematerialize == append-only)**, unchanged in both cases:
```
events.parquet:  ef88762430e875345ff9b43b2c32fdd7527b7b47aa694b7255effe771efc8b24
rejects.parquet: 5e0945eb2475388d6f97f929867d76ecac22d6d9248425bff459344c8ef4a95c
```

**Peak RSS from the CI memory-budget step:** not measured in this session. All three budget
suites' peak-RSS assertions self-skip on this Windows dev machine (`resource` module
unavailable) — the same carried-forward open item recorded in `STATE.md`'s Blockers/Concerns
for plans 01-06/01-08/01-09/01-10. This plan adds the CI-side gate (`tests/unit/
test_ci_workflow_structure.py` + the new CI step) that will force these three numbers to be
produced and enforced the first time this workflow runs on Linux CI, but no such run has
occurred yet as part of this execution. **This must be confirmed green on the first real CI
run before ENG-08 is treated as fully proven** — recorded explicitly here per the plan's own
risk-note instruction to distinguish what was actually run to completion from what was wired.

**What was and was not run to completion (risk-note honesty statement):**
- `tiny` profile (100 customers, 30 days): run to completion multiple times via `just
  reproduce`, including a forced full re-execution and three consecutive no-op reruns with a
  byte-identical `dvc.lock`. **Fully demonstrated end to end.**
- `ci` profile (500 customers, 60 days): run to completion multiple times, including the full
  golden two-root byte-identical suite, the seed-adjacency test, the environment-independence
  subprocess test, and the interruption test. **Fully demonstrated end to end**, including the
  byte-identical reproducibility claim across two independent output roots.
- `default` profile (50,000 customers, 548 days): **not run to completion in this session.**
  `dvc.yaml`'s committed `vars.profile` default is `default`, so a bare `just reproduce`/
  `make reproduce` targets it, but actually executing it was not attempted here — plan 01-08's
  SUMMARY previously estimated this at "on the order of an hour," and that estimate is
  unchanged and still unconfirmed by this plan. The reproducibility *mechanism* is proven at
  `tiny`/`ci` scale; the `default`-scale run itself remains an open item, identical in kind to
  the pre-existing carried-forward blocker for the memory-budget numbers above.

## Decisions Made

- **dvc.yaml's committed default profile is `default`, not a fast profile.** A bare
  `just reproduce`/`make reproduce` must target the full simulated history to make phase
  success criterion 1's literal wording true; committing a fast profile as the default would
  quietly narrow the phase's headline claim.
- **`just reproduce` patches `dvc.yaml`'s `vars.profile` line in place before calling
  `dvc repro`.** This dvc version (3.67.1) has no CLI flag to override a `vars:` value outside
  `dvc exp run`, which writes to a separate experiment ref rather than this repo's own
  `dvc.lock`. Rewriting the committed file in place — `cmd` is part of what DVC hashes per
  stage, so a profile switch correctly invalidates the stage cache, and a repeated run with the
  same profile is a genuine no-op — is the standard workaround for parameterizing a checked-in
  DVC pipeline without the experiments feature.
- **The zero-row-table proof zeros two probabilities rather than `n_customers`.**
  `simulator.n_customers` and `horizon_days` are both schema-constrained `Field(gt=0)`, so a
  literal zero-customer world is not a valid config. Zeroing `engagement
  .base_session_probability` and `campaigns.send_probability_per_eligible_day` instead produces
  real customers who never generate a single event, which is sufficient to exercise the
  zero-row, full-schema, byte-identical-across-runs assertion the plan requires.
- **Golden/config-mutation tests call `run_simulation`/`ingest_events`/`materialize_grid`
  directly rather than through each stage's CLI `main()`.** The CLIs hardcode the default
  config directory (`load_config(args.profile)` with no `config_dir` argument) and cannot be
  pointed at a temporary, mutated config tree — the exact thing the seed-adjacency, zero-row,
  and config-drives-behaviour tests all need. Each helper mirrors its CLI counterpart's logic
  (including the raw-events JSON-payload decode step) rather than reusing it directly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - missing test artifact] Added `tests/integration/test_dvc_pipeline_structure.py`**
- **Found during:** Task 1
- **Issue:** The plan's acceptance criteria for Task 1 require a static non-overlap/dep-coverage
  script and a runtime `dvc status` staleness proof, but Task 1's `files_modified` list names
  only `dvc.yaml`, `justfile`, and `src/nextmove/storage/__main__.py` — no test file to host
  these checks permanently.
- **Fix:** Added a new integration test file covering the four-rule non-overlap check
  (outs-vs-outs disjointness, no self-dependency, no lineage-fragment dep, required
  producer→consumer edges), the MEDIUM-9 dep-coverage check, and a `@pytest.mark.slow` runtime
  proof that touching `src/nextmove/storage/paths.py` marks all three stages stale via
  `dvc status`.
- **Files modified:** `tests/integration/test_dvc_pipeline_structure.py`
- **Verification:** `uv run pytest tests/integration/test_dvc_pipeline_structure.py -q` (5
  fast tests) and `-m slow` (1 test) both pass.
- **Committed in:** `2417147` (Task 1 commit)

**2. [Rule 2 - missing test artifact] Added `tests/unit/test_ci_workflow_structure.py`**
- **Found during:** Task 2
- **Issue:** The plan's acceptance criteria require "a test asserts that step exists and is
  not `continue-on-error`" for the memory-budget CI step, but Task 2's file list names only
  `.github/workflows/ci.yml` itself, not a test file to assert its structure.
- **Fix:** Added a small static YAML-structure test asserting the new steps exist, run in the
  right order, and that the memory-budget step is not `continue-on-error`.
- **Files modified:** `tests/unit/test_ci_workflow_structure.py`
- **Verification:** 4/4 tests pass.
- **Committed in:** `f2cc792` (Task 2 commit)

**3. [Rule 3 - blocking issue] Worked around a `dvc repro --dry` crash on a data-less repo**
- **Found during:** Task 1
- **Issue:** `uv run dvc repro --dry` on this dvc version (3.67.1) raises an uncaught
  `FileNotFoundError` inside `dvc/stage/cache.py`'s run-cache `_can_hash`/`restore` path when a
  downstream stage's dependency (an upstream stage's not-yet-materialized output directory,
  e.g. `data/raw/`) does not exist on disk at all — which is exactly the state of a genuinely
  fresh clone, since `data/` is entirely `.gitignore`d. The crash is unconditional (occurs even
  with `--no-run-cache`, since `_can_hash` is called before that flag is checked) and is not
  Windows-specific (the failing `os.stat` call has no OS-specific branch).
- **Fix:** No code fix is possible for a third-party package's own dry-run implementation. The
  operationally correct sequence — confirmed working — is to run the real pipeline once first
  (`just reproduce`), after which `dvc repro --dry`, `dvc status`, and repeated real runs all
  behave correctly (verified: two-and three-in-a-row no-op reruns, forced-re-execution digest
  equality, and `dvc repro --dry` all pass once `data/` exists).
- **Files modified:** none (no source change; documented here and in Task 1's acceptance-check
  narrative).
- **Verification:** `uv run dvc repro --dry` exits 0 and lists all three stages once a prior
  `just reproduce` run exists.
- **Committed in:** n/a (behavioral finding, not a code change)

---

**Total deviations:** 3 (2 added test artifacts under Rule 2, 1 documented tooling limitation
under Rule 3). No scope creep beyond what the plan's own acceptance criteria required a
permanent home for.

## Known Stubs

None.

## Threat Flags

None found — the threat surface introduced (the new `python -m nextmove.storage` CLI, the new
CI steps, the sed-based `dvc.yaml` in-place mutation) is all local-machine tooling with no new
network endpoint, auth path, or schema change at a trust boundary; the pre-existing threat
model's dispositions in this plan's frontmatter already cover it.

## Issues Encountered

- `dvc repro --dry`'s crash on a data-less repo (see Deviations #3) cost significant
  investigation time before the workaround was identified. It does not affect the correctness
  of `dvc.yaml` or the `reproduce` recipe — only the specific invocation order of `dvc repro
  --dry` as the very first command on a truly bare checkout.
- The interrupted-ingest golden test (`test_interrupted_ingest_leaves_no_partial_table`) is
  inherently timing-sensitive: a raw OS-level `terminate()` on a subprocess is not guaranteed
  to land mid-write, and Python's default signal disposition does not run cleanup code for an
  unhandled `SIGTERM`. The test asserts the properties that hold regardless of exact timing (no
  truncated table at any destination path, no leftover `.tmp` file, a subsequent clean run
  reproduces the reference digests) rather than asserting the kill landed mid-write.
- A final full-suite confirmation run (`uv run pytest -q -m "not slow"`) was started in the
  background before this SUMMARY was written but did not complete within this session's
  visible window; the pre-existing baseline (`STATE.md`/prior plans' SUMMARYs) already
  documents the full suite taking ">10 minutes." Every new test file was individually verified
  passing (Task 1's structural suite, Task 2's golden suite at `-m slow` and its
  config-drives-behaviour suite, Task 2's CI-structure suite, Task 3's floor check), and
  `just lint` (ruff check, ruff format --check, lint-imports) passed cleanly across the whole
  tree including all new files. The full-suite run should be re-confirmed at phase
  verification if its background completion was not observed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1's mechanical success criteria (byte-identical reruns, config-driven behaviour, one
  reproduce command, documented simulator assumptions) are proven at `tiny`/`ci` profile scale
  and wired for `default` scale.
- **Two open items carry forward, both pre-existing and neither newly introduced by this
  plan:** (1) the `default`-profile full pipeline run has never been executed to completion in
  any session — see the Verification Record's honesty statement; (2) all peak-RSS assertions
  across the whole phase (`01-06`, `01-08`, `01-09`, `01-10`, and this plan's new CI gate) have
  never run to completion on this Windows dev machine and must be confirmed on the first real
  Linux CI run.
- The unreviewed cycle-3 replan flagged in `STATE.md` (external review capacity exhausted,
  `gsd-plan-checker`-only verification) remains open and is unrelated to this plan's own
  content.
- Phase 1 is otherwise ready for `/gsd-plan-review-convergence` / phase verification.

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 10 files listed under "Files Created/Modified" confirmed present on disk. All 3 task
commit hashes (`2417147`, `f2cc792`, `6685263`) confirmed present in `git log --oneline --all`.
