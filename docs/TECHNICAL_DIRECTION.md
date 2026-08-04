# TECHNICAL_DIRECTION.md

**Project:** NextMove — Behavioral Decision Engine for E-commerce Personalization

---

## 1. Architectural Philosophy

- **Modular monolith, not services.** One Python repository, strict internal package boundaries (`ingest / features / segmentation / models / rules / decisions / policies / explain / evaluate / api / simulator`), one deployable API container. `[Decision — justified in OPEN_DECISIONS OD-1: services add operational surface with zero portfolio or product payoff at this scale; the corpus's offline-heavy consensus makes a monolith honest, not lazy.]`
- **Service boundaries expressed as interfaces, not networks.** Every registry interface (Model, Policy, Constraint, …) is designed as if it could be a service later; none is one now.
- **Data flow:** batch DAG (simulate → ingest → features → segment → train → decide → evaluate) + a thin synchronous read path (API serves precomputed or on-demand single decisions). No streaming infrastructure; "events" are append-only tables processed incrementally.
- **Ownership boundaries:** the decision engine owns the `Decision` contract; models own calibrated scores; rules own eligibility; evaluation owns truth. No component reaches around another's contract.

## 2. Data Philosophy

- **Data contracts first:** every event/feature/decision table has a Pydantic/JSON-schema contract, versioned; ingestion rejects contract violations into a quarantine table with reasons.
- **Canonical event schema:** `event(event_id, customer_id, session_id, ts, type, payload, source)` with typed payloads per event type (view, add_to_cart, purchase, campaign_exposure, action_delivered, override, context_signal). Adapters map external shapes into this schema — never the reverse.
- **Lineage:** each derived table records its inputs' content hashes and generating config hash; the evaluation report prints the full lineage chain.
- **Quality checks:** schema validation + semantic checks (no negative prices, monotonic timestamps per session, referential integrity to catalog) run as pipeline gates, not optional scripts.
- **Point-in-time correctness is non-negotiable:** features are computed `as_of` decision time; the test suite includes leakage tests. `[Evidence: random splits on behavioral time series flagged as the canonical mistake in the corpus.]`
- **Synthetic vs. real data `[Decision — OD-4]`:** a documented generative simulator (customers with latent traits: price sensitivity, loyalty, fatigue; seasonal demand; inventory dynamics; action-response functions) is the primary data source, because decision evaluation requires counterfactuals no public dataset provides. Honesty rules: (1) every generative assumption in `SIMULATOR_ASSUMPTIONS.md`; (2) simulator response functions are *not* available to models — models see only events; (3) headline results always labeled "in simulation"; (4) an optional adapter demo on a public clickstream dataset validates that pipelines run on non-synthetic shapes.

## 3. ML Philosophy

- **Classical-first ladder, each rung earning its place:**
  1. Rule-based heuristics (the honest baseline every result is measured against),
  2. Gradient boosting (XGBoost/LightGBM) as the workhorse — tabular, fast, SHAP-compatible,
  3. Optional shallow NN / two-tower comparison — included only to demonstrate the evaluation discipline (does representation learning pay for its complexity here? report the answer either way),
  4. Contextual bandit (stretch) for within-horizon adaptation, guardrailed.
- **Experimentation strategy:** every model change is an MLflow run with fixed splits; promotion requires beating the incumbent on decision-level metrics (constrained profit in replay), not just AUC.
- **Model selection criteria (in order):** decision value → calibration quality → explanation quality → prediction metrics → training cost.
- **Interpretability requirement:** any model whose attributions cannot feed the explanation engine is inadmissible in the decision path (it may still appear in the comparison study).

## 4. Decision Engine Philosophy

`data → insight → recommendation → action`, made concrete:

- **Data → insight:** features and segments summarize behavior; predictions quantify likely responses per action.
- **Insight → recommendation:** the policy converts predictions into a ranked, constraint-filtered action list under an explicit utility function (expected uplift × margin − cost − risk penalty).
- **Recommendation → action:** the API/exports deliver decisions to executing systems (simulator in MVP, campaign tools conceptually); humans can approve/override; every delivered action becomes an event.
- **Action → learning:** outcomes and overrides close the loop through the evaluation store and the 3WD gateway.
- The engine's governing asymmetry: **models propose, rules dispose, evaluation decides what survives.**

## 5. Configuration Philosophy

- **Behavior changes are config changes.** Action catalogs, constraints, utility weights, MCDA criteria and weights, 3WD thresholds (MDE, indifference margin, delay budget), segmentation constraints, feature lists — all declarative YAML, schema-validated, git-reviewed.
- **Feature flags** gate optional modules (bandit policy, content plugin, adapters).
- **Hardcoded business logic is a rejected PR.** The only business numbers in code are defaults that the config must be able to override.
- **Config is data:** every run records its resolved config hash; two runs with the same hash and seed must agree.

## 6. API Philosophy

- **Interfaces:** REST (FastAPI), OpenAPI-documented. Core: `POST /v1/decisions` (context in, Decision out), `POST /v1/decisions/{id}/override`, `GET /v1/segments`, `GET /v1/experiments/{id}`, `GET /v1/health`.
- **Contracts:** the `Decision` object is the versioned public contract; breaking changes bump `/v2` — never mutate `/v1` semantics.
- **Consumers:** the demo dashboard, batch exporters (CSV feed for the CRM persona), and future adapters. The API assumes nothing about the frontend (headless).
- **Versioning strategy:** URL-versioned API; semver for the Python package; model versions and config hashes embedded in every response for auditability.
