---
phase: 01-reproducible-world
verified: 2026-08-05T06:30:00Z
status: human_needed
score: 4/5 roadmap truths verified
behavior_unverified: 2
overrides_applied: 0
human_verification:
  - test: "Run `just reproduce` (or `make reproduce`) with the committed default `dvc.yaml` profile (50,000 customers, 548-day horizon) to completion at least once, then a second time into an independent `--out` root, and diff the sha256 of all twelve produced tables."
    expected: "The run completes (plan 01-08 estimated ~1 hour) and the two roots are byte-identical, exactly as already proven at `tiny` (100 customers/30 days) and `ci` (500 customers/60 days) scale by `tests/golden/test_reproducibility.py`."
    why_human: "This is a real ~1-hour compute job, not something a verifier should launch inside a review pass. Phase success criterion 1 says 'regenerates the full simulated history... byte-identical across two seeded runs' — the mechanism (deterministic RNG, sorted atomic writes, canonical hashing, out-of-core merges) is proven correct at every scale actually exercised, but the literal full-scale claim has never been executed by any of the 11 plans' executors, per `dvc.lock` still recording profile `tiny` as the last real run and every SUMMARY's own honesty section saying so."
  - test: "Configure a git remote for this repository and let `.github/workflows/ci.yml` run on Linux, in particular the 'Memory budget suite (demo profile...)' step, which fails the job if any peak-RSS assertion is skipped."
    expected: "The peak-process-RSS assertions in `tests/integration/test_simulation_budget.py`, `test_ingest_budget.py`, and `test_features_budget.py` execute (they self-skip on Windows because Python's `resource` module is POSIX-only) and report numbers under their stated budgets."
    why_human: "ENG-08's memory-bounded-at-scale mechanism (streaming Parquet writer, out-of-core DuckDB merges, row-capped flush buffers) is extensively engineered and unit/integration-tested via proxy instruments (tracemalloc heap, spill-invariance, chunk-invariance, batch-size-boundedness) that all pass — but the one instrument that can see the Arrow/DuckDB half of the memory hazard (process RSS) has never executed to completion on any machine across five plans (01-06, 01-08, 01-09, 01-10, 01-11), because this repo has no configured remote and the dev machine is Windows. A verifier cannot fabricate this number or stand up CI infrastructure; a human with Linux CI access must run it."
---

# Phase 1: Reproducible World Verification Report

**Phase Goal:** A clean clone produces a complete, queryable, deterministic simulated e-commerce
history — the data foundation every later claim rests on — with the module boundaries, config
discipline, and ratified decisions that keep it honest.
**Verified:** 2026-08-05
**Status:** human_needed
**Re-verification:** No — initial verification

## Summary

All 11 plans are executed and committed. I read all 11 PLAN/SUMMARY pairs, cross-referenced every
requirement ID against `REQUIREMENTS.md`, and independently re-ran a representative slice of the
test suite myself (not trusting the SUMMARYs' self-reported numbers) — golden write tests, import
contracts, ADR/doc structure tests, DVC/CI structure tests, config validation, event contract, and
adapter tests all pass when I run them directly. I also inspected `dvc.lock`, `pyproject.toml`'s
import-linter contracts, and the actual `docs/adr/*.md` / `docs/SIMULATOR_ASSUMPTIONS.md` file
contents rather than trusting the SUMMARYs' claims about them. I additionally built my own
transitive-re-export fixture to test a residual risk the executors flagged but did not resolve
(see SIM-02 below).

**Verdict: the phase goal is substantially achieved.** Sixteen of sixteen requirement IDs have real,
substantive, wired implementations with no stubs and no debt markers (`TBD`/`FIXME`/`XXX`/`TODO`/
`HACK`/`PLACEHOLDER`: zero occurrences anywhere in `src/`, `config/`, or `docs/`). The one
consistently and honestly disclosed gap — the memory-bounded-at-default-scale claim and the
full-simulated-history byte-identical claim have never actually been executed, only engineered and
proven at reduced scale — is real, not fixable by more code, and requires either a human running a
~1-hour job / standing up Linux CI, or an explicit decision to accept reduced-scale evidence as
sufficient for Phase 1 closure.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One command on a clean laptop regenerates the full simulated history into canonical event and feature tables, byte-identical across two seeded runs, no cloud dependency | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `dvc.yaml`/`just reproduce` mechanism exists, is wired, and is *proven* byte-identical across two independent `--out` roots — but only at `tiny` (100 customers/30 days) and `ci` (500 customers/60 days) scale (`tests/golden/test_reproducibility.py`, 6 tests, verified passing directly by me). `dvc.lock` on disk still records profile `tiny` as the last materialized run. The literal "full simulated history" (the committed default profile: 50,000 customers / 548 days) has never been run to completion by any plan in this phase — see `01-08-SUMMARY.md`, `01-09-SUMMARY.md`, `01-11-SUMMARY.md`'s own "Known Limitations"/"Verification Record" sections, all independently confirming this. No cloud dependency is confirmed true (DVC has no remote configured; all tooling is local). |
| 2 | Every derived table states input/config hashes; malformed or semantically invalid events land in quarantine or fail the run | ✓ VERIFIED | `uv run python -m nextmove.storage feature_grid` (run directly by me) prints the full lineage chain with content hashes and config hashes at every level. `tests/integration/test_lineage.py`, `tests/unit/test_ingest_quarantine.py`, `tests/unit/test_semantic_gates.py`, `tests/integration/test_reject_threshold.py` all exist substantively and (per direct + prior-session runs) pass. |
| 3 | A feature row read as_of a past timestamp contains no information created after that timestamp; no evaluation split is random over behavioral time | ✓ VERIFIED | `tests/leakage/test_no_lookahead.py` implements a whole-grid *mutation proof* (append events a decade in the future, assert zero materialized values change) rather than a vacuous "no future timestamp" check — this is real, substantive leakage testing. `tests/unit/test_time_aware_splits.py` proves `time_aware_split` is the only split entry point and has no shuffle/seed/random-state parameter. |
| 4 | CI fails the build if any module in models/, decisions/, policies/, or features/ imports the simulator package | ✓ VERIFIED | `uv run lint-imports --verbose` (run directly by me): both contracts `KEPT`, 67 files / 180 dependencies analyzed, contract one's report names all four forbidden source packages by name (non-vacuous). I additionally built my own scratch fixture with a `models -> shim -> simulator` re-export chain (the residual risk 01-04's SUMMARY flagged as unresolved) and confirmed import-linter's "forbidden" contract type correctly flags it as `BROKEN`, naming the full chain — this closes the disclosed open question. GitHub Actions itself has never executed (no git remote configured for this repo), but the local mechanism (`just ci`) is the identical command set and is proven equivalent. |
| 5 | A reviewer can find every generative assumption and every ratified open decision in `SIMULATOR_ASSUMPTIONS.md` and `docs/adr/001-010`, including an explicit ADR resolving OD-7, and can change a simulator parameter via schema-validated YAML | ✓ VERIFIED | All ten `docs/adr/*.md` files exist with real Context/Decision/Consequences prose (57-70 non-blank lines each, confirmed directly). `docs/adr/007-dvc-and-mlflow-artifact-versioning.md` names `AD-18` and states the recognizability rationale (confirmed by grep). `docs/adr/009-three-tier-autonomy.md` contains `Tier 3` and points at `config/autonomy.yaml` (confirmed). `docs/SIMULATOR_ASSUMPTIONS.md` (290 lines) documents latent-trait distributions, seasonality, restock calibration, the fatigue loophole, and states "in simulation" labeling explicitly (confirmed by grep). `tests/integration/test_config_drives_behavior.py` (4 tests) proves a seasonality multiplier, a trait parameter, and a features.yaml entry each change output digest and config hash with zero `src/` edits. |

**Score:** 4/5 truths verified (1 present, behavior-unverified)

### Requirements Coverage

All 16 requirement IDs declared across the 11 plans' frontmatter exactly match the 16 IDs
`ROADMAP.md` assigns to Phase 1 — no orphans, no gaps, no extras.

| Requirement | Source Plan(s) | Status | Evidence |
|---|---|---|---|
| SIM-01 | 01-07, 01-08 | ✓ SATISFIED | `World.initialize` (config-driven customers/catalog/inventory/campaigns), documented action-response functions computing ground-truth uplift per (customer, action) |
| SIM-02 | 01-04 | ✓ SATISFIED | Import-linter contract non-vacuous (verified directly); my own re-export-chain fixture confirms the disclosed "transitive edge" concern is unfounded — import-linter's forbidden-contract type already catches it |
| SIM-03 | 01-11 | ✓ SATISFIED | `docs/SIMULATOR_ASSUMPTIONS.md` exists substantively with a structural floor test (9 tests, confirmed passing); "in simulation" phrase present |
| SIM-04 | 01-08 | ✓ SATISFIED | scroll/filter_apply/dwell micro-events emitted in `tick.py`, no attached weight (confirmed by grep — the only "weight" hits are internal sku-selection mechanics, never a stored/emitted conversion weight) |
| DATA-01 | 01-05 | ✓ SATISFIED | Canonical `Event` schema, 13-member discriminated union, inward-only `IngestAdapter`, confirmed via direct test run |
| DATA-02 | 01-09 | ✓ SATISFIED | Contract validation + quarantine, append-only idempotent landing |
| DATA-03 | 01-09 | ✓ SATISFIED | Three semantic gates run per-batch before flush, inclusive reject-rate threshold |
| DATA-04 | 01-06 | ✓ SATISFIED | Content-hash lineage, anti-forgery by construction (hash computed from disk bytes, never caller-supplied), printable chain confirmed by direct CLI run |
| FEAT-01 | 01-10 | ✓ SATISFIED | 12 registered feature transforms, `FEATURE_SET_VERSION` stamped into Parquet metadata |
| FEAT-02 | 01-10 | ✓ SATISFIED | Mutation-proof leakage test, ground-truth-zone isolation (static ast ban + dynamic zone-recording check) |
| ENG-01 | 01-01, 01-04 | ✓ SATISFIED | Exactly 13 packages (11 + config/storage infra), both import-linter contracts KEPT, storage sole owner of pyarrow/duckdb |
| ENG-03 | 01-03 | ✓ SATISFIED | 8 domain YAML files + 4 profiles, `extra="forbid"` everywhere, no business literal in `src/` (the one disclosed grep-criterion contradiction is a documented false-positive on a *field name*, not a hardcoded value) |
| ENG-04 | 01-03, 01-06, 01-11 | ✓ SATISFIED | Deterministic hashing, sorted atomic writes, golden byte-identical suite passing at every scale exercised |
| ENG-08 | 01-01, 01-08, 01-09, 01-10, 01-11 | ⚠️ NEEDS HUMAN | Literal text ("runs on a laptop, no cloud dependency, no orchestration, no streaming infra") is true — verified: no cloud service anywhere, DVC has no remote, `justfile` is the sole operational interface. The phase's own (defensible) expansion of ENG-08 into a memory-bounded-at-scale guarantee is mechanically real (streaming writer, out-of-core merges, three review cycles closing successive gaps) but its headline proof — peak process RSS under budget at default/demo scale — has *never executed to completion* on any machine, Windows or Linux, across five plans. `REQUIREMENTS.md` currently marks ENG-08 "Complete"; recommend downgrading that until a Linux CI run confirms the peak-RSS gate (see human_verification below). |
| ENG-09 | 01-06, 01-11 | ✓ SATISFIED | DVC initialized (no remote), `dvc.yaml`/`dvc.lock` real and functioning, ADR-007 ratifies the mechanism |
| DOC-01 | 01-02 | ✓ SATISFIED | 10 ADRs, structural test, `docs/README.md` index, all confirmed by direct file inspection |

### Required Artifacts (spot-checked)

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/nextmove/*/` (13 packages) | importable, real `__init__.py` | ✓ VERIFIED | `ls src/nextmove` confirms all 13 |
| `docs/adr/001-010.md` | ratified ADRs | ✓ VERIFIED | All 10 present, 57-70 non-blank lines each |
| `config/*.yaml` (8) + `config/profiles/*.yaml` (4) | schema-validated, non-stub | ✓ VERIFIED | Inspected `autonomy.yaml`, `data_quality.yaml` directly — real content, not placeholders |
| `src/nextmove/storage/{paths,_parquet,repository,lineage}.py` | deterministic repository layer | ✓ VERIFIED | `write_table`/`write_table_from_parts` golden tests pass directly |
| `docs/SIMULATOR_ASSUMPTIONS.md` | assumption log | ✓ VERIFIED | 290 lines, structural floor test passes |
| `dvc.yaml` / `dvc.lock` | wired 3-stage pipeline | ✓ VERIFIED | Inspected directly; `dvc.lock` shows a real completed `tiny`-profile run |
| `.github/workflows/ci.yml` | Linux-only, no failure suppression | ✓ VERIFIED | Inspected directly: `ubuntu-latest` only, no `continue-on-error`, RSS-skip gate present |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `Makefile` | `justfile` | `make reproduce` → `just reproduce` | ✓ WIRED (3-line Makefile confirmed) |
| `src/nextmove/config/loader.py` | `src/nextmove/config/models.py` | `Config.model_validate` | ✓ WIRED |
| `src/nextmove/storage/repository.py` | `src/nextmove/storage/lineage.py` | `record_lineage` after write | ✓ WIRED (confirmed via lineage CLI output) |
| `.github/workflows/ci.yml` | `pyproject.toml` | `lint-imports` step | ✓ WIRED |
| `dvc.yaml` | three stage `__main__.py` CLIs | `cmd: uv run python -m nextmove.*` | ✓ WIRED (confirmed via `dvc.lock`) |

### Anti-Patterns Found

None. Grepped `src/`, `config/`, `docs/` for `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, `PLACEHOLDER`,
"coming soon", "not yet implemented" — zero occurrences. No stub `__init__.py` beyond the
documented, intentional Phase 2/3/4 boundary stubs (which are declared as stubs in their own
docstrings and are not part of this phase's scope).

### Behavioral Spot-Checks (run directly, not trusted from SUMMARYs)

| Behavior | Command | Result | Status |
|---|---|---|---|
| Import contracts non-vacuous | `uv run lint-imports --verbose` | 2 kept / 0 broken, 67 files, both contracts name real modules | ✓ PASS |
| Transitive re-export chain is caught (residual risk from 01-04) | scratch fixture: `models -> shim -> simulator` | `lint-imports` reports `BROKEN`, names full chain | ✓ PASS |
| Lineage chain printable | `uv run python -m nextmove.storage feature_grid` | prints full chain with content/config hashes at every level | ✓ PASS |
| Golden deterministic write suite | `uv run pytest tests/golden/test_deterministic_write.py tests/unit/test_import_contract.py -q` | 33 passed, 1 skipped (Windows RSS, as designed) | ✓ PASS |
| ADR/doc/config/event-contract/adapter unit suites | `uv run pytest tests/unit/test_adr_structure.py tests/unit/test_package_layout.py tests/unit/test_config_merge_hash.py tests/unit/test_config_validates.py tests/unit/test_event_contract.py tests/unit/test_adapter_registry.py -q` | all passed | ✓ PASS |
| DVC/CI structural tests | `uv run pytest tests/integration/test_dvc_pipeline_structure.py tests/unit/test_ci_workflow_structure.py tests/unit/test_simulator_assumptions_doc.py -q -m "not slow"` | all passed | ✓ PASS |
| `dvc.lock` reflects only reduced-scale runs | `cat dvc.lock` | `cmd: uv run python -m nextmove.simulator --profile tiny` | Confirms open item 2 |
| Full `uv run pytest -q` (whole suite, including demo-scale slow tests) | launched during this verification | did not complete within the verification window (demo-scale integration/golden suites take 10+ minutes per prior sessions' own measured numbers) | Not directly re-confirmed by me; consistent with every individual SUMMARY's own documented pass/fail numbers and with every fast-tier subset I did run directly |

### Deferred / Not Applicable

None — no later-phase deferral applies to any gap found here; the open items are scale/execution
gaps in *this* phase's own claims, not scope legitimately owned by a later phase.

## Gaps Summary

There are no FAILED truths, no missing/stub artifacts, and no broken key links. Every requirement
ID has a real, substantive, wired implementation, and the executors' own disclosure across all 11
SUMMARYs is unusually candid and consistent (the same two open items — default-scale run and
Linux-CI peak-RSS — are named honestly and identically in five separate plans rather than buried or
contradicted).

The phase's single material shortfall is that two of its own headline claims — "regenerates the
**full** simulated history" (roadmap SC1) and "runs entirely on a laptop" in its memory-bounded
sense (ENG-08) — have an engineered, tested-at-reduced-scale mechanism but no completed execution
at the scale the claims are actually made about. This is not a code defect; it is an unexecuted
verification step that requires either (a) a human spending ~1 hour running the default profile
and confirming byte-identical reruns, plus configuring a git remote so Linux CI can run the
peak-RSS gate, or (b) an explicit, recorded decision to accept `tiny`/`ci`/`demo`-scale evidence as
sufficient for Phase 1 closure and defer full-scale confirmation to before Phase 5's portfolio
claims are published.

**Recommendation:** downgrade `REQUIREMENTS.md`'s ENG-08 traceability entry from "Complete" to
"Complete — pending Linux CI confirmation" (or equivalent) until the peak-RSS gate has actually
run green, so the open item is visible in the one document most likely to be read without this
VERIFICATION.md alongside it.

## Human Verification Required

See frontmatter `human_verification` above. Two items, both flowing from the same root cause (no
completed default-scale run, no Linux CI execution to date):

1. Run `just reproduce` at default scale to completion (twice, into separate `--out` roots) and
   diff all twelve table digests.
2. Configure a git remote and let `.github/workflows/ci.yml`'s memory-budget step run on Linux;
   confirm it does not report a skipped peak-RSS assertion.

---

*Verified: 2026-08-05*
*Verifier: Claude (gsd-verifier)*
