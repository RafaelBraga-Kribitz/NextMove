# NextMove Documentation Index

This directory holds the project's foundation documents and its Architecture Decision Records
(ADRs). All ten foundation documents moved here from the repository root during Phase 1
scaffolding (D-17) via `git mv`, so their commit history is preserved — `git log --follow` still
resolves each file back to its original authoring commits.

## Foundation Documents

| Document | Purpose | Moved from root (D-17) |
|----------|---------|-------------------------|
| [PROJECT_IDENTITY.md](PROJECT_IDENTITY.md) | Who NextMove is for, the core pitch, and the product's identity statement | Yes — Phase 1 |
| [PROJECT_VISION.md](PROJECT_VISION.md) | The long-term vision and the problem space NextMove addresses | Yes — Phase 1 |
| [PRODUCT_CHARTER.md](PRODUCT_CHARTER.md) | UC1/UC2 use cases, MVP scope, measurable objectives, and stretch goals | Yes — Phase 1 |
| [RESEARCH_SYNTHESIS.md](RESEARCH_SYNTHESIS.md) | Synthesis of prior research and the contradictions it resolves | Yes — Phase 1 |
| [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) | The design principles governing product and engineering choices | Yes — Phase 1 |
| [ARCHITECTURAL_DIRECTION.md](ARCHITECTURAL_DIRECTION.md) | The locked system architecture: nine components, package boundaries, MLOps posture | Yes — Phase 1 |
| [TECHNICAL_DIRECTION.md](TECHNICAL_DIRECTION.md) | Proposed technical decisions elaborating the architecture (data, ML ladder, config) | Yes — Phase 1 |
| [DECISION_ENGINE_DESIGN.md](DECISION_ENGINE_DESIGN.md) | The typed `Decision` contract and decision engine inputs/outputs | Yes — Phase 1 |
| [QUALITY_BAR.md](QUALITY_BAR.md) | Acceptance criteria, anti-patterns, technical debt policy, documentation standards | Yes — Phase 1 |
| [OPEN_DECISIONS.md](OPEN_DECISIONS.md) | OD-1 through OD-10 — the open decisions ratified as ADRs below | Yes — Phase 1 |

## Architecture Decision Records

Each ADR ratifies one open decision (OD-1 through OD-10) per DOC-01. All ten are individually
written with genuine Context / Decision / Consequences reasoning — see `tests/unit/test_adr_structure.py`
for the structural floor every ADR must clear.

| ADR | OD | Decision Summary |
|-----|----|--------------------|
| [001-modular-monolith.md](adr/001-modular-monolith.md) | OD-1 | Modular monolith, one container, registry interfaces designed service-ready |
| [002-hybrid-batch-and-on-demand-decisioning.md](adr/002-hybrid-batch-and-on-demand-decisioning.md) | OD-2 | Batch is the operational truth; the same engine also serves on-demand at an arbitrary `as_of_ts` |
| [003-simulator-as-import-isolated-package.md](adr/003-simulator-as-import-isolated-package.md) | OD-3 | Same repository, isolated package, lint-enforced import ban toward models/decisions/policies/features |
| [004-synthetic-decisions-public-data-validation.md](adr/004-synthetic-decisions-public-data-validation.md) | OD-4 | Decisions evaluated in simulation only; public-dataset validation of data engineering is a v2 track |
| [005-attributable-models-only-in-decision-path.md](adr/005-attributable-models-only-in-decision-path.md) | OD-5 | Decision path requires attributions; black-box challengers appear in the comparison study only |
| [006-propensity-delta-uplift-approximation.md](adr/006-propensity-delta-uplift-approximation.md) | OD-6 | MVP approximates uplift as a response-model delta, with the approximation error quantified |
| [007-dvc-and-mlflow-artifact-versioning.md](adr/007-dvc-and-mlflow-artifact-versioning.md) | OD-7 | DVC for data/artifacts, MLflow for runs/models — closes the open marker in AD-18 |
| [008-static-3wd-thresholds.md](adr/008-static-3wd-thresholds.md) | OD-8 | Static 3WD thresholds in MVP, with the threshold interface designed for dynamism |
| [009-three-tier-autonomy.md](adr/009-three-tier-autonomy.md) | OD-9 | Three-tier autonomy (auto-apply / human sign-off / human-only), tiers in `config/autonomy.yaml` |
| [010-fixed-action-archetype-catalog.md](adr/010-fixed-action-archetype-catalog.md) | OD-10 | MVP fixes ~8 action archetypes with small parameter grids; `ActionProvider` registry is the escape hatch |
