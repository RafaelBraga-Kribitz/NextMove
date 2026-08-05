---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_phase_name: reproducible-world
status: executing
stopped_at: Completed 01-11-PLAN.md (final plan of phase 01)
last_updated: "2026-08-05T16:48:12.682Z"
last_activity: 2026-08-05
last_activity_desc: Phase 01 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 13
  completed_plans: 11
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-24)

**Core value:** Given a customer state, return the optimal next action — including the action of
doing nothing — ranked by expected incremental constrained profit, with confidence and a
manager-readable explanation.
**Current focus:** Phase 01 — reproducible-world

## Current Position

Phase: 01 (reproducible-world) — EXECUTING
Plan: 1 of 13
Status: Executing Phase 01
Last activity: 2026-08-05 — Phase 01 execution started
`/gsd-plan-review-convergence` (external review by Gemini CLI; Codex quota-blocked until
2026-08-17). 9 HIGH and 12 non-HIGH findings resolved across cycles 1–3; 4 HIGH and 6 non-HIGH
from cycle 3 fixed in a final replan verified by gsd-plan-checker only, with no external review
pass after it. Greenfield; no source code yet.

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 30min | 3 tasks | 22 files |
| Phase 01 P02 | 45min | 3 tasks | 22 files |
| Phase 01 P03 | 30min | 3 tasks | 16 files |
| Phase 01 P04 | 25min | 3 tasks | 8 files |
| Phase 01 P05 | 20min | 3 tasks | 5 files |
| Phase 01 P06 | n/a (interrupted-and-resumed session) | 3 tasks | 9 files |
| Phase 01 P07 | 14min | 3 tasks | 10 files |
| Phase 01 P08 | ~5h | 3 tasks | 17 files |
| Phase 01 P09 | ~4h | 3 tasks | 12 files |
| Phase 01 P10 | 165min | 3 tasks | 11 files |
| Phase 01 P11 | ~2h | 3 tasks | 12 files |

## Accumulated Context

### Decisions

Full log in PROJECT.md Key Decisions (18 locked ADR decisions, 18 proposed, 4 planning decisions).
Decisions most likely to bite during Phase 1:

- Locked AD-12 / proposed TD-10: the simulator is the primary data source; it must be
  import-isolated from `models/`, `decisions/`, `policies/` and `features/`, enforced by
  import-linter in CI (OD-3). If simulator internals reach the models, every result is fake.

- Locked AD-18: data/artifact versioning is **explicitly open** (OD-7 — DVC vs. content-hashed
  store). Ratify by ADR in Phase 1; do not assume DVC because OPEN_DECISIONS recommends it.

- Locked AD-16 / proposed TD-09: time-aware splits only. Random splits on behavioral data are
  banned and leakage tests are mandatory from the first feature table.

- Proposed TD-17: hardcoded business logic is a rejected change. Simulator parameters, feature
  lists, constraints, weights and thresholds all live in schema-validated YAML.

- Planning decision: the 3WD gateway lands in Phase 3, before the learned layer, because promotion
  requires beating the incumbent on decision-level metrics.

- Planning decision (user, 2026-07-24): timing/channel are fixed archetype **parameters** in v1
  (DEC-04) and optimized **dimensions** only in v2 (POL-02).

- [Phase ?]: Package legitimacy checkpoint approved: dvc corrected to github.com/iterative/dvc (seam returned wrong treeverse/lakeFS org); remaining nine core packages confirmed canonical
- [Phase ?]: ruff extend-exclude added for .planning/, docs/, *.md — ruff format by default reformats fenced Python code blocks in Markdown, which broke just lint against planning docs
- [Phase ?]: All ten root planning documents relocated to docs/ via git mv (D-17); OD-1..OD-10 ratified as docs/adr/001-010 (DOC-01), closing the OD-7 open marker in locked AD-18 with DVC + MLflow
- [Phase ?]: [Phase 1 P03] Added config/data_quality.yaml as an eighth per-domain base file (D-21's reject-rate threshold has no home among D-23's seven named domains)
- [Phase ?]: [Phase 1 P03] Added config/profiles/tiny.yaml as a fourth profile (~100 customers/~30d horizon) for unit tests, per RESEARCH.md Wave 0 Gaps
- [Phase ?]: [Phase 1 P03] Profile name is part of the hashed config surface — two different profiles never hash identically even with otherwise-identical content, matching D-24's intent
- [Phase ?]: [Phase 1 P04] Static type checking (mypy) deferred to Phase 2/ENG-02, recorded as a comment inside .github/workflows/ci.yml itself (review LOW-2)
- [Phase ?]: [Phase 1 P04] No carve-out on either import-linter contract; consumers needing an Arrow type annotation use nextmove.storage's public Table alias instead of importing pyarrow directly (review cycle 2 MEDIUM-6)
- [Phase ?]: [Phase 1 P04] SIM-02 transitive re-export edge remains open and unproven by a dedicated fixture; flagged for phase verification before SIM-02 is considered fully closed
- [Phase ?]: [Phase 1 P05] Payload shapes for session_start/session_end/cart_remove/cart_abandon were unspecified in REQUIREMENTS/RESEARCH; designed minimal fields (device, duration_s, sku+quantity, cart_value_cents) matching the plan's strictness conventions
- [Phase ?]: [Phase 1 P05] Event.ts uses plain datetime + explicit field_validator (not pydantic AwareDatetime) so naive-datetime rejection names the field explicitly per plan instruction
- [Phase ?]: [Phase 1 P05] EVENT_ID_NAMESPACE is a fixed, arbitrary hardcoded uuid.UUID constant (not a well-known namespace), documented as never-to-be-regenerated
- [Phase ?]: [Phase 1 P06] write_table/write_part_file derive Arrow schema from the row model class, always nullable=True (matches DuckDB's read_parquet->Arrow output so write_table and write_table_from_parts stay byte-identical); empty-row writes require an explicit row_model= kwarg since Python cannot recover element type from an empty list
- [Phase ?]: [Phase 1 P06] query()/write_query_to_part() table_bindings are name -> Path (caller-resolved Parquet paths), not table-name strings requiring zone resolution
- [Phase ?]: [Phase 1 P06] dvc init run without --no-scm-checks (flag does not exist in dvc 3.67); plain dvc init used since repo already has git
- [Phase ?]: [Phase 1 P07] Truncated normal/lognormal latent-trait draws to a documented 6-sigma window (np.clip) so 'impossible outside configured support' is provably true for every distribution family, not vacuous for the unbounded ones
- [Phase ?]: [Phase 1 P07] category_affinity uses softmax normalization, not literal sum-to-1, because the configured mean-zero normal family can produce a negative or near-zero raw sum across only two categories
- [Phase ?]: [Phase 1 P07] Added SeasonalityConfig.low_class_amplitude_factor and CampaignConfig.discount_bps_min/max to the config schema (Rule 2) -- both required by world-building logic and missing from plan 01-03's schema
- [Phase ?]: [Phase 1 P08] Added ResponseConfig.archetype_base_multiplier and SimulatorConfig.engagement -- plan 01-03's shipped schema had no per-archetype response coefficient or session-occurrence probability field
- [Phase ?]: [Phase 1 P08] EventRow flattens Event.payload to JSON before any storage write -- the storage layer's generic schema deriver cannot handle a 13-member discriminated union
- [Phase ?]: [Phase 1 P08] pyproject.toml's storage import-linter contract gained ignore_imports entries -- the transitive forbidden-import check previously blocked every consumer package from importing nextmove.storage at all
- [Phase ?]: [Phase 1 P08] Rule 1 calibration: restock_probability_per_day 0.08->0.01, add_to_cart_given_view_rate 0.18->0.33, uniform sku selection -> power-law popularity weighting (exponent 3.0) -- proven empirically across six demo-profile runs that shipped values made D-05's UC1 scarcity scenario structurally unreachable
- [Phase ?]: [Phase 1 P09] PipelineStage/RejectRecord physically defined in semantic.py not pipeline.py to break a circular import (pipeline needs run_semantic_gates from semantic; semantic's GateResult needs RejectRecord) -- pipeline.py re-exports both
- [Phase ?]: [Phase 1 P09] Tasks executed in dependency order (2, then 1, then 3) rather than plan-numeric order, forced by the semantic.py/pipeline.py import direction
- [Phase ?]: [Phase 1 P09] Scale-invariant growth budget assertions bound against each run's own observed batch-fill ratio (demo/tiny max_events_part_rows), not customer count -- tiny's total event count is smaller than one VALIDATION_BATCH_SIZE batch
- [Phase ?]: [Phase 1 P10] window_days is a per-transform module constant in definitions.py mirroring config/features.yaml, not read from FeaturesConfig.params at resolve time -- required for FEATURE_SET_VERSION to be a genuine uncalled module constant
- [Phase ?]: [Phase 1 P10] FeatureTransform.sql_expression is a correlated scalar subquery, not the row an ASOF LEFT JOIN itself returns -- a plain ASOF join can't express windowed COUNT/SUM aggregates; the join establishes the inclusive boundary structurally, each transform's subquery re-enforces it independently
- [Phase ?]: [Phase 1 P10] time_aware_split boundary corrected to as_of_ts<=boundary_ts trains / >boundary_ts tests, against the plan's own self-contradictory action-text prose, matching its must_haves.truths and acceptance criteria instead
- [Phase ?]: [Phase 1 P10] Rule 1 bug: naive TIMESTAMP grid literals silently shifted the ASOF boundary by DuckDB's session-local TimeZone (Europe/Vienna here vs UTC on CI) when compared against the TIMESTAMPTZ events.ts column; fixed with explicit +00-offset TIMESTAMPTZ literals -- caught by the leakage suite's explicit boundary test
- [Phase ?]: [Phase 1 P11] dvc.yaml vars.profile default is 'default' (full production scale), not a fast profile -- a bare just reproduce must target the full simulated history per phase success criterion 1
- [Phase ?]: [Phase 1 P11] just reproduce sed-patches dvc.yaml's vars.profile line before dvc repro -- this dvc version has no CLI override for vars: outside dvc exp run
- [Phase ?]: [Phase 1 P11] Zero-row-table proof zeros engagement.base_session_probability and campaigns.send_probability_per_eligible_day rather than n_customers, which is schema-constrained gt=0
- [Phase ?]: [Phase 1 P11] Added tests/integration/test_dvc_pipeline_structure.py and tests/unit/test_ci_workflow_structure.py (not in plan file list) as the permanent home for the plan's own structural acceptance criteria

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 2 size:** Phase 2 carries 19 of 64 requirements. It is the product's core vertical slice
  and should not be split into horizontal layers, but it will need the most plans of any phase.

- **AC-7 widened:** `QUALITY_BAR.md` AC-7 names two segmentation viability criteria; the locked ADR
  mandates four. SEG-02 uses all four. Do not narrow it back when writing the Phase 4 tests.

- **Final Phase 1 replan is unreviewed:** the cycle-3 amendment (commit `f4c788b`) closed 4 HIGH and
  6 non-HIGH findings but was verified by `gsd-plan-checker` only — external reviewer capacity was
  exhausted (Codex quota resets 2026-08-17; Gemini daily quota spent). Re-running
  `/gsd-plan-review-convergence 1` once quota returns would give those fixes an independent pass.
  Highest-risk surface: `01-06` storage API (`write_parquet_stream`, `write_table_from_parts`,
  `write_query_to_part`) and the three memory-budget suites in `01-08`/`01-09`/`01-10`. ENG-08
  failed review in all three cycles, each time in a new disguise.

- [Phase 1 P04] SIM-02 transitive re-export edge (a re-export chain carrying a simulator symbol into a forbidden source package without a direct import) has no dedicated fixture-based proof; raise before phase verification closes SIM-02
- [Phase 1 P06] ENG-08 peak-RSS proof (test_merge_peak_rss_stays_under_budget in tests/golden/test_deterministic_write.py) has never run to completion on this Windows dev machine -- it self-skips (POSIX-only resource module). Must be confirmed passing on Linux CI before ENG-08 is treated as fully proven for this plan.
- [Phase 1 P08] ENG-08 peak-RSS assertion (tests/integration/test_simulation_budget.py TestPeakResidentMemory / scale-invariant RSS-ratio) has never run to completion -- self-skips on this Windows dev machine (POSIX-only resource module), same open item as plan 01-06's peak-RSS test. Must be confirmed passing on Linux CI before ENG-08 is treated as fully proven.
- [Phase 1 P08] just budget profile="default" (50k customers, 548-day horizon) has never been run to completion in this session -- demo-scale (2000 customers) took ~3-4 min uninstrumented, so default scale plausibly takes on the order of an hour. Should be run once before treating the phase's laptop-reproducibility claim as proven at default scale.
- [Phase 1 P09] ENG-08 peak-RSS assertions in tests/integration/test_ingest_budget.py have never run to completion on this Windows dev machine -- self-skip (POSIX-only resource module), same open item as plans 01-06 and 01-08. Must be confirmed passing on Linux CI before ENG-08 is treated as fully proven for the ingest path.
- [Phase 1 P10] ENG-08 peak-RSS assertions in tests/integration/test_features_budget.py (TestPeakResidentMemory / TestScaleInvariantGrowth's RSS half) have never run to completion on this Windows dev machine -- self-skip (POSIX-only resource module), same open item as plans 01-06/01-08/01-09. Must be confirmed passing on Linux CI before ENG-08 is treated as fully proven for the features path.
- [Phase 1 P11] The default-profile (50k customers, 548 days) full pipeline run has never been executed to completion in any session. dvc.yaml's committed default targets it. Should be run once before treating phase success criterion 1 as proven at default scale (same class of open item as plan 01-08's just budget profile=default note).
- [Phase 1 P11] CI's new memory-budget gate (fails on any skipped peak-RSS assertion) has never run on Linux CI yet -- must be confirmed green on the first real CI run before ENG-08's memory bound is treated as measured rather than declared, across all of plans 01-06/01-08/01-09/01-10 and this plan.
- [Phase 1 P12] The G-01-1 two-stage merge fix (write_table_from_parts now runs the dedupe
  window and the sort as two separate DuckDB statements on two separate connections) landed
  in plan 01-12 and is proven at ci scale (three ci-profile table digests byte-identical
  pre/post-change) and against a tight synthetic memory budget (400k-row dedupe merge under a
  monkeypatched 100MB limit). The default-profile run that originally failed
  (.planning/debug/ingest-oom-default-scale.md) has NOT been re-executed, so UAT Test 1
  remains open and must be re-run before phase success criterion 1 is treated as proven.
  Commands for a human to run: `uv run python -m nextmove.simulator --profile default --out
  data/repro_a`, then `uv run python -m nextmove.ingest --profile default --out data/repro_a`,
  then `uv run python -m nextmove.features --profile default --out data/repro_a`, then the
  same three commands with `--out data/repro_b`, then compare the sha256 of every table under
  `raw/`, `canonical/`, `features/` and `ground_truth/` in both roots. Budget ~2.5 hours. Do
  not mark G-01-1 resolved until this has been observed.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-05T02:42:50.060Z
Stopped at: Completed 01-11-PLAN.md (final plan of phase 01)
Resume file: None

Next: `/gsd-execute-phase 1`
