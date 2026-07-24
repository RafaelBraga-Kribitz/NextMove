# Synthesis Summary

Entry point for `gsd-roadmapper`. Produced by `gsd-doc-synthesizer` from 10 classified docs.

- **Mode:** new (no pre-existing `.planning/` context)
- **Precedence:** ADR > SPEC > PRD > DOC (default; no per-doc overrides present)
- **Project:** NextMove — Behavioral Decision Engine for E-commerce Personalization

---

## Doc counts by type

| Type | Count | Sources |
|---|---|---|
| ADR | 2 | ARCHITECTURAL_DIRECTION.md (locked), TECHNICAL_DIRECTION.md |
| SPEC | 2 | QUALITY_BAR.md, DECISION_ENGINE_DESIGN.md |
| PRD | 1 | PRODUCT_CHARTER.md |
| DOC | 5 | OPEN_DECISIONS.md, RESEARCH_SYNTHESIS.md, DESIGN_PRINCIPLES.md, PROJECT_IDENTITY.md, PROJECT_VISION.md |

All 10 classifications were `high` confidence with `manifest_override: true`. No UNKNOWN types. No docs excluded from synthesis.

## Cycle detection

Three-color DFS over the `cross_refs` graph: **0 cycles**, 10 nodes, max traversal depth 3 (cap 50), 5 dangling external refs excluded.

The two cycles reported in the previous run are confirmed broken — `QUALITY_BAR.md` no longer back-references `OPEN_DECISIONS`. Re-verified against the source text, not assumed.

## Decisions

**18 locked** (all from `ARCHITECTURAL_DIRECTION.md`, ADR-AD-01..18) + **18 proposed** (all from `TECHNICAL_DIRECTION.md`, ADR-TD-01..18) = 36 decision entries.

Locked highlights: nine-component architecture with ML as one box; DuckDB + Pydantic ingestion (SQLite and Kafka rejected); MCDA-selected segmentation via TOPSIS/PROMETHEE II over K-means/GMM/BIRCH; mandatory calibration; internal YAML rule evaluator (Drools rejected); expected-value ranking in MVP with guardrailed bandit as stretch; **no LLM in the explanation path**; API is the product boundary and the dashboard is disposable; eight typed plugin registries requiring zero core changes; relevance-framed (never surveillance-framed) explanations; time-aware splits only.

One locked decision is an explicit deferral: **ADR-AD-18** leaves artifact versioning open (`[Open: OD-7]`).

Proposed highlights: modular monolith (OD-1); batch DAG plus thin synchronous read path, no streaming; canonical event schema with inward-only adapters; point-in-time correctness non-negotiable; simulator as primary data source under four honesty rules (OD-4); classical-first ML ladder; promotion on decision-level metrics not AUC; configuration-as-data with hardcoded business logic as a rejected PR; `/v1` REST surface with `Decision` as the versioned public contract.

→ `.planning/intel/decisions.md`

## Requirements

**37 extracted** from the single PRD (`PRODUCT_CHARTER.md`), including 2 competing variants.

- Objectives: `REQ-decision-not-prediction`, `REQ-beat-naive-policies`, `REQ-business-viable-segmentation`, `REQ-safe-experimentation-3wd`, `REQ-explainable-by-default`, `REQ-reproducible-pipeline`
- Success metrics: `REQ-demo-workflow-walkthrough`, `REQ-decision-quality-restraint`, `REQ-adoption-proxy-readme`, `REQ-model-performance-reporting`, `REQ-decision-performance-reporting`, `REQ-api-latency`, `REQ-reliability-reproducibility-ci`, `REQ-portfolio-artifacts`
- Personas: `REQ-persona-surfaces`
- Use cases: `REQ-uc1-next-best-action` (flagship), `REQ-uc2-do-nothing-wait`, `REQ-uc3-segment-interface-decision`, `REQ-uc4-experiment-adjudication`, `REQ-uc5-cold-start-routing`, `REQ-uc6-override-as-feedback`, `REQ-uc7-policy-comparison`, `REQ-edge-case-handling`
- MVP scope: `REQ-mvp-event-ingestion`, `REQ-mvp-feature-layer`, `REQ-mvp-predictive-models`, `REQ-mvp-segmentation`, `REQ-mvp-decision-engine`, `REQ-mvp-explanation-layer`, `REQ-mvp-evaluation-framework`, `REQ-mvp-headless-api-demo`, `REQ-mvp-engineering-floor`
- **Competing variants (unresolved):** `REQ-timing-channel-v1` (stretch) vs `REQ-timing-channel-v2` (MVP)
- Stretch: `REQ-stretch-contextual-bandit`, `REQ-stretch-dynamic-3wd-thresholds`, `REQ-stretch-uplift-modeling`, `REQ-stretch-longitudinal-cohort`, `REQ-stretch-content-plugin`, `REQ-stretch-adapters`
- Exclusions: `REQ-explicit-exclusions`

Note: `REQ-decision-quality-restraint` carries an unspecified threshold — the source states ">= X%" with "X reported, not invented". Marked absent rather than fabricated.

→ `.planning/intel/requirements.md`

## Constraints

**33 extracted** from 2 SPECs.

Type breakdown: `protocol` 11 · `nfr` 15 · `api-contract` 4 · `schema` 3

- From `DECISION_ENGINE_DESIGN.md` (13): objective function, restraint as first-class action, counterfactual scoring, hard/soft constraint separation, uncertainty intervals, three input-context schemas, the `Decision` public contract and its rules, the 7-stage pipeline, constraint precedence (`compliance > inventory > campaign > preference`), and six engine design rules.
- From `QUALITY_BAR.md` (20): AC-1..AC-14, Definition of Done, 10 prohibited anti-patterns, technical debt policy, documentation standards, human evaluation rubric.

→ `.planning/intel/constraints.md`

## Context topics

**16 topics** from 5 DOCs: open decisions OD-1..OD-10; alternative architectures A/B/C; pre-planning verification; research corpus (18 sources); 12 distilled research principles; 5 consensus findings; 7 resolved trade-offs (T1–T7); 6 research gaps; 8 design principles; product identity and pitch; differentiation vs recommenders/CDPs/marketing automation; why the project exists; portfolio positioning; business problem and economic frame; non-goals; evidence tag convention.

→ `.planning/intel/context.md`

## Conflicts

- **0 blockers**
- **1 competing variant** — timing/channel as MVP vs stretch (locked ADR and PRD stretch list say optional; PRD flagship UC1, the SPEC Decision contract, and OD-10 archetypes put them in MVP). Both variants preserved; synthesis did not pick.
- **8 auto-resolved / informational** — cycle-detection clean; locked ADR > PRD on minimum clustering candidates (>=3 vs >=2); ADR > DOC on API invocation mode (hybrid wins over read-cache-only); SPEC > PRD on the beat-the-baseline criterion (AC-6 honest-negative escape hatch stands); locked ADR > SPEC on the segmentation viability constraint list (AC-7 under-tests); OD-7 left open inside the locked ADR; OD-1..OD-10 unratified but substantively non-contradictory; 5 cross-refs pointing outside the ingest set.

→ `.planning/INGEST-CONFLICTS.md`

## Status

**AWAITING USER** — no blockers, but one competing variant (`REQ-timing-channel`) needs resolution before routing.
