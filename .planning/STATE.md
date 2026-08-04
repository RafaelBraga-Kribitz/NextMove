---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_phase_name: reproducible-world
status: executing
stopped_at: Completed 01-04-PLAN.md
last_updated: "2026-08-04T16:35:15.164Z"
last_activity: 2026-08-04
last_activity_desc: Phase 01 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 11
  completed_plans: 4
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
Plan: 5 of 11
Status: Ready to execute
Last activity: 2026-08-04 — Phase 01 execution started
`/gsd-plan-review-convergence` (external review by Gemini CLI; Codex quota-blocked until
2026-08-17). 9 HIGH and 12 non-HIGH findings resolved across cycles 1–3; 4 HIGH and 6 non-HIGH
from cycle 3 fixed in a final replan verified by gsd-plan-checker only, with no external review
pass after it. Greenfield; no source code yet.

Progress: [████░░░░░░] 36%

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

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-04T16:35:15.155Z
Stopped at: Completed 01-04-PLAN.md
Resume file: None

Next: `/gsd-execute-phase 1`
