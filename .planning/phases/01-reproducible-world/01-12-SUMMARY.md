---
phase: 01-reproducible-world
plan: 12
subsystem: storage
tags: [duckdb, parquet, ingest, memory-budget, gap-closure]

# Dependency graph
requires:
  - phase: 01-reproducible-world
    provides: write_table_from_parts (plan 01-06), ingest events merge call site (plan 01-09)
provides:
  - Two-stage (materialize-then-sort) dedupe merge in write_table_from_parts, eliminating the
    stacked QUALIFY-window-plus-outer-ORDER-BY DuckDB memory-accounting hazard
  - Tight-memory synthetic proof that the dedupe merge completes under a monkeypatched 100MB
    limit, plus a control proving the legacy single-statement shape still exhausts that budget
  - Runtime guard asserting a dedupe merge never executes one statement that both dedupes and
    sorts outside its window's OVER clause
affects: [phase-01-verification, phase-01-uat, ingest, features]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Blocking-operator staging: when a DuckDB query would stack two blocking operators
      (a QUALIFY window and an outer ORDER BY), split into two statements on two connections
      with an intermediate Parquet materialization in between, per DuckDB's own
      multiple-blocking-operator remediation guidance."

key-files:
  created: []
  modified:
    - src/nextmove/storage/repository.py
    - tests/golden/test_deterministic_write.py
    - .planning/STATE.md

key-decisions:
  - "Tight-memory reproduction parameters tuned to 20 parts x 20,000 rows (400,000 rows total)
    with a 400-byte payload column against a monkeypatched STORAGE_MEMORY_LIMIT_MB of 100 --
    reliably reproduces the exact DuckDB OOM error signature in ~1.1s, well under the plan's
    ~120s section budget, rather than the debug session's slower 3-6M row synthetic repro."
  - "Cross-part duplicate event_id is introduced at each part boundary (the first row of every
    part after the first reuses the immediately preceding part's last row's event_id) so
    surviving (customer_id, ts, event_id) triples stay unique post-dedupe without any extra
    bookkeeping -- event_id alone is unique among dedupe survivors."
  - "Dedupe intermediate lives at data/_staging/_merge_dedupe_<table_name>/part-000000.parquet
    (via resolve_staging_path), unlinked before write and removed in a finally via
    clear_staging, so the merge cleans up after itself rather than depending on the producer's
    later clear_staging() call."

requirements-completed: [ENG-04, ENG-08]

coverage:
  - id: D1
    description: "A dedupe merge whose dedupe_on differs from sort_key completes over a part
      set far larger than a tight configured DuckDB memory limit, instead of raising DuckDB's
      Out of Memory Error"
    requirement: "ENG-08"
    verification:
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py#test_dedupe_merge_with_a_different_sort_key_completes_under_a_tight_memory_limit"
        status: pass
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py#test_the_single_query_dedupe_and_sort_shape_exhausts_the_same_budget"
        status: pass
    human_judgment: false
  - id: D2
    description: "No single SQL statement executed by write_table_from_parts both dedupes and
      sorts; a dedupe merge runs at least two separate DuckDB queries"
    requirement: "ENG-08"
    verification:
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py#test_a_dedupe_merge_never_executes_one_statement_that_both_dedupes_and_sorts"
        status: pass
    human_judgment: false
  - id: D3
    description: "ci-profile canonical/events.parquet, canonical/rejects.parquet and
      features/feature_grid.parquet are byte-identical before and after the change"
    requirement: "ENG-04"
    verification:
      - kind: other
        ref: "manual sha256 comparison of ci-profile pipeline output pre/post-change (see below)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The full default-profile (50,000 customers, 548-day horizon) two-root
      byte-identical reproduction that is UAT Test 1's actual closing evidence for G-01-1"
    verification: []
    human_judgment: true
    rationale: "Explicitly out of scope for this plan's executor per the plan's own
      human-check verification block -- a ~2.5-hour compute job across two independent
      --out roots that a human must run and observe before G-01-1 can be marked resolved."

# Metrics
duration: 50min
completed: 2026-08-05
status: complete
---

# Phase 01 Plan 12: G-01-1 Two-Stage Dedupe Merge Summary

**Split `write_table_from_parts`'s dedupe merge into a materialized dedupe stage and a separate sort stage on two DuckDB connections, eliminating the stacked QUALIFY-window-plus-outer-ORDER-BY memory-accounting hazard that aborted the 24.7M-row ingest events merge at 512MB.**

## Performance

- **Duration:** ~50 min
- **Completed:** 2026-08-05
- **Tasks:** 3
- **Files modified:** 3 (`src/nextmove/storage/repository.py`, `tests/golden/test_deterministic_write.py`, `.planning/STATE.md`)

## Accomplishments

- Added three new tests to `tests/golden/test_deterministic_write.py` pinning the memory
  shape: a tight-memory-limit dedupe-merge completion proof, its legacy-shape OOM control,
  and a runtime guard on the executed SQL shape.
- Split `write_table_from_parts`'s dedupe path into two DuckDB statements on two connections
  (materialize the `QUALIFY`-deduped result, close the connection, then sort the intermediate
  on a fresh connection), per DuckDB's own documented remediation for stacked blocking
  operators. The no-dedupe path is unchanged.
- Corrected the docstring's unconditional "memory limit plus one row group at any table size"
  claim to state the true bound separately for each shape the function can take.
- Proved the fix is byte-identical to the pre-change implementation at ci scale across all
  three merge shapes present in the codebase (events: `dedupe_on != sort_key`; rejects:
  `dedupe_on == sort_key`; feature_grid: no `dedupe_on`).
- Recorded the one thing this plan deliberately does not do -- the full default-profile
  reproduction that is UAT Test 1's actual closing evidence -- as an open item in both
  `STATE.md` and this summary.

## Task Commits

Each task was committed atomically:

1. **Task 1: Record pre-change digests and write the three tests that pin the memory shape** - `eedb1ce` (test)
2. **Task 2: Split the dedupe merge into a materialized stage and a separate sort stage** - `11f364e` (fix)
3. **Task 3: Prove the ci-profile output is byte-identical and record the open default-scale check** - `8ca120b` (docs)

_No plan-metadata commit yet -- created after this summary (see `<final_commit>`)._

## Files Created/Modified

- `tests/golden/test_deterministic_write.py` - Added the "Tight-memory dedupe merge shape (G-01-1 gap closure, UAT Test 1)" section: `_build_tight_memory_dedupe_fixture` helper, `test_dedupe_merge_with_a_different_sort_key_completes_under_a_tight_memory_limit`, `test_the_single_query_dedupe_and_sort_shape_exhausts_the_same_budget`, `test_a_dedupe_merge_never_executes_one_statement_that_both_dedupes_and_sorts`.
- `src/nextmove/storage/repository.py` - Rewrote `write_table_from_parts`'s dedupe branch into a two-stage (materialize, then sort) implementation on two connections; corrected the docstring's peak-memory claim.
- `.planning/STATE.md` - Added a Blockers/Concerns bullet recording the open default-profile re-run needed to fully close G-01-1.

## Pre-Change Baseline (Task 1, captured before any `src/` edit)

ci-profile pipeline run into a scratch root outside the repository working tree
(`uv run python -m nextmove.simulator/ingest/features --profile ci --out $OUT/pre`):

| Table | sha256 |
|---|---|
| `canonical/events.parquet` | `e843977bc2643d9299d96f5d05a2549b0eec27e67728663522ae36fef481527a` |
| `canonical/rejects.parquet` | `bc9713e3bc84f00d9528d39d5b8b5f65e6b341a331c556c8a7de9aeb4a82e744` |
| `features/feature_grid.parquet` | `f424fdcbbd970a59484bac96d70b124d09cb081a00f4e6a344ab3ecaca8c8456` |

## Post-Change Verification (Task 3)

Same three stage entry points re-run into a **fresh** scratch root after the fix landed:

| Table | Pre-change sha256 | Post-change sha256 | Match |
|---|---|---|---|
| `canonical/events.parquet` | `e843977b...81527a` | `e843977b...81527a` | Yes |
| `canonical/rejects.parquet` | `bc9713e3...4a82e744` | `bc9713e3...4a82e744` | Yes |
| `features/feature_grid.parquet` | `f424fdcb...c8c8456` | `f424fdcb...c8c8456` | Yes |

All three digests are exact matches. `uv run pytest tests/golden tests/unit tests/leakage -q`
passes (1 pre-existing skip on Windows for the POSIX-only `resource`-based peak-RSS test,
unrelated to this change). `uv run lint-imports` keeps both contracts. `uv run ruff check .`
and `uv run ruff format --check .` are clean repo-wide.

## Tight-Memory Reproduction Parameters (Task 1)

Tuned on this machine: 20 parts x 20,000 rows (400,000 rows total) with a 400-byte payload
column, merged with `dedupe_on="event_id"` differing from
`sort_key=("customer_id","ts","event_id")`, against a monkeypatched
`STORAGE_MEMORY_LIMIT_MB` of 100.

- Fixture generation: ~1.3s
- Legacy single-statement shape (Test B, the control): **fails** in ~1.1s with
  `Out of Memory Error: failed to pin block of size 256.0 KiB (95.1-95.3 MiB/95.3 MiB used)`
  -- the same error signature (differing only in the reported MiB figures) as the production
  failure `Out of Memory Error: failed to pin block of size 256.0 KiB (488.0 MiB/488.2 MiB used)`
  reported in `.planning/debug/ingest-oom-default-scale.md`.
- Two-stage (materialize-then-sort) shape (Test A, the fix): completes in under 2s total.
- Total new-section wall clock: well under the plan's ~120s budget.

These constants (`_TIGHT_MEMORY_MERGE_LIMIT_MB`, `_TIGHT_MEMORY_MERGE_N_PARTS`,
`_TIGHT_MEMORY_MERGE_ROWS_PER_PART`, `_TIGHT_MEMORY_MERGE_PAYLOAD_WIDTH`) are recorded as
module constants in `tests/golden/test_deterministic_write.py` with the same timings and
error text in an adjacent comment.

## Decisions Made

- Tight-memory reproduction scaled down to 400,000 rows / 100MB (vs. the debug session's 3-6M
  rows / 100MB) because the hazard reproduces reliably and instantly at this smaller scale on
  this machine, keeping the new test section's wall clock well under the plan's 120s budget
  while still proving the exact same DuckDB error signature.
- Cross-part duplicate `event_id`s are introduced at part boundaries (each part's first row,
  from the second part onward, duplicates the previous part's last row's `event_id`) rather
  than via a separate distinct-duplicate-ID scheme -- simplest construction that satisfies
  both "one deliberate cross-part duplicate per part" and "surviving triples stay unique"
  without extra bookkeeping.
- The dedupe intermediate's staging path uses the existing `resolve_staging_path`/
  `clear_staging` primitives with a `_merge_dedupe_<table_name>` directory name, keeping it
  invisible to `list_part_files` (which globs `part-*.parquet` only inside directories a
  caller explicitly names) and consistent with every other containment-checked path in this
  module.

## Deviations from Plan

None - plan executed exactly as written. All three tasks, their `<action>` and `<verify>`
blocks, and the pinned interface surfaces (`write_table_from_parts` signature, `connect`,
`write_parquet_stream`, `resolve_staging_path`, `clear_staging`, `list_part_files`) were
followed without modification. The only judgment calls made were the ones the plan explicitly
delegated to the executor (tight-memory parameter tuning in Task 1, per its own instruction
to "adjust ... until BOTH hold on this machine").

## Issues Encountered

None. The reproduction, fix, and byte-identity proof all worked on the first attempt at the
tuned parameters; no auto-fixes (Rules 1-3) or architectural escalations (Rule 4) were needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The G-01-1 code fix is complete, tested at ci scale, and byte-identical to the pre-change
  implementation across all three merge shapes in the codebase.
- **Open item (do not close G-01-1 yet):** the full default-profile (50,000 customers,
  548-day horizon) two-root byte-identical reproduction -- UAT Test 1, the gap's actual
  closing evidence -- has not been re-run. A human must run:
  1. `uv run python -m nextmove.simulator --profile default --out data/repro_a`
  2. `uv run python -m nextmove.ingest --profile default --out data/repro_a`
  3. `uv run python -m nextmove.features --profile default --out data/repro_a`
  4. the same three commands with `--out data/repro_b`
  5. compare the sha256 of every table under `raw/`, `canonical/`, `features/` and
     `ground_truth/` in both roots
  Expected: ingest now completes instead of aborting at ~79% with
  `Out of Memory Error: failed to pin block`, and both roots are byte-identical.
  Budget ~2.5 hours. Recorded in `.planning/STATE.md` under Blockers/Concerns.
- Plan 01-13 (the second gap-closure plan in this phase) can proceed independently of this
  open item.

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-05*

## Self-Check: PASSED

- FOUND: `src/nextmove/storage/repository.py`
- FOUND: `tests/golden/test_deterministic_write.py`
- FOUND: `.planning/STATE.md`
- FOUND: `.planning/phases/01-reproducible-world/01-12-SUMMARY.md`
- FOUND commit: `eedb1ce` (Task 1)
- FOUND commit: `11f364e` (Task 2)
- FOUND commit: `8ca120b` (Task 3)
