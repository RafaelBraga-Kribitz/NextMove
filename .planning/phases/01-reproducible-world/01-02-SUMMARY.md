---
phase: 01-reproducible-world
plan: 02
subsystem: docs
tags: [adr, documentation, governance, decision-records]

# Dependency graph
requires:
  - phase: 01-reproducible-world (plan 01)
    provides: uv-managed Python 3.12 project, src/nextmove/ package boundaries, justfile/Makefile interface
provides:
  - docs/ foundation corpus (ten relocated planning documents, history preserved via git mv)
  - docs/adr/001-*.md through docs/adr/010-*.md — all ten open decisions (OD-1..OD-10) ratified
  - docs/README.md index mapping the relocated corpus and the ten ADRs
  - tests/unit/test_adr_structure.py — structural floor test preventing ADR stubs
affects: [phase-02-decision-engine, phase-03-evaluation-gateway, all-future-phases-citing-OD-or-AD-decisions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ADR heading contract: `## Status` / `## Context` / `## Decision` / `## Consequences` / `## Alternatives Considered`, enforced by tests/unit/test_adr_structure.py"

key-files:
  created:
    - docs/README.md
    - docs/adr/001-modular-monolith.md
    - docs/adr/002-hybrid-batch-and-on-demand-decisioning.md
    - docs/adr/003-simulator-as-import-isolated-package.md
    - docs/adr/004-synthetic-decisions-public-data-validation.md
    - docs/adr/005-attributable-models-only-in-decision-path.md
    - docs/adr/006-propensity-delta-uplift-approximation.md
    - docs/adr/007-dvc-and-mlflow-artifact-versioning.md
    - docs/adr/008-static-3wd-thresholds.md
    - docs/adr/009-three-tier-autonomy.md
    - docs/adr/010-fixed-action-archetype-catalog.md
    - tests/unit/test_adr_structure.py
  modified: []

key-decisions:
  - "All ten root planning documents relocated to docs/ via git mv (D-17); repository root now holds only tooling files"
  - "OD-1, 2, 3, 5, 6, 8, 10 ratified as recommended without re-litigation, each citing its already-locked AD-* precedent (D-11)"
  - "OD-4 ratified as recommendation B: decisions stay simulation-only; public-dataset validation of data engineering is explicit v2 scope, no dataset named (D-13)"
  - "OD-7 ratified as DVC + MLflow, closing the open marker in locked AD-18, with reviewer recognizability as the stated deciding factor (D-09)"
  - "OD-9 ratified as three-tier autonomy (auto-apply / human sign-off / human-only), tier membership in schema-validated config/autonomy.yaml (D-12)"

patterns-established:
  - "ADR structural floor: every ADR needs >=25 non-blank lines and non-empty Status/Context/Decision/Consequences sections, enforced by a parametrized pytest suite over all ten files"

requirements-completed: [DOC-01]

coverage:
  - id: D1
    description: "Ten root planning documents relocated to docs/ with git history preserved (git mv, not copy-delete)"
    requirement: "DOC-01"
    verification:
      - kind: unit
        ref: "manual shell verification: git log --follow --oneline -- docs/QUALITY_BAR.md returns 2 commits; git status showed R (rename) not D+??"
        status: pass
    human_judgment: false
  - id: D2
    description: "All ten open decisions (OD-1..OD-10) ratified as individually-written ADRs docs/adr/001-*.md through 010-*.md with genuine Context/Decision/Consequences prose"
    requirement: "DOC-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_adr_structure.py::test_adr_file_exists_exactly_once[001..010]"
        status: pass
      - kind: unit
        ref: "tests/unit/test_adr_structure.py::test_adr_has_required_headings[001..010]"
        status: pass
      - kind: unit
        ref: "tests/unit/test_adr_structure.py::test_adr_section_bodies_are_non_empty[001..010]"
        status: pass
      - kind: unit
        ref: "tests/unit/test_adr_structure.py::test_adr_meets_minimum_length_floor[001..010]"
        status: pass
      - kind: unit
        ref: "tests/unit/test_adr_structure.py::test_adr_filenames_sort_lexicographically_in_decision_order"
        status: pass
    human_judgment: false
  - id: D3
    description: "ADR 007 explicitly closes the OD-7 open marker in locked AD-18, names DVC + MLflow, and states reviewer recognizability as the deciding factor"
    requirement: "DOC-01"
    verification:
      - kind: unit
        ref: "shell: grep -lF 'AD-18' docs/adr/007-dvc-and-mlflow-artifact-versioning.md; grep -iF 'recogniz' docs/adr/007-dvc-and-mlflow-artifact-versioning.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "ADR 009 defines all three autonomy tiers concretely and points at config/autonomy.yaml"
    requirement: "DOC-01"
    verification:
      - kind: unit
        ref: "shell: grep -cF 'Tier 3' docs/adr/009-three-tier-autonomy.md; grep -F 'config/autonomy.yaml' docs/adr/009-three-tier-autonomy.md"
        status: pass
    human_judgment: false
  - id: D5
    description: "docs/README.md indexes all ten relocated documents and all ten ADRs by filename"
    requirement: "DOC-01"
    verification:
      - kind: unit
        ref: "manual review of docs/README.md against ls docs/adr/*.md output (10 files, exact filename match)"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-04
status: complete
---

# Phase 1 Plan 2: Documentation Relocation and ADR Ratification Summary

**All ten open decisions (OD-1..OD-10) ratified as individually-written ADRs under `docs/adr/`, and the ten root planning documents relocated to `docs/` via `git mv` with history preserved, closing DOC-01 and the OD-7 open marker inside locked decision AD-18.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-08-04T16:00:00Z (approx.)
- **Completed:** 2026-08-04T16:45:00Z (approx.)
- **Tasks:** 3
- **Files modified:** 22 (11 renamed, 11 created)

## Accomplishments

- Relocated all ten root planning documents (`ARCHITECTURAL_DIRECTION.md`, `DECISION_ENGINE_DESIGN.md`, `DESIGN_PRINCIPLES.md`, `OPEN_DECISIONS.md`, `PRODUCT_CHARTER.md`, `PROJECT_IDENTITY.md`, `PROJECT_VISION.md`, `QUALITY_BAR.md`, `RESEARCH_SYNTHESIS.md`, `TECHNICAL_DIRECTION.md`) into `docs/` using `git mv`, confirmed by 100%-similarity renames and `git log --follow` resolving pre-move commits.
- Wrote `docs/README.md` indexing the relocated corpus (with one-line purpose per document) and all ten ADRs (with OD number and decision summary per ADR).
- Ratified OD-1 through OD-5 as `docs/adr/001-*.md` through `005-*.md`: modular monolith (OD-1), hybrid batch/on-demand decisioning (OD-2), import-isolated simulator package (OD-3), synthetic decisions + v2 public-data validation track (OD-4), attributable-models-only decision path (OD-5).
- Ratified OD-6 through OD-10 as `docs/adr/006-*.md` through `010-*.md`: propensity-delta uplift approximation (OD-6), DVC + MLflow artifact versioning explicitly closing AD-18's open marker (OD-7), static 3WD thresholds (OD-8), three-tier autonomy with tiers in `config/autonomy.yaml` (OD-9), fixed ~8 action archetype catalog (OD-10).
- Wrote `tests/unit/test_adr_structure.py`: a parametrized structural-floor test asserting exactly one file per OD number, all four required headings present with non-empty section bodies, a 25-non-blank-line minimum per ADR, and a filename-ordering test proving zero-padding keeps lexicographic and numeric sort identical.

## Task Commits

Each task was committed atomically:

1. **Task 1: Relocate the ten planning documents into docs/ with history preserved** - `be4c527` (docs)
2. **Task 2: Write ADRs 001-005 ratifying OD-1 through OD-5** - `e44616e` (docs)
3. **Task 3: Write ADRs 006-010 and the ADR structure test** - `b37116f` (docs)

**Plan metadata:** pending (this SUMMARY + STATE/ROADMAP update commit)

## Files Created/Modified

- `docs/README.md` - Index of the ten relocated foundation documents and the ten ADRs
- `docs/ARCHITECTURAL_DIRECTION.md` ... `docs/TECHNICAL_DIRECTION.md` - Ten documents relocated from repo root via `git mv` (content unchanged, including the untouched `[Open: OD-7]` marker in `ARCHITECTURAL_DIRECTION.md` §8)
- `docs/adr/001-modular-monolith.md` - Ratifies OD-1 as modular monolith, cites AD-14
- `docs/adr/002-hybrid-batch-and-on-demand-decisioning.md` - Ratifies OD-2 as batch-truth + synchronous invocation, cites AD-11/TD-03/TD-04
- `docs/adr/003-simulator-as-import-isolated-package.md` - Ratifies OD-3, names the four forbidden source packages plus `nextmove.simulator`, cites AD-12
- `docs/adr/004-synthetic-decisions-public-data-validation.md` - Ratifies OD-4 as recommendation B, states validation track is v2 with no dataset named
- `docs/adr/005-attributable-models-only-in-decision-path.md` - Ratifies OD-5, cites AD-09/AD-15
- `docs/adr/006-propensity-delta-uplift-approximation.md` - Ratifies OD-6, cites AD-08
- `docs/adr/007-dvc-and-mlflow-artifact-versioning.md` - Ratifies OD-7, closes AD-18's open marker, states recognizability rationale and DATA-04 content-hash implication
- `docs/adr/008-static-3wd-thresholds.md` - Ratifies OD-8, cites AD-10
- `docs/adr/009-three-tier-autonomy.md` - Ratifies OD-9, defines all three tiers, points at `config/autonomy.yaml`
- `docs/adr/010-fixed-action-archetype-catalog.md` - Ratifies OD-10, cites AD-06, references the resolved timing/channel split (DEC-04)
- `tests/unit/test_adr_structure.py` - Structural floor test over all ten ADRs plus a filename-ordering test

## Decisions Made

None beyond what the plan and D-09/D-10/D-11/D-12/D-13/D-17 already specified — this plan's job was to write down decisions already made in `01-CONTEXT.md`, not to make new ones. All ten ADRs follow the identical five-heading structure (`## Status` / `## Context` / `## Decision` / `## Consequences` / `## Alternatives Considered`) established in `docs/adr/001-modular-monolith.md` and reused verbatim across the other nine.

## Deviations from Plan

None - plan executed exactly as written.

One incidental formatting fix during verification: `ruff format` flagged one line-wrap style issue in the freshly written `tests/unit/test_adr_structure.py` (a list comprehension exceeding the project's configured line length in its unformatted form); `uv run ruff format` reformatted it in place before commit. This is routine formatting, not a logic or scope change, and is folded into the Task 3 commit rather than tracked as a separate deviation.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DOC-01 is fully satisfied: all ten ODs ratified, structural test green, `docs/README.md` current.
- The Phase 1 blocker recorded in STATE.md ("OD-1..OD-10 are formally unratified") is now resolved — Phase 1's fifth success criterion (a reviewer can find every ratified open decision written down) is met.
- OD-7's genuine resolution (DVC + MLflow) is now available to inform plan 01-06+ storage/artifact-versioning work, which was flagged in STATE.md as the highest-risk unreviewed surface from the Phase 1 replan.
- `config/autonomy.yaml` is now a named, ADR-referenced deliverable for plan 01-03 (config scaffolding) — ADR 009 depends on that file existing with the three tiers it defines.
- `just lint` and `just test` both exit 0 after this plan's changes (44 tests passing, up from 01-01's baseline).

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*

## Self-Check: PASSED

All 12 created/relocated files confirmed present on disk (docs/README.md, all ten docs/adr/*.md
files, tests/unit/test_adr_structure.py). All three task commits (be4c527, e44616e, b37116f)
confirmed present in git history.
