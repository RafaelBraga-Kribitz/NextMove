# PRODUCT_CHARTER.md

**Project:** NextMove — Behavioral Decision Engine for E-commerce Personalization

---

## 1. Product Objective

Build a system capable of recommending the optimal next customer-facing action by combining:

```
User behavior  +  Business context  +  Operational constraints  +  Predictive models  +  Decision logic
```

Formally: given a customer state, a catalog of candidate actions, and a set of business constraints, produce a ranked decision with expected outcome, confidence, and reasoning — and evaluate whether deployed decisions actually improved business outcomes.

### Measurable objectives

1. **O1 — Decision, not prediction:** For any evaluated customer state, the system returns a complete decision object (action, expected impact, confidence, reasoning, constraints considered) — including the actions *offer nothing* and *wait*.
2. **O2 — Beat the naive policies:** In offline simulation, the decision policy achieves higher cumulative constrained profit than (a) "always discount," (b) "always recommend top-seller," and (c) "do nothing" baselines, with confidence intervals reported.
3. **O3 — Business-viable segmentation:** Every produced segment satisfies configured viability constraints (minimum size, maximum segment count, activity diversity); MCDA scoring of candidate clustering methods is reproducible.
4. **O4 — Safe experimentation:** Every simulated policy/UI change is routed through the three-way decision gateway (Accept / Reject / Delay) with explicit thresholds and indifference margins.
5. **O5 — Explainable by default:** 100% of decisions carry a reasoning payload renderable as one paragraph a marketing manager can read; model-level attributions (SHAP or equivalent) available on demand.
6. **O6 — Reproducible:** A fresh clone + one documented command regenerates the dataset, features, models, decisions, and evaluation report deterministically (seeded).

---

## 2. Success Criteria

### Product metrics

- **Workflow improvement:** the demo walks a marketing-manager scenario end-to-end (inspect customer → see decision → read explanation → override → see override logged as feedback) in under 5 minutes.
- **Decision quality:** ≥ X% of simulated decisions where "no incentive" was chosen for would-buy-anyway customers, versus 0% for the naive discount policy (X reported, not invented; target directionally positive and statistically supported).
- **Adoption proxy (portfolio):** a reviewer can run the demo from the README without assistance.

### Technical metrics

- **Model performance:** calibrated probabilities (reported Brier score / calibration curves), AUC/PR reported per model vs. baseline; no single-metric claims.
- **Decision performance:** cumulative reward/regret curves for the bandit vs. static policies in simulation; uplift estimates with intervals.
- **Latency:** single-decision API response < 500 ms on a laptop `[Assumption: adequate for batch/near-line marketing decisions; real-time UI serving is out of MVP scope]`.
- **Reliability/reproducibility:** CI green; seeded end-to-end run produces byte-identical metrics tables.

### Portfolio metrics

- Architecture explainable in one diagram + one page.
- Every non-obvious choice has an ADR.
- Model cards for every trained model; assumption log for the simulator.

---

## 3. Personas

### P1 — Marketing / CRM Manager ("Claudia")
- **Role & responsibilities:** owns campaign calendar, discounting budget, email/push programs for a mid-market fashion retailer.
- **Frustrations:** cannot tell which discounts were wasted; tools give scores, not recommendations; can't defend spend to finance.
- **Goals:** grow revenue without eroding margin; defensible, explainable targeting.
- **Technical maturity:** Excel + campaign tools; will not read a notebook.
- **Expected interaction:** reads decision cards ("what should we do for this segment/customer and why"), approves/overrides, sets constraints (max discount, frequency caps).

### P2 — E-commerce Product Manager ("Jonas")
- **Role:** owns site experience and merchandising placements; runs experiments.
- **Frustrations:** binary A/B forces bad calls; conflicting metrics (CR ↑, AOV ↓) unresolvable; fears shipping changes that quietly hurt revenue.
- **Goals:** safe, evidence-routed rollout of interface/merchandising variants per segment.
- **Maturity:** comfortable with dashboards and experiment readouts; not with code.
- **Interaction:** consumes 3WD experiment verdicts (Accept/Reject/Delay + why), configures MDE and indifference margins with guidance.

### P3 — Data Scientist ("Priya")
- **Role:** builds and maintains the models; accountable for their honesty.
- **Frustrations:** models shipped as CSVs that never touch decisions; no evaluation infrastructure; irreproducible experiments.
- **Goals:** plug new models/policies into a stable contract; compare fairly against baselines.
- **Maturity:** high; primary user of the Python API and config system.
- **Interaction:** extends model/policy registries, runs offline evaluation and replay, reads experiment tracking.

### P4 — CRM Specialist ("Marek")
- **Role:** executes lifecycle communications (cart recovery, win-back, post-purchase).
- **Frustrations:** timing and channel chosen by static rules; message fatigue complaints.
- **Goals:** right message, right channel, right time — with restraint (frequency caps respected automatically).
- **Maturity:** operates campaign tooling.
- **Interaction:** consumes per-customer action feeds (action + timing + channel + explanation) exported from the decision API.

---

## 4. Use Cases

### Primary

**UC1 — Next-best-action for an engaged high-value customer** *(the flagship scenario)*
- **Trigger:** customer session ends with cart abandonment.
- **Input:** Austrian customer, 7 visits to winter jackets, item in cart, high LTV, low modeled price sensitivity, jacket inventory low, pre-Christmas season, cold-weather context.
- **Process:** feature assembly → response/propensity predictions per candidate action → constraint filtering (low inventory ⇒ suppress discount; frequency cap check) → expected-value ranking → explanation.
- **Output:** `action: premium_bundle_email, timing: +6h, expected_uplift: +3.8% CR, confidence: 0.82, reasoning: "High purchase intent without incentive (would-buy probability 0.64); discount suppressed: low inventory + low price sensitivity ⇒ margin loss without uplift; bundle historically outperforms discount for this segment."`
- **Value:** margin protected; conversion nudged; decision defensible.

**UC2 — Do-nothing / wait decision**
- **Trigger:** routine batch decision run.
- **Input:** recently purchased, satisfied customer with high message-fatigue score.
- **Output:** `action: none, reasoning: "Contact now raises churn risk (fatigue signal); next evaluation in 7 days."`
- **Value:** demonstrates restraint — the differentiating behavior.

**UC3 — Segment-level interface/merchandising decision**
- **Trigger:** weekly segmentation run.
- **Process:** MCDA-constrained clustering selection → per-segment UI/merchandising variant assignment → 3WD-gated rollout in simulation.
- **Output:** segment definitions with viability scores; variant assignments; experiment verdicts.
- **Value:** operationalizes the anchor paper's proven mechanism (+27.6% CR / +68.1% AOV ceiling evidence).

**UC4 — Experiment adjudication (3WD)**
- **Trigger:** an experiment reaches its evaluation window.
- **Input:** variant vs. control metrics (CR, AOV, PCR micro-conversions), MDE, indifference margin.
- **Output:** Accept / Reject / **Delay** with the statistical rationale; Delay schedules continued data collection.
- **Value:** prevents premature ship/kill; the portfolio's most novel visible artifact.

### Secondary

- **UC5 — Cold-start routing:** anonymous/new user → default variant of the best-performing generalized cluster, with explicit "cold-start" reasoning. `[Evidence: cold-start fallback named in corpus future work]`
- **UC6 — Override-as-feedback:** manager overrides a decision; the override is logged as a high-weight signal and surfaces in evaluation. `[Evidence: semi-adaptive literature treats overrides as prime reward signals]`
- **UC7 — Policy comparison for the data scientist:** run rules-only vs. ML vs. bandit policy over the same simulated horizon; produce the comparison report.

### Edge cases

- Conflicting constraints (campaign mandates promotion; inventory forbids it) → deterministic precedence rules + flag for human review.
- Insufficient data / low confidence → decision degrades to safe default with "low confidence" reasoning, never a fabricated certainty.
- Constraint-infeasible action set (everything filtered) → `action: none` with the filter trace.
- Simulator drift scenario → scheduled re-segmentation demonstrates the closed loop.

---

## 5. Scope

### MVP — the smallest complete valuable system

`[Decision]` MVP = one closed loop, end to end, on simulated data:

1. **Event ingestion:** canonical event schema; simulator emits sessions/orders/campaign exposures; loader into DuckDB/Postgres.
2. **Feature layer:** customer behavior features (recency/frequency/monetary, session dynamics, category affinity, price-sensitivity proxy, fatigue), point-in-time correct.
3. **Predictive models:** rule baseline + gradient-boosted response/propensity models, calibrated; SHAP attributions.
4. **Segmentation:** ≥2 clustering candidates evaluated by an MCDA wrapper with business-viability constraints.
5. **Decision engine:** candidate action generation → constraint filtering → expected-value ranking → decision object (typed).
6. **Explanation layer:** templated reasoning composed from model attributions + fired constraints.
7. **Evaluation framework:** policy comparison in simulation; 3WD gateway adjudicating at least one variant experiment; metrics report.
8. **Headless API + thin demo:** FastAPI decision endpoint + minimal dashboard/CLI walkthrough of UC1/UC2.
9. **Engineering floor:** tests, experiment tracking, seeded reproducibility, docs.

### Stretch goals (ruthlessly ordered)

1. **Contextual bandit policy** (LinUCB/Thompson) with off-policy evaluation against logged data — highest research-alignment payoff.
2. **Timing/channel as decision dimensions** (beyond act/don't-act).
3. **Dynamic 3WD thresholds** (traffic/seasonality-aware MDE) — corpus-flagged novelty.
4. **Uplift modeling** (T-/X-learner) replacing propensity-only targeting.
5. **Longitudinal cohort tracking** (fatigue, LTV proxy over simulated months).
6. **Guarded content plugin:** pre-generated, catalog-validated copy variants (GenUI in its safe form only).
7. **Adapters:** GA4/CSV/Postgres ingestion adapters proving the headless claim.

Explicitly not even stretch: real-time serving infra, deep RL, federated learning, live LLM UI generation.
