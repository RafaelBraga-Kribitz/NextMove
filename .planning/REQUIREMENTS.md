# Requirements: NextMove — Behavioral Decision Engine for E-commerce Personalization

**Defined:** 2026-07-24
**Core Value:** Given a customer state, return the optimal next action — including the action of
doing nothing — ranked by expected incremental constrained profit, with confidence and a
manager-readable explanation.

**Provenance:** Derived from `.planning/intel/` (10 ingested planning documents). The `REQ-{slug}`
names in `.planning/intel/requirements.md` are synthesis artifacts; the IDs below are the canonical
ones. All 14 acceptance criteria from `QUALITY_BAR.md` are covered — see the AC map at the bottom.

---

## v1 Requirements

MVP scope. Every requirement maps to exactly one roadmap phase.

### Simulator (SIM)

- [x] **SIM-01**: The simulator generates a mid-market e-commerce world — customers with latent
      price sensitivity, loyalty and fatigue; a seasonal catalog; inventory dynamics; campaigns —
      that *responds* to delivered actions via explicit action-response functions, enabling
      counterfactual policy evaluation.

- [x] **SIM-02**: The simulator is an import-isolated package: no module under `models/`,
      `decisions/`, `policies/`, or `features/` may import it, enforced by an import-linter contract
      that fails CI. Simulator response functions are never visible to models — models see only
      events.

- [ ] **SIM-03**: Every generative assumption is documented in `SIMULATOR_ASSUMPTIONS.md`, and every
      result derived from simulated data is labeled "in simulation" wherever it is reported.

- [x] **SIM-04**: The simulator emits micro-conversion (PCR) events — scroll, filter, dwell class —
      alongside sessions, product views, add-to-cart, orders, campaign exposures, action deliveries
      and overrides, so micro-conversion weights can be derived empirically rather than guessed.

### Event Ingestion & Storage (DATA)

- [x] **DATA-01**: All events conform to one canonical schema
      `event(event_id, customer_id, session_id, ts, type, payload, source)` with typed payloads per
      event type; ingestion adapters map external shapes inward to this schema, never the reverse.

- [ ] **DATA-02**: Events are validated against versioned Pydantic contracts and landed append-only
      in DuckDB; contract violations are quarantined into a rejects table with a stated reason
      rather than silently dropped or coerced.

- [ ] **DATA-03**: Semantic quality checks — no negative prices, monotonic timestamps within a
      session, referential integrity to the catalog — run as pipeline gates that fail the run, not
      as optional scripts.

- [x] **DATA-04**: Every derived table records the content hashes of its inputs and the hash of the
      config that generated it, and the full lineage chain is printable.

### Feature Layer (FEAT)

- [ ] **FEAT-01**: Versioned feature tables keyed by `(customer_id, as_of_ts)` provide RFM, session
      dynamics (visits, depth, dwell), category affinity, price-sensitivity proxy, message-fatigue
      counters, cart state, abandonment history, and micro-conversion aggregates.

- [ ] **FEAT-02**: Features are computed strictly `as_of` decision time and all train/evaluation
      splits are time-aware; random splits on behavioral data are banned and leakage tests are part
      of the test suite.

### Predictive Models (MODEL)

- [ ] **MODEL-01**: A documented rule-based baseline policy exists and is the honest comparison point
      every later result is measured against.

- [ ] **MODEL-02**: Gradient-boosted models (XGBoost/LightGBM) score each `(customer, candidate
      action)` pair for purchase propensity, incentive response, and churn/fatigue risk.

- [ ] **MODEL-03**: Calibration is mandatory (isotonic/Platt) for every decision-path model; a
      calibration report with reliability curve and Brier score exists per model, and miscalibration
      beyond a configured bound fails the pipeline gate.

- [ ] **MODEL-04**: SHAP (or equivalent) attributions are produced and persisted per prediction with
      the model version, and any model whose attributions cannot feed the explanation engine is
      inadmissible in the decision path — it may still appear in the comparison study.

- [ ] **MODEL-05**: Model performance is reported multi-metrically — AUC/PR, Brier, calibration
      curves, each against the baseline — with no single-metric claims, and every trained model has
      a model card (data, features, metrics, calibration, limitations, intended use).

- [ ] **MODEL-06**: Uplift is approximated as `P(convert|action) − P(convert|none)` from the response
      models, and the approximation error against simulator ground truth is quantified and reported
      as a headline evaluation section rather than hidden.

- [ ] **MODEL-07**: The GBM-driven policy is promoted only if it beats the incumbent on
      decision-level replay profit with reported confidence intervals; if it does not, the report
      explicitly states so and the rule baseline ships.

### Segmentation (SEG)

- [ ] **SEG-01**: At least three clustering candidates — K-means, GMM, and BIRCH at minimum — are
      evaluated on every segmentation run through a `ClusteringCandidate` registry.

- [ ] **SEG-02**: The clustering method is selected by an MCDA module implementing TOPSIS and
      PROMETHEE II under **all four** configured viability constraints: minimum segment size,
      maximum cluster count, activity diversity, and compute cost. Segments violating any of the
      four are rejected regardless of statistical quality.

- [ ] **SEG-03**: Every run emits an MCDA scorecard (per-candidate criteria matrix, weights,
      ranking) plus a viability report and a sensitivity analysis over the MCDA weights; segments
      are readable at `GET /v1/segments`.

- [ ] **SEG-04**: Anonymous or brand-new customers are deterministically routed to the default
      variant of the best-performing generalized cluster, with "cold-start" stated explicitly in the
      decision reasoning.

### Decision Engine (DEC)

- [ ] **DEC-01**: The engine emits the typed `Decision` object with all contract fields —
      `decision_id`, `customer_id`, `as_of`, `action{type, params}`, `expected_outcome{metric,
      estimate, interval, horizon_days}`, `confidence`, `reasoning`, `reasoning_trace`,
      `constraints_considered`, `policy{name, model_versions, config_hash}`. No field is ever
      fabricated: an unavailable value is `null` with a stated reason.

- [ ] **DEC-02**: The action set always includes `none` and `wait(Δt)`, and both always appear in
      `candidates_considered` — a system that cannot recommend doing nothing cannot be trusted with
      discounts.

- [ ] **DEC-03**: The MVP action catalog is approximately eight archetypes — `none`, `wait`,
      `recommend`, `bundle`, two discount tiers, `email-now`, `email-delayed` — expanded into
      concrete parameterized candidates by the `ActionProvider` registry with small parameter grids.

- [ ] **DEC-04**: Timing and channel ship as **fixed parameters** of the action archetypes, carried
      in the `Decision` contract as `action.params.send_delay_hours` and `action.params.channel`, so
      UC1 renders `timing: +6h`. The policy ranks over archetypes; it does not search a delay or
      channel grid. (Optimizing them is v2 — see POL-02.)

- [ ] **DEC-05**: Hard constraints remove candidate actions before ranking; soft constraints penalize
      within ranking. The hard/soft distinction is declarative config, never code.

- [ ] **DEC-06**: Business rules — eligibility, frequency caps, inventory gates, discount ceilings,
      brand safety, cold-start routing — are declarative versioned YAML evaluated by a small
      internal rule evaluator over Pydantic contexts, emitting a fired-rule trace that feeds
      explanations.

- [ ] **DEC-07**: Surviving candidates are ranked by expected constrained profit
      `E[uplift(a|c,t)] × margin(a,B) − cost(a) − risk_penalty(a,c)` with an uncertainty penalty;
      every score carries an interval and the reported confidence derives from model calibration
      plus the score gap to the runner-up.

- [ ] **DEC-08**: No decision ever contains an action excluded by a hard constraint — verified by a
      property-based test over at least 10,000 randomized contexts with zero violations. Rules bound
      learning; no learned component may emit an action a rule has excluded.

- [ ] **DEC-09**: Given fixed `(context, config hash, model versions, seed)` the decision is
      byte-identical across runs (golden-file test), and the recorded `reasoning_trace` plus versions
      are sufficient to replay it. Exploration randomness, when present, is seeded and logged.

- [ ] **DEC-10**: Conflicting constraints resolve by declared precedence
      `compliance > inventory > campaign > preference`; unresolvable conflicts and fully-filtered
      candidate sets emit `action: none` with the filter trace and a `needs_human_review` flag.

- [ ] **DEC-11**: Insufficient data or low calibrated confidence degrades the decision to a safe
      default with an explicit "low confidence" statement in the reasoning — the engine never
      presents a guess as certainty.

### Explanation (EXPL)

- [ ] **EXPL-01**: 100% of decisions carry a non-empty manager-readable `reasoning` paragraph and a
      structured `reasoning_trace` containing `candidates_considered`, `filtered` (action, rule,
      detail), `scores`, `runner_up` with score gap, and `model_attributions`. The paragraph must be
      renderable to a marketing manager without edits.

- [ ] **EXPL-02**: Explanations are composed deterministically from model attributions, fired
      constraints, the counterfactual gap to the runner-up action, and a confidence statement, using
      templates. **No LLM appears anywhere in the decision or explanation path.**

- [ ] **EXPL-03**: Explanations use relevance framing ("this category interests this segment") and
      never surveillance framing ("because you viewed X at 02:13"), enforced by a documented
      explanation style guide.

- [ ] **EXPL-04**: A sampled set of decisions scores median ≥ 4 on the five-axis human rubric —
      faithfulness, completeness, readability, framing, honesty — with no faithfulness score below 3.

### Evaluation & 3WD Gateway (EVAL)

- [ ] **EVAL-01**: The three-way decision gateway adjudicates every simulated policy or variant
      change as **Accept / Reject / Delay** using a configured MDE and indifference margin, returning
      the metrics, thresholds, effect sizes and statistical rationale; verdicts are readable at
      `GET /v1/experiments/{id}`.

- [ ] **EVAL-02**: The gateway reproduces the correct verdict on a fixture suite covering clear-win,
      clear-loss, in-margin, and conflicting-metric (e.g. CR ↑ / AOV ↓) cases.

- [ ] **EVAL-03**: A Delay verdict that exhausts its configured delay budget escalates to
      `needs_human_review` rather than looping indefinitely.

- [ ] **EVAL-04**: A policy comparison harness replays any registered policy over the same simulated
      horizon and emits cumulative constrained profit with confidence intervals, regenerable by one
      command; the MVP comparison covers do-nothing, always-discount, always-top-seller, and the
      rules-only policy.

- [ ] **EVAL-05**: A three-axis evaluation report is published — prediction quality, decision quality
      (uplift, regret, constrained profit), system quality (latency, reproducibility,
      explainability) — including a mandatory failure-analysis section covering worst decisions,
      constraint conflicts, delay-loop incidents, and reward-hacking probes. Every headline number
      traces to an MLflow run ID and carries its "in simulation" caveat.

- [ ] **EVAL-06**: The report states the measured share of decisions in which no incentive was chosen
      for customers the simulator says would have bought anyway, next to the naive discount policy's
      0%. The value is reported as measured, never invented.

- [ ] **EVAL-07**: A manager override is logged as a high-weight labeled event and surfaces as a
      distinct signal in the next evaluation run.

- [ ] **EVAL-08**: A simulated drift epoch triggers scheduled re-segmentation and retraining whose
      material policy change is routed back through the 3WD gateway, demonstrating the closed loop
      end to end.

### Headless API (API)

- [ ] **API-01**: `POST /v1/decisions` accepts a customer/business/environmental context and returns
      a schema-valid `Decision` for any valid input, OpenAPI-documented.

- [ ] **API-02**: `POST /v1/decisions/{id}/override` persists a manager's alternative action as an
      event, and `GET /v1/health` reports readiness; the whole `/v1` surface is OpenAPI-documented.

- [ ] **API-03**: A single-decision API response completes in under 500 ms on a laptop.
- [ ] **API-04**: The `Decision` object is the versioned public contract: model versions and the
      resolved config hash are embedded in every response, breaking changes bump `/v2`, and `/v1`
      semantics are never mutated.

- [ ] **API-05**: One engine serves two invocation modes — batch materialization of decisions across
      a whole population, exported as a per-customer CSV action feed (action, timing, channel,
      explanation) for the CRM persona, and on-demand synchronous single decisions for the
      interactive path.

### Demo Surface (DEMO)

- [ ] **DEMO-01**: A thin demo surface (Streamlit or CLI) walks UC1 end to end — inspect customer →
      see decision → read explanation → override → see the override reflected in evaluation — in
      under 5 minutes without touching code.

- [ ] **DEMO-02**: The same surface walks UC2: a recently-purchased, satisfied customer with a high
      message-fatigue score receives `action: none` with reasoning of the form "contact now raises
      churn risk (fatigue signal); next evaluation in 7 days."

- [ ] **DEMO-03**: Everything the demo displays is obtainable from the public `/v1` API — the
      dashboard has zero privileged access and can be deleted without loss of capability.

- [ ] **DEMO-04**: The constraint configuration a manager steers with — maximum discount, frequency
      caps, discount ceilings — is documented for the non-technical persona and editable without
      code, with the effect visible in the next decision.

### Engineering Floor (ENG)

- [x] **ENG-01**: The repository is a modular monolith with packages `simulator / ingest / features /
      segmentation / models / rules / decisions / policies / explain / evaluate / api`; boundary
      violations fail CI via import-linter, and storage sits behind a thin repository layer.

- [ ] **ENG-02**: Eight typed plugin registries exist — `ActionProvider`, `Model`, `Policy`,
      `Constraint`, `ClusteringCandidate`, `MCDAMethod`, `IngestAdapter`, `Explainer` — and adding a
      new `Constraint` plus a new `ActionProvider` requires zero core-module edits, demonstrated by
      an example plugin in-repo.

- [x] **ENG-03**: All business numbers live in schema-validated, git-reviewed YAML — action catalog,
      constraints, utility weights, MCDA criteria and weights, 3WD thresholds (MDE, indifference
      margin, delay budget), segmentation constraints, feature lists, simulator parameters. Feature
      flags gate optional modules. Hardcoded business logic is a rejected change.

- [x] **ENG-04**: Any pipeline stage rerun with the same seed and config hash produces byte-identical
      outputs; seeds are explicit everywhere including exploration, and each run records its resolved
      config hash.

- [ ] **ENG-05**: `make reproduce` on a clean clone completes end to end and reproduces the published
      metrics tables exactly, and CI runs the miniature end-to-end version green on every push.

- [ ] **ENG-06**: Test coverage is ≥ 85% of lines in `rules/`, `decisions/` and `evaluate/`, and
      ≥ 75% overall, across unit, property-based, integration, and golden-file layers.

- [ ] **ENG-07**: Every training and evaluation run is an MLflow run with fixed splits, whose run ID
      is cited in the reports that use it.

- [x] **ENG-08**: The system runs entirely on a laptop — one deployable API container, a
      Makefile/justfile as the operational interface, no orchestration platform, no cloud
      dependency, no streaming infrastructure.

- [x] **ENG-09**: Data and model artifacts are versioned by a ratified mechanism. **OD-7 is open**
      (DVC vs. content-hashed artifact store + MLflow artifacts) and must be decided by ADR, not
      assumed.

### Documentation & Portfolio (DOC)

- [x] **DOC-01**: OD-1 through OD-10 are ratified as `docs/adr/001-*.md` … `010-*.md`, including the
      explicit ratification of OD-7; thereafter every resolved open decision and every accepted debt
      exception gets its own ADR, and any change to a ratified decision requires a superseding ADR.

- [ ] **DOC-02**: The portfolio artifact set is complete and current: `README.md` with the
      90-second pitch, a one-page C4-ish architecture diagram, quickstart and results table (a
      reviewer can run the demo from it unaided); `DEBT.md` with what/why/blast-radius/removal-trigger
      per accepted shortcut; `EXPERIMENTS.md` as a human-readable MLflow index; the explanation style
      guide; and the OpenAPI reference.

**Persona coverage** (from `REQ-persona-surfaces`; no separate requirement — traced through the
above): P1 Marketing/CRM manager → DEMO-01, DEMO-02, DEMO-04, EXPL-01, API-02 · P2 E-commerce
product manager → EVAL-01, EVAL-02, EVAL-03, ENG-03 · P3 Data scientist → ENG-02, ENG-03, ENG-07,
EVAL-04, MODEL-07 · P4 CRM specialist → API-05.

---

## v2 Requirements

Deferred. Listed in the ruthless priority order fixed by `PRODUCT_CHARTER.md` §5 — contextual
bandit first, adapters last. Not in the current roadmap.

### Adaptive Policy (POL)

- **POL-01** *(stretch #1 — highest research-alignment payoff)*: A contextual bandit policy
  (LinUCB / Thompson) explores **only within** the rule-bounded surviving action set, with
  off-policy evaluation against logged data and regret bookkeeping reported with smoothing. Reward
  includes fatigue and margin penalties.

- **POL-02** *(stretch #2)*: Timing and channel are promoted from fixed archetype parameters to
  optimized decision dimensions — the policy searches a delay/channel grid rather than selecting a
  fixed archetype. Depends on DEC-04 and POL-01.

- **POL-03** *(stretch #4)*: Explicit uplift learners (T-/X-learner) replace the propensity-difference
  approximation of MODEL-06 in the decision path. Removal trigger for that debt item.

### Adaptive Experimentation (EXP)

- **EXP-01** *(stretch #3 — corpus-flagged novelty)*: 3WD thresholds become dynamic
  (traffic- and seasonality-aware MDE) behind the threshold interface designed for it in MVP.

### Longitudinal & Content (LONG, CONT)

- **LONG-01** *(stretch #5)*: Longitudinal cohort tracking of fatigue and LTV proxies over simulated
  months, reported alongside short-term conversion metrics.

- **CONT-01** *(stretch #6)*: A guarded generative content plugin serving pre-generated,
  catalog-validated copy variants — GenUI in its safe form only, never in the core decision path.

### Integration (ADPT)

- **ADPT-01** *(stretch #7)*: GA4, CSV and Postgres ingestion adapters map external shapes inward to
  the canonical event schema, proving the headless claim.

- **ADPT-02**: A public clickstream dataset runs through ingestion → features → segmentation,
  validating that the pipelines work on non-synthetic shapes (simulator honesty rule 4, OD-4
  option B).

---

## Out of Scope

Explicitly excluded. Reasoning preserved so these are not re-added.

| Feature | Reason |
|---------|--------|
| Amazon-scale recommendation infrastructure (distributed serving, vector DBs at scale, sub-10ms SLAs) | Non-goal #1. The stated buyer cannot afford it; it demonstrates infrastructure theater, not decision intelligence |
| Production CDP replacement (identity resolution, consent management, connector marketplace) | Non-goal #2. NextMove assumes the data problem is roughly solved and owns the layer CDPs delegate |
| Generic, domain-agnostic AI/ML framework | Non-goal #3. Opinionated over generic — the e-commerce-native action catalog, utility function and constraint vocabulary *are* the product |
| Autonomous marketing agent | Non-goal #4. No action executed without a human-approvable surface; fully autonomous adaptation is empirically rejected by users across the corpus |
| Real-time in-session UI mutation at scale | Non-goal #5. MVP decides at batch/near-line cadence; real-time adaptation is studied only inside the simulator |
| Live LLM-generated UI in the core path | Non-goal #6. Hallucination liability; at most an optional guarded plugin with pre-generated, catalog-validated content |
| A front-end product | Non-goal #7. The engine is headless; the dashboard is a thin, disposable demo client |
| Deep-learning maximalism | Non-goal #8. Neural models appear only where the comparison teaches something |
| Real personal data | Non-goal #9. Synthetic simulator only — no scraping, no PII, no GDPR exposure |
| Multi-tenant SaaS concerns (auth, billing, tenancy) | Non-goal #10. Single-developer portfolio project, no tenancy story |
| Real-time serving infrastructure | Explicitly not even stretch (`PRODUCT_CHARTER.md` §5) |
| Deep reinforcement learning | Explicitly not even stretch; corpus rates single-developer feasibility low |
| Federated learning | Explicitly not even stretch; infeasible solo |
| Streaming decisioning architecture (Kafka/Redpanda, online features, real-time bandit serving) | Architecture B, rejected: high complexity, unneeded scalability, low solo maintainability, superficially flashy and substantively thin |
| Notebook-and-library research repo with no API | Architecture C, rejected: violates production realism and prohibited anti-pattern #1. Notebooks are allowed under `notebooks/` for exploration, never as pipeline |
| Drools / JVM production rule engines | Rejected in ADR-AD-07: JVM heft for a small declarative evaluator's job |
| Feast feature store | Rejected for MVP in ADR-AD-03: complexity without payoff. The feature interface must not preclude it later |
| SQLite as the analytical store | Rejected in ADR-AD-02: weak analytical SQL. DuckDB instead |
| Preference-trajectory modeling | Deliberately not pursued: novel but orthogonal to the decision thesis |
| Autonomous UI-generating RL | Deliberately not pursued: corpus rates feasibility low |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIM-01 | Phase 1 | Complete |
| SIM-02 | Phase 1 | Complete |
| SIM-03 | Phase 1 | Pending |
| SIM-04 | Phase 1 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Complete |
| FEAT-01 | Phase 1 | Pending |
| FEAT-02 | Phase 1 | Pending |
| ENG-01 | Phase 1 | Complete |
| ENG-03 | Phase 1 | Complete |
| ENG-04 | Phase 1 | Complete |
| ENG-08 | Phase 1 | Complete |
| ENG-09 | Phase 1 | Complete |
| DOC-01 | Phase 1 | Complete |
| MODEL-01 | Phase 2 | Pending |
| DEC-01 | Phase 2 | Pending |
| DEC-02 | Phase 2 | Pending |
| DEC-03 | Phase 2 | Pending |
| DEC-04 | Phase 2 | Pending |
| DEC-05 | Phase 2 | Pending |
| DEC-06 | Phase 2 | Pending |
| DEC-07 | Phase 2 | Pending |
| DEC-08 | Phase 2 | Pending |
| DEC-09 | Phase 2 | Pending |
| DEC-10 | Phase 2 | Pending |
| EXPL-01 | Phase 2 | Pending |
| EXPL-02 | Phase 2 | Pending |
| EXPL-03 | Phase 2 | Pending |
| API-01 | Phase 2 | Pending |
| API-02 | Phase 2 | Pending |
| API-03 | Phase 2 | Pending |
| API-04 | Phase 2 | Pending |
| ENG-02 | Phase 2 | Pending |
| EVAL-01 | Phase 3 | Pending |
| EVAL-02 | Phase 3 | Pending |
| EVAL-03 | Phase 3 | Pending |
| EVAL-04 | Phase 3 | Pending |
| EVAL-06 | Phase 3 | Pending |
| EVAL-07 | Phase 3 | Pending |
| API-05 | Phase 3 | Pending |
| MODEL-02 | Phase 4 | Pending |
| MODEL-03 | Phase 4 | Pending |
| MODEL-04 | Phase 4 | Pending |
| MODEL-05 | Phase 4 | Pending |
| MODEL-06 | Phase 4 | Pending |
| MODEL-07 | Phase 4 | Pending |
| SEG-01 | Phase 4 | Pending |
| SEG-02 | Phase 4 | Pending |
| SEG-03 | Phase 4 | Pending |
| SEG-04 | Phase 4 | Pending |
| DEC-11 | Phase 4 | Pending |
| EXPL-04 | Phase 4 | Pending |
| ENG-07 | Phase 4 | Pending |
| EVAL-08 | Phase 4 | Pending |
| DEMO-01 | Phase 5 | Pending |
| DEMO-02 | Phase 5 | Pending |
| DEMO-03 | Phase 5 | Pending |
| DEMO-04 | Phase 5 | Pending |
| EVAL-05 | Phase 5 | Pending |
| ENG-05 | Phase 5 | Pending |
| ENG-06 | Phase 5 | Pending |
| DOC-02 | Phase 5 | Pending |

**Coverage:**

- v1 requirements: 64 total
- Mapped to phases: 64
- Unmapped: 0 ✓

**Per phase:** Phase 1 → 16 · Phase 2 → 19 · Phase 3 → 7 · Phase 4 → 14 · Phase 5 → 8

---

## Appendix: QUALITY_BAR acceptance criteria map

All 14 acceptance criteria from `QUALITY_BAR.md` are represented. AC-7 is deliberately **widened**:
the SPEC names two viability constraints, the locked ADR mandates four, and the locked ADR wins.

| AC | Requirement(s) | Phase |
|----|----------------|-------|
| AC-1 — schema-valid Decision, `none`/`wait` in candidates | API-01, DEC-01, DEC-02 | 2 |
| AC-2 — no hard-constraint-excluded action, ≥10k property cases | DEC-08 | 2 |
| AC-3 — decision determinism, golden file | DEC-09 | 2 |
| AC-4 — reasoning completeness | EXPL-01 | 2 |
| AC-5 — calibration gate | MODEL-03 | 4 |
| AC-6 — GBM vs. baseline with honest-negative escape hatch | MODEL-07 | 4 |
| AC-7 — segmentation viability + MCDA scorecard *(widened to 4 criteria)* | SEG-02, SEG-03 | 4 |
| AC-8 — 3WD verdict fixture suite | EVAL-02 | 3 |
| AC-9 — delay budget escalation | EVAL-03 | 3 |
| AC-10 — policy comparison report | EVAL-04, MODEL-07 | 3, 4 |
| AC-11 — one-command reproduction, CI green | ENG-05 | 5 |
| AC-12 — coverage thresholds | ENG-06 | 5 |
| AC-13 — registry extensibility without core edits | ENG-02 | 2 |
| AC-14 — UC1 walkthrough via the demo surface | DEMO-01 | 5 |

**Use case map:** UC1 → DEMO-01 (rendered), DEC-01..07 (produced) · UC2 → DEMO-02, DEC-02, DEC-11 ·
UC3 → SEG-01..03, EVAL-01 · UC4 → EVAL-01, EVAL-02, EVAL-03 · UC5 → SEG-04 · UC6 → API-02, EVAL-07 ·
UC7 → EVAL-04, MODEL-07 · Edge cases → DEC-10 (conflict, infeasible set), DEC-11 (low confidence),
EVAL-08 (drift).

---
*Requirements defined: 2026-07-24*
*Last updated: 2026-07-24 after initial definition from `/gsd-ingest-docs` synthesis*
