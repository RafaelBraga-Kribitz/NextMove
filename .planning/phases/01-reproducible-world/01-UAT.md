---
status: testing
phase: 01-reproducible-world
source: [01-VERIFICATION.md]
started: 2026-08-05T00:00:00Z
updated: 2026-08-05T00:00:00Z
---

## Current Test

number: 1
name: Full-scale byte-identical reproduction at the `default` profile
expected: |
  The run completes (plan 01-08 estimated ~1 hour) and the two independent `--out` roots are
  byte-identical across all twelve produced tables, exactly as already proven at `tiny`
  (100 customers / 30 days) and `ci` (500 customers / 60 days) scale by
  tests/golden/test_reproducibility.py.
awaiting: user response

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

result: [pending]

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

result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
