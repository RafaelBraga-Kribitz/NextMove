# NextMove — Behavioral Decision Engine for E-commerce Personalization

## What This Is

NextMove is an opinionated, headless behavioral decision engine for mid-market e-commerce. It turns
raw customer events and business context (inventory, margin, campaigns, message fatigue) into
explainable next-best-actions — including the action of doing nothing — and refuses to ship any
policy change that has not survived a three-way (Accept / Reject / Delay) experimentation gateway.

It is built as a portfolio project demonstrating Marketing Data Science and Decision Intelligence
seniority: a Python modular monolith that runs entirely on a laptop, with the ML deliberately
positioned as one component of nine rather than the whole story.

"NextMove" is a working codename and is replaceable without consequence. The durable identity is
the subtitle: *Behavioral Decision Engine for E-commerce Personalization*.

## Core Value

Given a customer state, return the optimal next action — including the action of doing nothing —
ranked by expected incremental constrained profit, with confidence and a manager-readable
explanation.

## Business Context

- **Customer**: A reviewing hiring manager / technical interviewer for a personalization, CRM, or
  growth data-science role. Conceptual buyer in the fiction: a mid-market e-commerce marketing lead.
- **Revenue model**: None. This is a portfolio artifact; its return is interview signal.
- **Success metric**: A reviewer runs `make reproduce` from a clean clone, regenerates
  dataset → features → models → decisions → evaluation report deterministically, and walks the UC1
  scenario end to end (inspect customer → decision → explanation → override → override visible in
  evaluation) in under 5 minutes without touching code.
- **Strategy notes**: `PROJECT_VISION.md` (§3 portfolio positioning), `PROJECT_IDENTITY.md`
  (pitch and differentiation vs. recommenders / CDPs / marketing automation).

## Requirements

Full, ID'd list with acceptance criteria: `.planning/REQUIREMENTS.md` (64 v1 requirements).
The themes below are the Active scope; each maps to exactly one roadmap phase.

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — greenfield. No source code exists.)

### Active

- [ ] A seeded generative simulator producing a mid-market e-commerce world that *responds* to
      actions, with every assumption documented and lint-enforced isolation from the models
- [ ] A canonical append-only event log with Pydantic contracts, quarantine-on-violation, semantic
      pipeline gates, and content-hash lineage
- [ ] Point-in-time-correct feature tables with mandatory leakage tests and time-aware splits only
- [ ] A decision engine emitting the typed `Decision` contract, with `none` and `wait` always in the
      action space and hard constraints that learning can never override
- [ ] Declarative YAML business rules (eligibility, frequency caps, inventory gates, discount
      ceilings, brand safety) evaluated into a fired-rule trace
- [ ] Deterministic, template-composed explanations from attributions + fired constraints +
      runner-up counterfactual — no LLM anywhere in the decision or explanation path
- [ ] A `/v1` REST surface where the `Decision` object is the versioned public contract, plus an
      override endpoint, serving both on-demand and batch invocation from one engine
- [ ] A three-way (Accept / Reject / Delay) experimentation gateway with MDE, indifference margin,
      and delay-budget escalation to human review
- [ ] Policy replay and comparison on cumulative constrained profit with confidence intervals
- [ ] Calibrated GBM response/propensity models with SHAP attributions, model cards, and promotion
      gated on decision-level metrics rather than AUC
- [ ] MCDA-selected segmentation (TOPSIS / PROMETHEE II over K-means, GMM, BIRCH) under four
      business viability constraints, with cold-start routing
- [ ] `make reproduce` on a clean clone plus a thin demo surface that walks UC1 and UC2 without code

### Out of Scope

Reasoning preserved from `PROJECT_VISION.md` §5 (ten non-goals) — these boundaries are load-bearing
and rejecting re-adds is policy, not preference.

- **Amazon-scale recommendation infrastructure** — no distributed serving, no vector databases at
  scale, no sub-10ms SLAs. The stated buyer cannot afford it and it teaches nothing here.
- **A production CDP replacement** — no identity resolution across devices, no consent-management
  platform, no connector marketplace. NextMove assumes the data problem is roughly solved and owns
  the layer CDPs delegate.
- **A generic, domain-agnostic AI/ML framework** — the action catalog, utility function, and
  constraint vocabulary are e-commerce-native by design. Feature requests that generalize the
  domain are rejected by policy.
- **An autonomous marketing agent** — no action is executed without a human-approvable surface.
- **Real-time in-session UI mutation at scale** — real-time adaptation is a stretch goal simulated
  offline; the MVP decides at batch / near-line cadence.
- **Live LLM-generated UI (GenUI) in the core path** — at most an optional, guarded plugin serving
  pre-generated, catalog-validated content.
- **A front-end product** — the engine is headless; the dashboard is a thin, disposable demo client
  with zero privileged access.
- **Deep-learning maximalism** — neural models appear only where the comparison teaches something.
- **Real personal data** — synthetic-but-realistic simulator only. No scraping, no PII, no GDPR
  exposure.
- **Multi-tenant SaaS concerns** — auth, billing, and tenancy are out of scope.
- **Not even stretch**: real-time serving infrastructure, deep reinforcement learning, federated
  learning, live LLM UI generation.
- **Rejected alternative architectures**: streaming decisioning (Kafka/Redpanda + online features +
  real-time bandit serving) — high complexity, unneeded scalability, superficially flashy and
  substantively thin; notebook-and-library research repo — violates production realism and the
  anti-pattern list.

## Context

**Origin.** This project was bootstrapped from ten pre-existing planning documents at the repo root
(`PROJECT_VISION`, `PROJECT_IDENTITY`, `DESIGN_PRINCIPLES`, `RESEARCH_SYNTHESIS`, `PRODUCT_CHARTER`,
`ARCHITECTURAL_DIRECTION`, `TECHNICAL_DIRECTION`, `DECISION_ENGINE_DESIGN`, `QUALITY_BAR`,
`OPEN_DECISIONS`) via `/gsd-ingest-docs`. Synthesized intel lives in `.planning/intel/`; the
conflict report and its one user-resolved warning live in `.planning/INGEST-CONFLICTS.md`.

**Greenfield.** No source code exists. Everything is built from zero.

**Why the simulator is load-bearing.** No public dataset contains action→response counterfactuals
with business context, so decision evaluation is impossible without a generative world that
responds to actions. The simulator is therefore the primary data source *and* the primary
credibility risk. Four honesty rules bound it: (1) every generative assumption is written down in
`SIMULATOR_ASSUMPTIONS.md`; (2) simulator response functions are never importable by models —
models see only events; (3) every headline result is labeled "in simulation"; (4) an optional
public-clickstream adapter demo (v2) validates that the pipelines run on non-synthetic shapes.

**Economic frame.** The value function is incremental profit under constraints, not conversion:
`expected_uplift × margin − incentive_cost − operational_cost`, subject to inventory, campaign,
frequency-cap, and trust constraints. Every design choice flows from this.

**Research grounding.** An 18-source corpus (anchor: Wasilewski & Ramsey 2025, IEEE Access —
adaptive e-commerce UI personalization validated on 438,261 + 99,193 real sessions, +27.6% CR and
+68.1% AOV in one cluster) yields four differentiators the corpus does not currently offer as an
integrated system: an automated 3WD experimentation gateway (named a "massive gap in the MLOps
ecosystem" and the project's flagship differentiator), business-constrained MCDA evaluation
wrappers around standard algorithms, decision-level explanation composition, and restraint as a
first-class action.

**Personas the system must serve.** P1 Marketing/CRM manager (reads decision cards, approves and
overrides, sets constraints; will not read a notebook) · P2 E-commerce product manager (consumes
3WD verdicts, configures MDE and indifference margins) · P3 Data scientist (extends registries,
runs offline evaluation and replay via Python API and config) · P4 CRM specialist (consumes
per-customer action feeds exported from the decision API).

**Known open item.** OD-7 (data/artifact versioning: DVC vs. content-hashed artifact store) is
deliberately left open inside the locked ADR. It must be ratified during Phase 1, not assumed.

## Constraints

- **Tech stack**: Python modular monolith; FastAPI (`/v1` REST); DuckDB as the local analytical
  store with an optional Postgres adapter; Pydantic for all contracts; scikit-learn +
  XGBoost/LightGBM; SHAP; MLflow (local) for experiment tracking; DVC *or* a content-hashed
  artifact store (open, OD-7). — Chosen for laptop-scale operability and reviewer legibility.
  SQLite rejected (weak analytical SQL); Kafka rejected (non-goal); Drools rejected (JVM heft);
  Feast rejected for MVP (complexity without payoff, interface must not preclude it).
- **Platform**: Runs entirely on one laptop. One deployable API container. Makefile/justfile is the
  operational interface. No cloud, no orchestration platform, no streaming infrastructure. —
  Production realism at the stated scale; architecture astronautics is a listed anti-pattern.
- **Package boundaries**: `simulator / ingest / features / segmentation / models / rules /
  decisions / policies / explain / evaluate / api`, enforced by import-linter in CI. The simulator
  must never be importable from the decision path. — If simulator internals reach the models, every
  result is fake.
- **Determinism**: Seeds everywhere including exploration; content-hashed lineage on derived tables;
  golden-file tests on `Decision` objects; identical inputs must yield byte-identical outputs. —
  Reproducibility is the portfolio claim.
- **Evaluation**: Time-aware splits only. Random splits on behavioral time series are banned and
  leakage tests are mandatory. — The canonical mistake flagged across the research corpus.
- **Explainability**: No LLM in the decision or explanation path. Models without usable attributions
  are inadmissible in the decision path (they may still appear in the comparison study).
  Explanations use relevance framing, never surveillance framing. — Determinism and honesty outrank
  fluency; surveillance framing triggers reactance and churn.
- **Configuration**: Action catalogs, constraints, utility weights, MCDA criteria and weights, 3WD
  thresholds, segmentation constraints, and feature lists are all schema-validated YAML. Hardcoded
  business logic is a rejected change; the only business numbers in code are overridable defaults. —
  Changing business posture must not require a deploy.
- **Performance**: Single-decision API response under 500 ms on a laptop. — Adequate for batch and
  near-line marketing decisions; real-time UI serving is explicitly out of MVP scope.
- **Testing**: `rules/`, `decisions/`, `evaluate/` at ≥ 85% line coverage; overall ≥ 75%. Unit,
  property-based, integration, and golden-file layers all required. — The decision path carries the
  product's entire trust budget.
- **Honesty**: No business impact stated without its simulation caveat; no invented percentages;
  every headline number traces to an MLflow run ID; single-metric victory laps are prohibited —
  any improvement claim must cite the three-axis report.

## Key Decisions

### Locked (ADR — `ARCHITECTURAL_DIRECTION.md`, 18 decisions)

These cannot be auto-overridden. Changing one requires a superseding ADR.

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| AD-01 — Nine-component architecture; ML is one box; the Evaluation & 3WD gateway closes the loop back into the feature layer | The product is the decision system, not the model | — Pending |
| AD-02 — Event ingestion on Python + Pydantic into DuckDB (optional Postgres adapter) | Laptop-scale analytical SQL; SQLite and Kafka rejected | — Pending |
| AD-03 — Feature layer as versioned SQL + Python transforms, feature definitions in config, keyed `(customer_id, as_of_ts)` | Point-in-time correctness without a feature store's complexity | — Pending |
| AD-04 — Segmentation method selected by MCDA (TOPSIS + PROMETHEE II) over ≥ K-means, GMM, BIRCH under min size / max clusters / activity diversity / compute cost | Context-free metrics produce economically unviable segments | — Pending |
| AD-05 — Calibrated model ladder: rules baseline → XGBoost/LightGBM → optional shallow NN; calibration is mandatory | Uncalibrated probabilities make expected-value ranking meaningless | — Pending |
| AD-06 — The decision engine emits the typed `Decision` object; detailed contract delegated to `DECISION_ENGINE_DESIGN.md` | One contract, one owner | — Pending |
| AD-07 — Business rules as declarative versioned YAML over a small internal evaluator | Drools / production rule engines rejected as JVM heft | — Pending |
| AD-08 — Expected-value ranking with uncertainty penalties in MVP; contextual bandit is a guardrailed stretch | Ship a policy that can be explained before one that adapts | — Pending |
| AD-09 — No LLM in the explanation path; SHAP + deterministic templates | Determinism and honesty outrank fluency | — Pending |
| AD-10 — Evaluation and 3WD gateway: offline policy comparison, Accept/Reject/Delay adjudication, feedback triggers | Binary A/B is insufficient for multi-metric commerce decisions | — Pending |
| AD-11 — The API is the product boundary; the dashboard is disposable | Headless is the architectural claim | — Pending |
| AD-12 — The simulator is a cross-cutting component with a documented assumption log | No public dataset has action→response counterfactuals | — Pending |
| AD-13 — Eight typed plugin registries (`ActionProvider`, `Model`, `Policy`, `Constraint`, `ClusteringCandidate`, `MCDAMethod`, `IngestAdapter`, `Explainer`); adding one of each requires zero core changes, acceptance-tested | Extensibility must be demonstrated, not asserted | — Pending |
| AD-14 — Modular monolith: ten packages in one repo, storage behind a thin repository layer, API versioned `/v1` | Services add operational surface with zero payoff at this scale | — Pending |
| AD-15 — Relevance framing, never surveillance framing; per-decision manager-readable reasoning plus a structured trace; confidence reported verbally *and* numerically; low confidence degrades to safe defaults | Explanation is a trust-load-bearing feature | — Pending |
| AD-16 — Time-aware evaluation only; calibration curves; policy replay with constrained profit and regret; MCDA weight sensitivity; mandatory per-release failure analysis | Random splits on behavioral data are the canonical corpus mistake | — Pending |
| AD-17 — MLOps posture: MLflow local, git for code/config, model registry with cards, one `make reproduce`, CI miniature end-to-end, containerized API, no orchestration platform | Reproducibility is the portfolio claim | — Pending |
| AD-18 — Data and artifact versioning left **OPEN** (`[Open: OD-7]`) — DVC vs. content-hashed store | The locked ADR deliberately asserts no choice | ⚠️ Revisit — ratify in Phase 1 |

### Proposed (`TECHNICAL_DIRECTION.md`, 18 decisions — not yet ratified)

Substantively consistent with the locked ADR set; the gap is procedural. Full text:
`.planning/intel/decisions.md` (ADR-TD-01..18). Ratify alongside OD-1..OD-10 in Phase 1.

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TD-01/02 — Modular monolith, not services; every registry interface designed as if it could become a service, none is one now | OD-1: services add ops surface with zero payoff | — Proposed |
| TD-03/04 — Batch DAG plus a thin synchronous read path, no streaming; no component reaches around another's contract | Corpus consensus is offline-heavy / online-light | — Proposed |
| TD-05/06/07/08 — Contracts first with quarantine on violation; canonical event schema with inward-only adapters; content-hash lineage printed in the evaluation report; quality checks as pipeline gates | Data credibility is the foundation of every later claim | — Proposed |
| TD-09 — Point-in-time correctness is non-negotiable; leakage tests in the suite | The canonical mistake in behavioral ML | — Proposed |
| TD-10 — Simulator is the primary data source under four honesty rules | Counterfactuals no public dataset provides | — Proposed |
| TD-11/13/14 — Classical-first ML ladder; selection order = decision value → calibration → explanation → prediction metrics → cost; non-attributable models inadmissible in the decision path | Each rung must earn its place | — Proposed |
| TD-12/15/16 — Promotion requires beating the incumbent on decision-level replay profit, not AUC; utility = expected uplift × margin − cost − risk penalty; models propose, rules dispose, evaluation decides what survives | The governing asymmetry of the engine | — Proposed |
| TD-17/18 — Configuration as data (hardcoded business logic is a rejected PR); REST `/v1` with `Decision` as the versioned public contract, model versions and config hash embedded in every response | Behavior changes are config changes | — Proposed |

### Project-level decisions made during planning

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Timing/channel **split** into MVP-as-fixed-archetype-parameter vs. stretch-as-optimized-dimension | Reconciles PRODUCT_CHARTER UC1 and the SPEC `Decision` contract (which need timing/channel present) with the locked ADR (which defers timing/channel *decision dimensions*) — the distinction is present-as-parameter vs. optimized-as-dimension | ✓ Good — user-resolved 2026-07-24 |
| The segmentation viability gate covers **all four** locked criteria (min size, max clusters, activity diversity, compute cost) | `QUALITY_BAR.md` AC-7 names only two and therefore under-tests the locked ADR; widen the gate rather than narrow the requirement | ✓ Good |
| The 3WD gateway lands in Phase 3, **before** the learned layer | Promotion requires beating the incumbent on decision-level metrics — you cannot promote a model without the gateway existing. Also keeps the flagship differentiator out of a final polish phase | — Pending |
| OD-1..OD-10 ratified as ADR-001..010 as a **Phase 1 deliverable**, not a planning blocker | Their recommendations are already substantively consistent with the locked ADR content; the gap is procedural | — Pending |

---
*Last updated: 2026-07-24 after initial project definition from `/gsd-ingest-docs` synthesis*
