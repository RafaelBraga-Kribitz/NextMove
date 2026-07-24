# ARCHITECTURAL_DIRECTION.md

**Project:** NextMove — Behavioral Decision Engine for E-commerce Personalization

---

## 1. Conceptual Architecture

```
Raw Events ──► Feature Layer ──► Behavior Analysis ──► ML Models ──► Decision Engine
                                                                        ▲      │
                                              Business Rules ───────────┘      ▼
                                                                     Optimization Layer
                                                                              │
                                                                              ▼
                                                                    Explanation Engine
                                                                              │
                                                                              ▼
                                                                  Headless API ► Dashboard/CLI
                                                                              │
                    Evaluation & 3WD Gateway ◄── Outcomes (simulator) ◄───────┘
                              │
                              └────────── feedback: retrain / re-segment / re-weight ─────► Feature Layer
```

The ML models are deliberately one component among nine. The evaluation gateway closes the loop.

---

## 2. Component Definitions

### 2.1 Event Ingestion & Telemetry
- **Responsibility:** accept canonical behavioral/business events (session, view, add-to-cart, purchase, campaign exposure, override) from the simulator or adapters; validate against schema; land in storage.
- **Inputs:** JSON/Parquet event streams; adapter outputs (CSV/GA4-shaped/Postgres — stretch).
- **Outputs:** validated event tables (append-only), rejects log.
- **Technology:** Python + Pydantic schemas; DuckDB (local analytical store) with optional Postgres adapter. `[Alternative: SQLite — rejected, weak analytical SQL; Kafka — rejected, non-goal #1.]`

### 2.2 Feature Layer
- **Responsibility:** point-in-time-correct customer/segment features: RFM, session dynamics, category affinity, price-sensitivity proxy, message-fatigue counters, micro-conversion aggregates (PCR inputs).
- **Inputs:** event tables + catalog/inventory/campaign reference data.
- **Outputs:** versioned feature tables keyed by (customer_id, as_of_ts).
- **Technology:** SQL (dbt-style models or plain versioned SQL) + Python transforms; feature definitions in config. `[Alternative: Feast feature store — rejected for MVP as complexity without payoff; the interface should not preclude it.]`

### 2.3 Behavior Analysis (Segmentation)
- **Responsibility:** produce business-viable customer segments; select the clustering method via MCDA under configured constraints (min size, max clusters, activity diversity, compute cost).
- **Inputs:** feature vectors; constraint config; candidate algorithm registry (K-means, GMM, BIRCH at minimum).
- **Outputs:** segment assignments + MCDA scorecard (per-candidate criteria matrix and ranking) + viability report.
- **Technology:** scikit-learn + a small MCDA module (TOPSIS and PROMETHEE II). `[Evidence-grounded: this is the anchor paper's "contextual algorithm."]`

### 2.4 ML Models (Prediction)
- **Responsibility:** calibrated response predictions per (customer, candidate action): purchase propensity, incentive response, churn/fatigue risk.
- **Inputs:** features; labeled outcomes from simulator history.
- **Outputs:** calibrated probabilities + SHAP attributions, persisted with model version.
- **Technology:** rules baseline → XGBoost/LightGBM (primary) → optional shallow NN or two-tower for the comparison narrative. Calibration mandatory (isotonic/Platt).

### 2.5 Decision Engine (core)
- **Responsibility:** generate candidate actions, filter by constraints, rank by expected constrained profit, emit the decision object. Detailed contract in DECISION_ENGINE_DESIGN.md.
- **Inputs:** predictions, action catalog, business context (inventory, margin, campaigns), constraint config, segment.
- **Outputs:** typed `Decision` (action, expected impact, confidence, reasoning trace, constraints considered, runner-up).

### 2.6 Business Rules
- **Responsibility:** declarative, versioned constraints and precedences: eligibility, frequency caps, inventory gates, discount ceilings, brand-safety, cold-start routing.
- **Inputs:** YAML rule definitions.
- **Outputs:** filter/adjustment verdicts with fired-rule trace (feeds explanations).
- **Technology:** small internal rule evaluator over Pydantic contexts. `[Alternative: Drools/production rule engines — rejected, JVM heft, non-goal.]`

### 2.7 Optimization Layer
- **Responsibility:** ranking policy. MVP: expected-value ranking with uncertainty penalties. Stretch: contextual bandit (LinUCB/Thompson) operating *within* the rule-bounded action set, with off-policy evaluation.
- **Outputs:** ranked actions + policy metadata (exploration flag, regret bookkeeping in simulation).

### 2.8 Explanation Engine
- **Responsibility:** compose decision-grade explanations: top model attributions (relevance-framed, never surveillance-framed), fired constraints, counterfactual gap to runner-up action, confidence statement.
- **Outputs:** `reasoning` (manager-readable paragraph) + `reasoning_trace` (structured, machine-readable).
- **Technology:** SHAP + deterministic templates. `[Decision: no LLM in the explanation path — determinism and honesty outrank fluency.]`

### 2.9 Evaluation & 3WD Experimentation Gateway
- **Responsibility:** (a) offline policy comparison over the simulator (cumulative constrained profit, uplift, regret); (b) adjudicate variant/policy experiments via Accept/Reject/Delay with MDE, indifference margin, and max-delay escalation; (c) trigger feedback actions (re-segment, retrain).
- **Outputs:** evaluation report (three-axis: prediction / decision / system), experiment verdicts with statistical rationale.

### 2.10 Headless API & Demo Surface
- **Responsibility:** REST decision API (`POST /decisions`, `GET /segments`, `GET /experiments/{id}`), override endpoint; thin Streamlit (or equivalent) demo for UC1/UC2 walkthrough.
- **Decision:** the API is the product boundary; the dashboard is disposable.

### 2.11 Simulator (cross-cutting)
- **Responsibility:** generate a realistic mid-market e-commerce world (customers with latent price sensitivity/loyalty/fatigue, seasonal catalog, inventory, campaigns) and *respond* to actions, enabling counterfactual policy evaluation. All generative assumptions documented in an assumption log.
- **Why it exists:** no public dataset contains action–response counterfactuals with business context; the corpus itself notes most studies rely on synthesized or short-term data — the simulator makes that limitation explicit and controlled rather than hidden.

---

## 3. Required Capabilities (MVP)

Event ingestion & schema validation · point-in-time feature generation · MCDA-constrained segmentation · calibrated response modeling with baseline comparison · candidate-action generation · declarative constraint filtering · expected-value decision ranking · decision-grade explanation · 3WD experiment adjudication · offline policy simulation & report · headless decision API · seeded end-to-end reproducibility · experiment tracking.

## 4. Optional Capabilities ("useful but not required")

Contextual bandit policy with OPE · uplift models · timing/channel decision dimensions · dynamic 3WD thresholds · longitudinal cohort/fatigue tracking · ingestion adapters (GA4/CSV/Postgres) · guarded pre-generated content plugin · UMAP pre-clustering reduction · two-tower retrieval comparison.

## 5. Extensibility Requirements

- **Plugin points (registries with typed interfaces):** `ActionProvider`, `Model`, `Policy`, `Constraint`, `ClusteringCandidate`, `MCDAMethod`, `IngestAdapter`, `Explainer`. Adding one of each must require zero core changes (acceptance-tested).
- **Modular boundaries:** `ingest / features / segmentation / models / decisions / rules / policies / explain / evaluate / api` as separate packages inside one repo (modular monolith).
- **Future integrations kept cheap:** feature-store interface abstracted; storage behind a thin repository layer; API versioned (`/v1`).

## 6. Explainability Requirements

- **Predictions:** per-prediction SHAP top-k attributions, stored.
- **Recommendations/decisions:** every decision object carries (1) manager-readable reasoning; (2) structured trace: candidate set → filtered (which rule, why) → scores → chosen vs. runner-up delta.
- **Uncertainty:** calibrated confidence reported verbally *and* numerically; low-confidence decisions must say so and degrade to safe defaults.
- **Perception rule `[Evidence: privacy-paradox literature]`:** explanations use relevance framing ("because this category interests this segment") and never raw-surveillance framing ("because you viewed X at 02:13"); a documented style guide enforces this.
- **Experiments:** every 3WD verdict includes the metrics, thresholds, effect sizes, and margin that produced it.

## 7. Evaluation Requirements

- **Offline:** time-aware splits only (no random splits on behavioral data — corpus-flagged mistake); calibration curves; policy replay/simulation with cumulative constrained profit + regret; sensitivity analysis on MCDA weights.
- **Online (simulated):** 3WD-gated experiments with macro (CR, AOV) + micro (PCR) metrics; effect sizes (Cohen's d class), not p-values alone.
- **Human evaluation:** structured review of a decision sample for explanation quality (rubric in QUALITY_BAR.md); override-rate tracking in the demo loop.
- **Failure analysis:** mandatory section per release: worst decisions, constraint conflicts, delay-loop incidents, reward-hacking probes (does the bandit exploit the fatigue loophole if the penalty is removed?).

## 8. MLOps Expectations

- **Experiment tracking:** MLflow (local) for every training/evaluation run; run IDs referenced in reports.
- **Versioning:** code (git), data & artifacts (DVC or content-hashed artifact store `[Open: OD-7]`), models (registry with model cards), configs (git, schema-validated).
- **Reproducibility:** single `make reproduce` (or equivalent) regenerates dataset → features → models → decisions → report from seeds; CI runs a miniature end-to-end version.
- **Testing:** unit (rules, MCDA math, schemas), property-based (constraint filtering never emits ineligible actions), integration (pipeline stages), golden-file (decision objects for fixed seeds).
- **Deployment posture:** containerized API; no orchestration platform required; a Makefile/justfile is the operational interface.
- **Monitoring (simulated):** drift checks on feature distributions between simulator epochs; segment-stability report per re-clustering.
