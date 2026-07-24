# Requirements (PRD intel)

Extracted from classified PRD sources. Paths are relative to project root.

Source PRDs:
- `PRODUCT_CHARTER.md` — the only PRD in this ingest set

Note: `REQ-timing-channel-*` was raised as competing variants by synthesis and resolved by the
user on 2026-07-24 via a split (see `.planning/INGEST-CONFLICTS.md`). The two variants below are
now scoped requirements, not open alternatives: `REQ-timing-channel-mvp` (fixed archetype
parameters, MVP) and `REQ-timing-channel-optimized` (ranked decision dimensions, stretch).

---

## REQ-decision-not-prediction
- source: PRODUCT_CHARTER.md (O1)
- description: The system returns a decision, not a prediction, for any evaluated customer state.
- acceptance: For any evaluated customer state, the system returns a complete decision object (action, expected impact, confidence, reasoning, constraints considered) — including the actions *offer nothing* and *wait*.
- scope: decision engine, decision contract

## REQ-beat-naive-policies
- source: PRODUCT_CHARTER.md (O2)
- description: The decision policy must outperform naive baseline policies in offline simulation.
- acceptance: In offline simulation, the decision policy achieves higher cumulative constrained profit than (a) "always discount", (b) "always recommend top-seller", and (c) "do nothing" baselines, with confidence intervals reported.
- scope: policy evaluation, baselines

## REQ-business-viable-segmentation
- source: PRODUCT_CHARTER.md (O3)
- description: Segmentation must be business-viable, not merely statistically optimal.
- acceptance: Every produced segment satisfies configured viability constraints (minimum size, maximum segment count, activity diversity); MCDA scoring of candidate clustering methods is reproducible.
- scope: segmentation, MCDA

## REQ-safe-experimentation-3wd
- source: PRODUCT_CHARTER.md (O4)
- description: Every simulated policy or UI change is routed through the three-way decision gateway.
- acceptance: Every simulated policy/UI change is routed through the three-way decision gateway (Accept / Reject / Delay) with explicit thresholds and indifference margins.
- scope: experimentation gateway, 3WD

## REQ-explainable-by-default
- source: PRODUCT_CHARTER.md (O5)
- description: Explanations ship with every decision by default.
- acceptance: 100% of decisions carry a reasoning payload renderable as one paragraph a marketing manager can read; model-level attributions (SHAP or equivalent) available on demand.
- scope: explanation engine

## REQ-reproducible-pipeline
- source: PRODUCT_CHARTER.md (O6)
- description: The full pipeline is deterministically reproducible from a fresh clone.
- acceptance: A fresh clone plus one documented command regenerates the dataset, features, models, decisions, and evaluation report deterministically (seeded).
- scope: reproducibility

## REQ-demo-workflow-walkthrough
- source: PRODUCT_CHARTER.md (§2 Product metrics)
- description: The demo must walk a marketing-manager scenario end to end.
- acceptance: The demo walks inspect customer → see decision → read explanation → override → see override logged as feedback, in under 5 minutes.
- scope: demo surface, workflow

## REQ-decision-quality-restraint
- source: PRODUCT_CHARTER.md (§2 Product metrics)
- description: The system must demonstrably withhold incentives from would-buy-anyway customers, versus a naive discount policy.
- acceptance: >= X% of simulated decisions where "no incentive" was chosen for would-buy-anyway customers, versus 0% for the naive discount policy. Source states "X reported, not invented; target directionally positive and statistically supported" — the threshold X is left unspecified in the source.
- scope: decision quality, restraint

## REQ-adoption-proxy-readme
- source: PRODUCT_CHARTER.md (§2 Product metrics)
- description: A reviewer must be able to run the demo unaided.
- acceptance: A reviewer can run the demo from the README without assistance.
- scope: portfolio, onboarding

## REQ-model-performance-reporting
- source: PRODUCT_CHARTER.md (§2 Technical metrics)
- description: Model performance is reported honestly and multi-metrically.
- acceptance: Calibrated probabilities (reported Brier score / calibration curves), AUC/PR reported per model vs. baseline; no single-metric claims.
- scope: model evaluation

## REQ-decision-performance-reporting
- source: PRODUCT_CHARTER.md (§2 Technical metrics)
- description: Decision-level performance is reported with uncertainty.
- acceptance: Cumulative reward/regret curves for the bandit vs. static policies in simulation; uplift estimates with intervals.
- scope: decision evaluation

## REQ-api-latency
- source: PRODUCT_CHARTER.md (§2 Technical metrics)
- description: Single-decision API latency budget.
- acceptance: Single-decision API response < 500 ms on a laptop. Source assumption: adequate for batch/near-line marketing decisions; real-time UI serving is out of MVP scope.
- scope: API, non-functional

## REQ-reliability-reproducibility-ci
- source: PRODUCT_CHARTER.md (§2 Technical metrics)
- description: CI and seeded runs must be deterministic.
- acceptance: CI green; seeded end-to-end run produces byte-identical metrics tables.
- scope: CI, reproducibility

## REQ-portfolio-artifacts
- source: PRODUCT_CHARTER.md (§2 Portfolio metrics)
- description: Portfolio-grade documentation artifacts must exist.
- acceptance: Architecture explainable in one diagram plus one page; every non-obvious choice has an ADR; model cards for every trained model; assumption log for the simulator.
- scope: documentation, portfolio

## REQ-persona-surfaces
- source: PRODUCT_CHARTER.md (§3 Personas)
- description: The product must serve four personas through distinct surfaces.
- acceptance: P1 Marketing/CRM Manager ("Claudia") reads decision cards, approves/overrides, sets constraints (max discount, frequency caps) — will not read a notebook. P2 E-commerce Product Manager ("Jonas") consumes 3WD experiment verdicts (Accept/Reject/Delay + why) and configures MDE and indifference margins with guidance. P3 Data Scientist ("Priya") extends model/policy registries, runs offline evaluation and replay, reads experiment tracking via the Python API and config system. P4 CRM Specialist ("Marek") consumes per-customer action feeds (action + timing + channel + explanation) exported from the decision API.
- scope: personas, user surfaces

## REQ-uc1-next-best-action
- source: PRODUCT_CHARTER.md (UC1, primary/flagship)
- description: Next-best-action for an engaged high-value customer.
- acceptance: Trigger — customer session ends with cart abandonment. Input — Austrian customer, 7 visits to winter jackets, item in cart, high LTV, low modeled price sensitivity, jacket inventory low, pre-Christmas season, cold-weather context. Process — feature assembly → response/propensity predictions per candidate action → constraint filtering (low inventory ⇒ suppress discount; frequency cap check) → expected-value ranking → explanation. Output — `action: premium_bundle_email, timing: +6h, expected_uplift: +3.8% CR, confidence: 0.82` with reasoning "High purchase intent without incentive (would-buy probability 0.64); discount suppressed: low inventory + low price sensitivity ⇒ margin loss without uplift; bundle historically outperforms discount for this segment."
- scope: decision engine, flagship use case

## REQ-uc2-do-nothing-wait
- source: PRODUCT_CHARTER.md (UC2, primary)
- description: Do-nothing / wait decision demonstrating restraint.
- acceptance: Trigger — routine batch decision run. Input — recently purchased, satisfied customer with high message-fatigue score. Output — `action: none, reasoning: "Contact now raises churn risk (fatigue signal); next evaluation in 7 days."`
- scope: decision engine, restraint

## REQ-uc3-segment-interface-decision
- source: PRODUCT_CHARTER.md (UC3, primary)
- description: Segment-level interface/merchandising decision.
- acceptance: Trigger — weekly segmentation run. Process — MCDA-constrained clustering selection → per-segment UI/merchandising variant assignment → 3WD-gated rollout in simulation. Output — segment definitions with viability scores; variant assignments; experiment verdicts.
- scope: segmentation, merchandising, 3WD

## REQ-uc4-experiment-adjudication
- source: PRODUCT_CHARTER.md (UC4, primary)
- description: Experiment adjudication via 3WD.
- acceptance: Trigger — an experiment reaches its evaluation window. Input — variant vs. control metrics (CR, AOV, PCR micro-conversions), MDE, indifference margin. Output — Accept / Reject / **Delay** with the statistical rationale; Delay schedules continued data collection.
- scope: experimentation gateway

## REQ-uc5-cold-start-routing
- source: PRODUCT_CHARTER.md (UC5, secondary)
- description: Cold-start routing for anonymous or new users.
- acceptance: Anonymous/new user routed to the default variant of the best-performing generalized cluster, with explicit "cold-start" reasoning.
- scope: cold start

## REQ-uc6-override-as-feedback
- source: PRODUCT_CHARTER.md (UC6, secondary)
- description: Manager overrides become feedback signal.
- acceptance: Manager overrides a decision; the override is logged as a high-weight signal and surfaces in evaluation.
- scope: human-in-the-loop, feedback

## REQ-uc7-policy-comparison
- source: PRODUCT_CHARTER.md (UC7, secondary)
- description: Policy comparison for the data scientist.
- acceptance: Run rules-only vs. ML vs. bandit policy over the same simulated horizon; produce the comparison report.
- scope: policy evaluation

## REQ-edge-case-handling
- source: PRODUCT_CHARTER.md (§4 Edge cases)
- description: Defined behavior for four edge cases.
- acceptance: Conflicting constraints (campaign mandates promotion; inventory forbids it) → deterministic precedence rules plus flag for human review. Insufficient data / low confidence → decision degrades to safe default with "low confidence" reasoning, never a fabricated certainty. Constraint-infeasible action set (everything filtered) → `action: none` with the filter trace. Simulator drift scenario → scheduled re-segmentation demonstrates the closed loop.
- scope: edge cases, failure handling

## REQ-mvp-event-ingestion
- source: PRODUCT_CHARTER.md (§5 MVP #1)
- description: Event ingestion into analytical storage.
- acceptance: Canonical event schema; simulator emits sessions/orders/campaign exposures; loader into DuckDB/Postgres.
- scope: MVP, ingestion

## REQ-mvp-feature-layer
- source: PRODUCT_CHARTER.md (§5 MVP #2)
- description: Point-in-time-correct customer behavior features.
- acceptance: Customer behavior features (recency/frequency/monetary, session dynamics, category affinity, price-sensitivity proxy, fatigue), point-in-time correct.
- scope: MVP, features

## REQ-mvp-predictive-models
- source: PRODUCT_CHARTER.md (§5 MVP #3)
- description: Baseline plus gradient-boosted calibrated models.
- acceptance: Rule baseline plus gradient-boosted response/propensity models, calibrated; SHAP attributions.
- scope: MVP, models

## REQ-mvp-segmentation
- source: PRODUCT_CHARTER.md (§5 MVP #4)
- description: MCDA-wrapped clustering with business-viability constraints.
- acceptance: >= 2 clustering candidates evaluated by an MCDA wrapper with business-viability constraints. (Note: ARCHITECTURAL_DIRECTION.md §2.3, a locked ADR, mandates K-means, GMM, BIRCH at minimum — i.e. >= 3. See INGEST-CONFLICTS.md INFO.)
- scope: MVP, segmentation

## REQ-mvp-decision-engine
- source: PRODUCT_CHARTER.md (§5 MVP #5)
- description: The core decision pipeline.
- acceptance: Candidate action generation → constraint filtering → expected-value ranking → decision object (typed).
- scope: MVP, decision engine

## REQ-mvp-explanation-layer
- source: PRODUCT_CHARTER.md (§5 MVP #6)
- description: Templated explanation composition.
- acceptance: Templated reasoning composed from model attributions plus fired constraints.
- scope: MVP, explanation

## REQ-mvp-evaluation-framework
- source: PRODUCT_CHARTER.md (§5 MVP #7)
- description: Offline evaluation and 3WD adjudication.
- acceptance: Policy comparison in simulation; 3WD gateway adjudicating at least one variant experiment; metrics report.
- scope: MVP, evaluation

## REQ-mvp-headless-api-demo
- source: PRODUCT_CHARTER.md (§5 MVP #8)
- description: Headless API plus a thin demo surface.
- acceptance: FastAPI decision endpoint plus minimal dashboard/CLI walkthrough of UC1/UC2.
- scope: MVP, API, demo

## REQ-mvp-engineering-floor
- source: PRODUCT_CHARTER.md (§5 MVP #9)
- description: Baseline engineering hygiene.
- acceptance: Tests, experiment tracking, seeded reproducibility, docs.
- scope: MVP, engineering

## REQ-timing-channel-mvp (MVP — resolved from competing variant)
- source: PRODUCT_CHARTER.md (UC1, §4 Primary use cases); DECISION_ENGINE_DESIGN.md §3 (SPEC); OPEN_DECISIONS.md OD-10
- description: Timing and channel ship in MVP as fixed parameters of the action archetypes, and are carried in the Decision contract — but are not searched or optimized.
- acceptance: The Decision contract includes `action.params.send_delay_hours` and `action.params.channel` per DECISION_ENGINE_DESIGN.md §3. The ~8 MVP action archetypes (OD-10) include `email-now` and `email-delayed`, each with its timing/channel fixed by the archetype definition rather than chosen by the policy. UC1 renders `timing: +6h` from the selected archetype's parameters. The policy ranks over archetypes; it does not search a delay or channel grid.
- scope: timing, channel, action space, Decision contract
- resolution: User-resolved 2026-07-24. Split from REQ-timing-channel-v1/v2 competing variants. Reconciles PRODUCT_CHARTER.md UC1 + the SPEC Decision contract (which require timing/channel present in MVP) with ARCHITECTURAL_DIRECTION.md §4 locked ADR (which lists timing/channel *decision dimensions* as Optional). The distinction is present-as-parameter vs. optimized-as-dimension.

## REQ-timing-channel-optimized (STRETCH — resolved from competing variant)
- source: PRODUCT_CHARTER.md (§5 Stretch goals #2); ARCHITECTURAL_DIRECTION.md §4 (locked ADR, Optional Capabilities)
- description: Timing and channel promoted to optimized decision dimensions the policy ranks over.
- acceptance: "Timing/channel as decision dimensions (beyond act/don't-act)" per stretch goal #2, ordered after the contextual bandit policy. The policy searches over a delay/channel parameter grid rather than selecting a fixed archetype. Satisfies ARCHITECTURAL_DIRECTION.md §4 "timing/channel decision dimensions" under Optional Capabilities.
- scope: timing, channel, action space, optimization layer
- resolution: User-resolved 2026-07-24. Stretch half of the REQ-timing-channel split; depends on REQ-timing-channel-mvp.

## REQ-stretch-contextual-bandit
- source: PRODUCT_CHARTER.md (§5 Stretch #1)
- description: Contextual bandit policy with off-policy evaluation.
- acceptance: Contextual bandit policy (LinUCB/Thompson) with off-policy evaluation against logged data — highest research-alignment payoff.
- scope: stretch, policy

## REQ-stretch-dynamic-3wd-thresholds
- source: PRODUCT_CHARTER.md (§5 Stretch #3)
- description: Traffic/seasonality-aware 3WD thresholds.
- acceptance: Dynamic 3WD thresholds (traffic/seasonality-aware MDE) — corpus-flagged novelty.
- scope: stretch, 3WD

## REQ-stretch-uplift-modeling
- source: PRODUCT_CHARTER.md (§5 Stretch #4)
- description: Explicit uplift learners replacing propensity-only targeting.
- acceptance: Uplift modeling (T-/X-learner) replacing propensity-only targeting.
- scope: stretch, uplift

## REQ-stretch-longitudinal-cohort
- source: PRODUCT_CHARTER.md (§5 Stretch #5)
- description: Longitudinal cohort tracking in simulation.
- acceptance: Longitudinal cohort tracking (fatigue, LTV proxy over simulated months).
- scope: stretch, longitudinal metrics

## REQ-stretch-content-plugin
- source: PRODUCT_CHARTER.md (§5 Stretch #6)
- description: Guarded generative content plugin.
- acceptance: Pre-generated, catalog-validated copy variants (GenUI in its safe form only).
- scope: stretch, generative content

## REQ-stretch-adapters
- source: PRODUCT_CHARTER.md (§5 Stretch #7)
- description: Ingestion adapters proving the headless claim.
- acceptance: GA4/CSV/Postgres ingestion adapters proving the headless claim.
- scope: stretch, adapters

## REQ-explicit-exclusions
- source: PRODUCT_CHARTER.md (§5 Scope)
- description: Items excluded even from stretch scope.
- acceptance: Explicitly not even stretch — real-time serving infra, deep RL, federated learning, live LLM UI generation.
- scope: scope exclusions
