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

## Delivery, evaluation and operations documents

| Document | Purpose |
|----------|---------|
| [MILESTONES.md](MILESTONES.md) | The finish-and-polish plan (ADR-011) and the explicit "Later" list |
| [STATUS_LOG.md](STATUS_LOG.md) | Item-by-item progress log |
| [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md) | AC-1 … AC-14 mapped to the test or artifact that proves each |
| [EXPLANATION_STYLE_GUIDE.md](EXPLANATION_STYLE_GUIDE.md) | Rules for the manager-readable `reasoning` paragraph |
| [RUNBOOK.md](RUNBOOK.md) | How to run, check and troubleshoot the pipeline |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | The 5-minute UC1 walkthrough |
| [api/decision.schema.json](api/decision.schema.json), [api/openapi.json](api/openapi.json) | Public contract and API reference |
| [../reports/demo/evaluation/evaluation_report.md](../reports/demo/evaluation/evaluation_report.md) | Three-axis evaluation report (simulated) |
| [../reports/demo/evaluation/model_cards/](../reports/demo/evaluation/model_cards/) | Model cards |
| [../reporting/powerbi/README.md](../reporting/powerbi/README.md) | Power BI build kit |
| [../DEBT.md](../DEBT.md) | Technical debt register |

## Architecture Decision Records

ADR-001 … ADR-010 each ratify one open decision (OD-1 through OD-10) per DOC-01; ADR-011 and
ADR-012 record the delivery scope and the evaluation design. All are individually
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
| [011-portfolio-scope-for-hiring-market.md](adr/011-portfolio-scope-for-hiring-market.md) | — | Finish a thin vertical slice; SQL mart and Power BI kit; weak spots measured openly |
| [012-simulated-evaluation-design.md](adr/012-simulated-evaluation-design.md) | — | Randomized experiment, outcome oracle, common random numbers, temporal windows, `demo` as published profile |
