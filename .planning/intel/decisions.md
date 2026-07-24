# Decisions (ADR intel)

Extracted from classified ADR sources. Paths are relative to project root.
Precedence: ADR > SPEC > PRD > DOC. Entries marked `locked` cannot be auto-overridden.

Source ADRs:
- `ARCHITECTURAL_DIRECTION.md` — locked: true (manifest-declared ADR, no Proposed/Draft marker)
- `TECHNICAL_DIRECTION.md` — locked: false (no document-level Accepted status)

---

## ADR-AD-01: ML is one component of nine; the evaluation gateway closes the loop
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Raw Events → Feature Layer → Behavior Analysis → ML Models → Decision Engine (fed by Business Rules) → Optimization Layer → Explanation Engine → Headless API → Dashboard/CLI; Evaluation & 3WD Gateway consumes simulator outcomes and feeds back retrain / re-segment / re-weight into the Feature Layer. The ML models are deliberately one component among nine.
- scope: conceptual architecture, system topology

## ADR-AD-02: Event ingestion on Python + Pydantic with DuckDB
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Accept canonical behavioral/business events (session, view, add-to-cart, purchase, campaign exposure, override) from the simulator or adapters; validate against schema; land in storage. Technology: Python + Pydantic schemas; DuckDB (local analytical store) with optional Postgres adapter. Alternatives rejected: SQLite (weak analytical SQL); Kafka (non-goal #1). Outputs: validated append-only event tables plus a rejects log.
- scope: Event Ingestion & Telemetry, storage

## ADR-AD-03: Feature layer as SQL + Python transforms with config-defined features
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Produce point-in-time-correct customer/segment features (RFM, session dynamics, category affinity, price-sensitivity proxy, message-fatigue counters, micro-conversion/PCR aggregates) as versioned feature tables keyed by (customer_id, as_of_ts). Technology: SQL (dbt-style or plain versioned SQL) + Python transforms; feature definitions in config. Alternative rejected: Feast feature store for MVP (complexity without payoff); the interface must not preclude it.
- scope: Feature Layer, point-in-time correctness

## ADR-AD-04: Segmentation method selected by MCDA under business constraints
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Produce business-viable customer segments; select the clustering method via MCDA under configured constraints (min size, max clusters, activity diversity, compute cost). Candidate algorithm registry contains K-means, GMM, BIRCH at minimum. Technology: scikit-learn plus a small MCDA module implementing TOPSIS and PROMETHEE II. Outputs: segment assignments + MCDA scorecard (per-candidate criteria matrix and ranking) + viability report.
- scope: Behavior Analysis (Segmentation), MCDA

## ADR-AD-05: Calibrated model ladder with mandatory calibration
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Produce calibrated response predictions per (customer, candidate action): purchase propensity, incentive response, churn/fatigue risk. Technology ladder: rules baseline → XGBoost/LightGBM (primary) → optional shallow NN or two-tower for the comparison narrative. Calibration is mandatory (isotonic/Platt). Outputs: calibrated probabilities plus SHAP attributions, persisted with model version.
- scope: ML Models (Prediction), calibration

## ADR-AD-06: Decision engine emits the typed Decision object
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Generate candidate actions, filter by constraints, rank by expected constrained profit, emit the decision object. Inputs: predictions, action catalog, business context (inventory, margin, campaigns), constraint config, segment. Outputs: typed `Decision` (action, expected impact, confidence, reasoning trace, constraints considered, runner-up). Detailed contract delegated to DECISION_ENGINE_DESIGN.md.
- scope: Decision Engine

## ADR-AD-07: Business rules as declarative YAML over an internal evaluator
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Declarative, versioned constraints and precedences (eligibility, frequency caps, inventory gates, discount ceilings, brand-safety, cold-start routing) defined in YAML; evaluated by a small internal rule evaluator over Pydantic contexts; outputs filter/adjustment verdicts with a fired-rule trace feeding explanations. Alternative rejected: Drools / production rule engines (JVM heft, non-goal).
- scope: Business Rules

## ADR-AD-08: Expected-value ranking in MVP, bandit as guardrailed stretch
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Ranking policy for MVP is expected-value ranking with uncertainty penalties. Stretch: contextual bandit (LinUCB/Thompson) operating *within* the rule-bounded action set, with off-policy evaluation. Outputs: ranked actions plus policy metadata (exploration flag, regret bookkeeping in simulation).
- scope: Optimization Layer, policy

## ADR-AD-09: No LLM in the explanation path
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Compose decision-grade explanations from top model attributions (relevance-framed), fired constraints, counterfactual gap to runner-up action, and a confidence statement, using SHAP plus deterministic templates. Explicit decision: no LLM in the explanation path — determinism and honesty outrank fluency. Outputs: `reasoning` (manager-readable paragraph) and `reasoning_trace` (structured, machine-readable).
- scope: Explanation Engine

## ADR-AD-10: Evaluation and 3WD experimentation gateway
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: (a) Offline policy comparison over the simulator (cumulative constrained profit, uplift, regret); (b) adjudicate variant/policy experiments via Accept/Reject/Delay with MDE, indifference margin, and max-delay escalation; (c) trigger feedback actions (re-segment, retrain). Outputs: three-axis evaluation report (prediction / decision / system) and experiment verdicts with statistical rationale.
- scope: Evaluation & 3WD Experimentation Gateway

## ADR-AD-11: The API is the product boundary; the dashboard is disposable
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Provide a REST decision API (`POST /decisions`, `GET /segments`, `GET /experiments/{id}`) plus an override endpoint, and a thin Streamlit (or equivalent) demo for the UC1/UC2 walkthrough. Explicit decision: the API is the product boundary; the dashboard is disposable.
- scope: Headless API & Demo Surface

## ADR-AD-12: Simulator is a cross-cutting component with a documented assumption log
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Generate a realistic mid-market e-commerce world (customers with latent price sensitivity/loyalty/fatigue, seasonal catalog, inventory, campaigns) that *responds* to actions, enabling counterfactual policy evaluation. All generative assumptions documented in an assumption log. Rationale: no public dataset contains action–response counterfactuals with business context.
- scope: Simulator

## ADR-AD-13: Typed plugin registries must require zero core changes
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Plugin points are registries with typed interfaces: `ActionProvider`, `Model`, `Policy`, `Constraint`, `ClusteringCandidate`, `MCDAMethod`, `IngestAdapter`, `Explainer`. Adding one of each must require zero core changes, acceptance-tested.
- scope: extensibility, plugin registries

## ADR-AD-14: Modular monolith package boundaries in one repo
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Modular boundaries `ingest / features / segmentation / models / decisions / rules / policies / explain / evaluate / api` as separate packages inside one repo (modular monolith). Future integrations kept cheap: feature-store interface abstracted; storage behind a thin repository layer; API versioned (`/v1`).
- scope: repository structure, modular monolith

## ADR-AD-15: Explanations use relevance framing, never surveillance framing
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Explanations use relevance framing ("because this category interests this segment") and never raw-surveillance framing ("because you viewed X at 02:13"); a documented style guide enforces this. Per-prediction SHAP top-k attributions are stored; every decision carries manager-readable reasoning plus a structured trace (candidate set → filtered with rule and why → scores → chosen vs runner-up delta); calibrated confidence is reported verbally *and* numerically, and low-confidence decisions must say so and degrade to safe defaults; every 3WD verdict includes metrics, thresholds, effect sizes, and margin.
- scope: explainability requirements, explanation style guide

## ADR-AD-16: Time-aware evaluation only; no random splits on behavioral data
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Offline evaluation uses time-aware splits only (no random splits on behavioral data), calibration curves, policy replay/simulation with cumulative constrained profit plus regret, and sensitivity analysis on MCDA weights. Online (simulated): 3WD-gated experiments with macro (CR, AOV) plus micro (PCR) metrics and effect sizes (Cohen's d class), not p-values alone. Human evaluation: structured review of a decision sample against the QUALITY_BAR.md rubric, plus override-rate tracking. Failure analysis is a mandatory per-release section (worst decisions, constraint conflicts, delay-loop incidents, reward-hacking probes).
- scope: evaluation requirements, leakage prevention

## ADR-AD-17: MLOps posture — MLflow, seeded reproduce, containerized API, no orchestration platform
- source: ARCHITECTURAL_DIRECTION.md
- status: locked
- decision: Experiment tracking via MLflow (local) for every training/evaluation run with run IDs referenced in reports. Versioning: code in git; models in a registry with model cards; configs in git, schema-validated. Reproducibility: a single `make reproduce` (or equivalent) regenerates dataset → features → models → decisions → report from seeds, with CI running a miniature end-to-end version. Testing: unit (rules, MCDA math, schemas), property-based (constraint filtering never emits ineligible actions), integration (pipeline stages), golden-file (decision objects for fixed seeds). Deployment: containerized API, no orchestration platform required, a Makefile/justfile is the operational interface. Monitoring (simulated): drift checks on feature distributions between simulator epochs; segment-stability report per re-clustering.
- scope: MLOps, reproducibility, testing, deployment

## ADR-AD-18: Data and artifact versioning left OPEN
- source: ARCHITECTURAL_DIRECTION.md
- status: locked (decision itself explicitly deferred)
- decision: Data and artifacts versioned by "DVC or content-hashed artifact store" — explicitly annotated `[Open: OD-7]` in the source. No choice is asserted by this ADR.
- scope: artifact versioning, data versioning

---

## ADR-TD-01: Modular monolith, not services
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: One Python repository, strict internal package boundaries (`ingest / features / segmentation / models / rules / decisions / policies / explain / evaluate / api / simulator`), one deployable API container. Justified in OPEN_DECISIONS OD-1: services add operational surface with zero portfolio or product payoff at this scale.
- scope: modular monolith architecture

## ADR-TD-02: Service boundaries expressed as interfaces, not networks
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Every registry interface (Model, Policy, Constraint, …) is designed as if it could be a service later; none is one now.
- scope: interface design, service readiness

## ADR-TD-03: Batch DAG plus a thin synchronous read path; no streaming
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Data flow is a batch DAG (simulate → ingest → features → segment → train → decide → evaluate) plus a thin synchronous read path where the API serves precomputed or on-demand single decisions. No streaming infrastructure; "events" are append-only tables processed incrementally.
- scope: data flow, API invocation model

## ADR-TD-04: Ownership boundaries — no component reaches around another's contract
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: The decision engine owns the `Decision` contract; models own calibrated scores; rules own eligibility; evaluation owns truth. No component reaches around another's contract.
- scope: ownership boundaries, contracts

## ADR-TD-05: Data contracts first, with quarantine on violation
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Every event/feature/decision table has a Pydantic/JSON-schema contract, versioned; ingestion rejects contract violations into a quarantine table with reasons.
- scope: data contracts

## ADR-TD-06: Canonical event schema; adapters map inward only
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: `event(event_id, customer_id, session_id, ts, type, payload, source)` with typed payloads per event type (view, add_to_cart, purchase, campaign_exposure, action_delivered, override, context_signal). Adapters map external shapes into this schema — never the reverse.
- scope: canonical event schema, adapters

## ADR-TD-07: Content-hash lineage printed in the evaluation report
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Each derived table records its inputs' content hashes and generating config hash; the evaluation report prints the full lineage chain.
- scope: lineage, auditability

## ADR-TD-08: Quality checks run as pipeline gates, not optional scripts
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Schema validation plus semantic checks (no negative prices, monotonic timestamps per session, referential integrity to catalog) run as pipeline gates, not optional scripts.
- scope: data quality gates

## ADR-TD-09: Point-in-time correctness is non-negotiable
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Features are computed `as_of` decision time; the test suite includes leakage tests. Evidence: random splits on behavioral time series are flagged as the canonical mistake in the corpus.
- scope: point-in-time correctness, leakage tests

## ADR-TD-10: Simulator is the primary data source, under four honesty rules
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: A documented generative simulator (customers with latent traits — price sensitivity, loyalty, fatigue; seasonal demand; inventory dynamics; action-response functions) is the primary data source, because decision evaluation requires counterfactuals no public dataset provides. Justified as OD-4. Honesty rules: (1) every generative assumption in `SIMULATOR_ASSUMPTIONS.md`; (2) simulator response functions are *not* available to models — models see only events; (3) headline results always labeled "in simulation"; (4) an optional adapter demo on a public clickstream dataset validates that pipelines run on non-synthetic shapes.
- scope: synthetic data simulator, data credibility

## ADR-TD-11: Classical-first ML ladder, each rung earning its place
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: (1) Rule-based heuristics as the honest baseline every result is measured against; (2) gradient boosting (XGBoost/LightGBM) as the workhorse — tabular, fast, SHAP-compatible; (3) optional shallow NN / two-tower comparison, included only to demonstrate evaluation discipline, reporting the answer either way; (4) contextual bandit (stretch) for within-horizon adaptation, guardrailed.
- scope: classical ML ladder, gradient boosting

## ADR-TD-12: Promotion requires beating the incumbent on decision-level metrics
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Every model change is an MLflow run with fixed splits; promotion requires beating the incumbent on decision-level metrics (constrained profit in replay), not just AUC.
- scope: experimentation strategy, model promotion

## ADR-TD-13: Model selection criteria, in order
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Decision value → calibration quality → explanation quality → prediction metrics → training cost.
- scope: model selection

## ADR-TD-14: Non-attributable models are inadmissible in the decision path
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Any model whose attributions cannot feed the explanation engine is inadmissible in the decision path; it may still appear in the comparison study.
- scope: interpretability requirement

## ADR-TD-15: The utility function is expected uplift × margin − cost − risk penalty
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: `data → insight → recommendation → action` made concrete: features and segments summarize behavior and predictions quantify likely responses per action; the policy converts predictions into a ranked, constraint-filtered action list under an explicit utility function (expected uplift × margin − cost − risk penalty); the API/exports deliver decisions to executing systems (simulator in MVP, campaign tools conceptually) with human approve/override, and every delivered action becomes an event; outcomes and overrides close the loop through the evaluation store and the 3WD gateway.
- scope: decision engine, utility function, closed loop

## ADR-TD-16: Models propose, rules dispose, evaluation decides what survives
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: The engine's governing asymmetry is that models propose, rules dispose, and evaluation decides what survives.
- scope: decision engine governance

## ADR-TD-17: Configuration as data; hardcoded business logic is a rejected PR
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: Behavior changes are config changes. Action catalogs, constraints, utility weights, MCDA criteria and weights, 3WD thresholds (MDE, indifference margin, delay budget), segmentation constraints, and feature lists are all declarative YAML, schema-validated, git-reviewed. Feature flags gate optional modules (bandit policy, content plugin, adapters). Hardcoded business logic is a rejected PR — the only business numbers in code are defaults the config must be able to override. Every run records its resolved config hash; two runs with the same hash and seed must agree.
- scope: configuration as data, feature flags

## ADR-TD-18: REST API surface, versioning, and the Decision public contract
- source: TECHNICAL_DIRECTION.md
- status: proposed
- decision: REST (FastAPI), OpenAPI-documented. Core endpoints: `POST /v1/decisions` (context in, Decision out), `POST /v1/decisions/{id}/override`, `GET /v1/segments`, `GET /v1/experiments/{id}`, `GET /v1/health`. The `Decision` object is the versioned public contract; breaking changes bump `/v2` and `/v1` semantics are never mutated. Consumers: the demo dashboard, batch exporters (CSV feed for the CRM persona), and future adapters; the API assumes nothing about the frontend (headless). Versioning: URL-versioned API, semver for the Python package, model versions and config hashes embedded in every response for auditability.
- scope: REST API, Decision contract, versioning
