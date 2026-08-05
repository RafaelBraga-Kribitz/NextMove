---
status: complete
phase: 01-reproducible-world
source: [01-VERIFICATION.md]
started: 2026-08-05T00:00:00Z
updated: 2026-08-05T15:20:00Z
---

## Current Test

number: none
name: all tests complete
expected: |
  n/a
awaiting: none

## Tests

### 1. Full-scale byte-identical reproduction at the `default` profile

expected: Run `just reproduce` (or `make reproduce`) with the committed default `dvc.yaml`
profile (50,000 customers, 548-day horizon) to completion at least once, then a second time into
an independent `--out` root, and diff the sha256 of all twelve produced tables. Both roots must be
byte-identical.

why_human: This is a real ~1-hour compute job, not something a verifier should launch inside a
review pass. Phase success criterion 1 says "regenerates the full simulated history... byte-identical
across two seeded runs". The mechanism — deterministic RNG, sorted atomic writes, canonical hashing,
out-of-core merges — is proven correct at every scale actually exercised, but the literal full-scale
claim has never been executed by any of the 11 plans' executors. `dvc.lock` still records profile
`tiny` as the last real run.

result: issue
reported: |
  fail — the full-scale default pipeline does not complete, so the byte-identical check never runs.

  What ran:
  - simulator on data/repro_a: 81.8 min — OK — 548 ticks, 24,698,721 events, events_raw ≈ 745 MB
  - ingest on data/repro_a: ~54 min, died at ~79% — OOM during canonical merge
  - features / repro_b / SHA256 comparison: not reached

  What's wrong: ingest fails in write_table_from_parts when DuckDB merges/sorts the part files
  under the intentional STORAGE_MEMORY_LIMIT_MB = 512 ceiling:

    OSError: Out of Memory Error: failed to pin block of size 256.0 KiB
    (488.0 MiB/488.2 MiB used)

  Stack: ingest_events -> write_table_from_parts -> write_parquet_stream <- DuckDB ORDER BY /
  dedupe reader.

  Simulate left a valid raw tree; staging still holds ~754 MB of ingest parts; no
  canonical/*.parquet. Second independent root (repro_b) was never started.

  Not a hash mismatch — default-scale ingest is unrunnable under the shipped 512 MB DuckDB
  limit on this machine.
severity: blocker

### 2. Linux CI run of the peak-RSS memory-budget gate (ENG-08)

expected: Configure a git remote for this repository and let `.github/workflows/ci.yml` run on
Linux — in particular the "Memory budget suite" step, which fails the job if any peak-RSS assertion
is skipped. The peak-process-RSS assertions in tests/integration/test_simulation_budget.py,
test_ingest_budget.py and test_features_budget.py must execute and report numbers under their
stated budgets.

why_human: ENG-08's memory-bounded-at-scale mechanism (streaming Parquet writer, out-of-core DuckDB
merges, row-capped flush buffers) is extensively engineered and tested via proxy instruments
(tracemalloc heap, spill-invariance, chunk-invariance, batch-size-boundedness) that all pass — but
the one instrument that can see the Arrow/DuckDB half of the memory hazard (process RSS) has never
executed to completion on any machine across five plans (01-06, 01-08, 01-09, 01-10, 01-11),
because this repo has no configured remote and the dev machine is Windows. A verifier cannot
fabricate this number or stand up CI infrastructure.

result: issue
reported: |
  fail — Memory budget suite ran on Linux CI but did not execute the peak-RSS assertions under
  budget; the step failed before (and without) those measurements.

  What was set up:
  - remote: https://github.com/RafaelBraga-Kribitz/NextMove (private), origin/master pushed
  - CI run: https://github.com/RafaelBraga-Kribitz/NextMove/actions/runs/31015357302
  - preceding steps OK: Test suite, ci-profile reproduce, Golden suite
  - also pushed bb507b5 fixing a Path/str bug in test_merge_peak_rss_stays_under_budget that
    aborted the first CI run before this step

  What's wrong (two stacked problems):

  1. Marker mismatch: the Memory budget suite invokes the three budget files with `-m slow`,
     but among them only `test_default_profile_completes_within_its_stated_budget` is marked
     `@pytest.mark.slow`. The named peak-RSS tests
     (`test_demo_subprocess_peak_rss_under_budget` in simulation/ingest/features) are not
     marked slow, so they were deselected — the step collected exactly 1 test (`F [100%]`).

  2. That one test failed on wall clock, not RSS:
       [demo budget] wall_clock=638.4s (budget 600.0s),
                     peak_traced_heap=183.8MB (budget 512.0MB)
       AssertionError: demo wall clock 638.4s exceeds budget
     Peak RSS is measured only after the wall-clock/heap asserts, so it never ran. The step's
     "fail on any skipped peak-RSS" grep never evaluated either (`bash -e` exited on pytest).

  Side note: the earlier unfiltered `uv run pytest -q` Test suite step did exercise the
  non-slow budget tests on Linux (~35 min, 1 skip — almost certainly the env-gated default
  budget test) and passed, but without printed peak-RSS numbers and without this step's
  skip-gate — so it does not satisfy the UAT expected outcome for this gate.
severity: blocker

## Summary

total: 2
passed: 0
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-01-1
  truth: "Run the default-profile pipeline (50,000 customers, 548-day horizon) to completion
    twice into independent `--out` roots; both roots byte-identical across all twelve tables."
  status: failed
  reason: "User reported: full-scale default pipeline does not complete. simulator succeeded
    (81.8 min, 24,698,721 events, events_raw ~745MB) but ingest OOM'd at ~79% (~54 min in) inside
    write_table_from_parts while DuckDB merges/sorts part files under the shipped
    STORAGE_MEMORY_LIMIT_MB=512 ceiling: 'OSError: Out of Memory Error: failed to pin block of
    size 256.0 KiB (488.0 MiB/488.2 MiB used)'. Stack: ingest_events -> write_table_from_parts ->
    write_parquet_stream <- DuckDB ORDER BY/dedupe reader. features stage and the second
    independent root (repro_b) were never reached — not a hash mismatch, an unrunnable stage."
  severity: blocker
  test: 1
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- gap_id: G-01-2
  truth: "Linux CI Memory budget suite executes peak-process-RSS assertions in
    test_simulation_budget / test_ingest_budget / test_features_budget and reports numbers
    under stated budgets (no skipped peak-RSS)."
  status: failed
  reason: "CI Memory budget suite on ubuntu-latest
    (https://github.com/RafaelBraga-Kribitz/NextMove/actions/runs/31015357302) collected only
    the one `@pytest.mark.slow` gated test via `-m slow`; named peak-RSS tests were deselected.
    That test failed: demo wall_clock 638.4s > 600s (heap 183.8MB under 512MB); peak RSS never
    measured. Skip-gate grep did not run after pytest failure."
  severity: blocker
  test: 2
  root_cause: ""
  artifacts:
    - "https://github.com/RafaelBraga-Kribitz/NextMove/actions/runs/31015357302"
    - "https://github.com/RafaelBraga-Kribitz/NextMove"
  missing: []
  debug_session: ""
