# Roadmap: NextMove — Behavioral Decision Engine for E-commerce Personalization

## Overview

The MVP is one closed loop, not nine stacked layers. This roadmap deliberately refuses the
horizontal split implied by `PRODUCT_CHARTER.md` §5's nine numbered components — building all the
ingestion, then all the models, then all the API would mean nothing works until the end.

Instead: **Phase 1** builds the simulated world and the engineering floor, because no public
dataset contains the action→response counterfactuals this project is about, which makes the
simulator the primary data source and a prerequisite for everything downstream. **Phase 2** cuts a
complete vertical slice through the whole nine-component pipeline on a rule baseline — a running
service that answers "what should we do for this customer?" with a constraint-legal, self-explaining
`Decision`, including the decision to do nothing. **Phase 3** builds the evaluation gateway *before*
the learned layer, because the project's own rule is that promotion requires beating the incumbent on
decision-level metrics — you cannot honestly promote a model without the gateway that judges it, and
the 3WD gateway is the flagship differentiator, not final polish. **Phase 4** then earns the learned
layer: calibrated models, SHAP into explanations, and MCDA-selected segments, each of which must
survive the gateway built in Phase 3. **Phase 5** turns a working system into a reviewable artifact:
one-command reproduction, the UC1/UC2 walkthrough, and the honest three-axis report.

Each phase deepens the same loop rather than adding a disconnected tier.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Reproducible World** - A seeded simulated e-commerce world, canonical event log, point-in-time features, and the engineering floor that makes every later claim checkable
- [ ] **Phase 2: The Decision Spine** - A running service that returns a constraint-legal, self-explaining, reproducible `Decision` — including `none` — from a rule baseline
- [ ] **Phase 3: The Evaluation Gateway** - Accept / Reject / Delay adjudication and policy replay, so nothing can be promoted without proving it earned promotion
- [ ] **Phase 4: The Learned Layer** - Calibrated models and business-viable segments replace hand-written guesses, judged by the Phase 3 gateway
- [ ] **Phase 5: Portfolio Proof** - One-command reproduction, the UC1/UC2 walkthrough, and an honest three-axis report a reviewer can read in five minutes

## Phase Details

### Phase 1: Reproducible World

**Goal**: A clean clone produces a complete, queryable, deterministic simulated e-commerce history — the data foundation every later claim rests on — with the module boundaries, config discipline, and ratified decisions that keep it honest.
**Depends on**: Nothing (first phase)
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04, DATA-01, DATA-02, DATA-03, DATA-04, FEAT-01, FEAT-02, ENG-01, ENG-03, ENG-04, ENG-08, ENG-09, DOC-01
**Success Criteria** (what must be TRUE):

  1. One command on a clean laptop regenerates the full simulated history — customers with latent price sensitivity, loyalty and fatigue; a seasonal catalog; inventory; campaigns; sessions, views, add-to-carts, orders, campaign exposures and micro-conversion events — into canonical event tables and point-in-time feature tables, byte-identical across two seeded runs, with no cloud dependency.
  2. Every derived table states the content hashes of its inputs and the config hash that produced it, and malformed or semantically invalid events (negative price, non-monotonic session timestamps, unknown SKU) land in a quarantine table with a stated reason or fail the run — never enter the store silently.
  3. A feature row read `as_of` a past timestamp contains no information created after that timestamp, proven by leakage tests in the suite; no evaluation split anywhere in the repo is random over behavioral time.
  4. CI fails the build if any module in `models/`, `decisions/`, `policies/` or `features/` imports the simulator package.
  5. A reviewer can open `SIMULATOR_ASSUMPTIONS.md` and `docs/adr/001`–`010` and find every generative assumption and every ratified open decision written down — including an explicit ADR resolving OD-7 (DVC vs. content-hashed artifact store) — and can change the seasonality curve, the feature list, or a simulator parameter by editing schema-validated YAML rather than code.

**Plans**: 11 plans

Plans:
**Wave 1**

- [ ] 01-01-PLAN.md — Toolchain, ten-package skeleton, test harness (ENG-01, ENG-08)
- [ ] 01-02-PLAN.md — ADRs 001–010 ratifying OD-1..OD-10; docs/ relocation (DOC-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-03-PLAN.md — Layered config, Pydantic validation, stable config hash, seeds (ENG-03, ENG-04)
- [ ] 01-04-PLAN.md — Import-linter boundary contracts and Linux-only CI (SIM-02, ENG-01)
- [ ] 01-05-PLAN.md — Canonical event schema and inward-only adapter seam (DATA-01)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-06-PLAN.md — Storage repository layer, content-hash lineage, DVC (DATA-04, ENG-01, ENG-04, ENG-09)
- [ ] 01-07-PLAN.md — Simulator world: per-entity RNG, clock, latent traits, seasonal catalog (SIM-01)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 01-08-PLAN.md — Daily tick, response functions, micro-events, UC1/UC2 occurrence (SIM-01, SIM-04)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 01-09-PLAN.md — Ingest validation, quarantine, semantic gates, DQ summary (DATA-02, DATA-03)

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 01-10-PLAN.md — Point-in-time feature layer, leakage proofs, time-aware splits (FEAT-01, FEAT-02)

**Wave 7** *(blocked on Wave 6 completion)*

- [ ] 01-11-PLAN.md — DVC pipeline, `just reproduce`, determinism proof, SIMULATOR_ASSUMPTIONS.md (ENG-04, ENG-08, ENG-09, SIM-03)

### Phase 2: The Decision Spine

**Goal**: Anyone can ask the running service what to do next for a given customer and receive a constraint-legal, self-explaining, reproducible `Decision` — including the decision to do nothing — produced end to end through the whole pipeline on a rule baseline.
**Depends on**: Phase 1
**Requirements**: MODEL-01, DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07, DEC-08, DEC-09, DEC-10, EXPL-01, EXPL-02, EXPL-03, API-01, API-02, API-03, API-04, ENG-02
**Success Criteria** (what must be TRUE):

  1. `POST /v1/decisions` with a valid context returns a schema-valid `Decision` in under 500 ms on a laptop — chosen archetype with its fixed `send_delay_hours` and `channel` (so UC1 renders `timing: +6h`), expected outcome with interval, confidence, and `none` and `wait` always present in `candidates_considered` — and no field is ever fabricated: unavailable values are `null` with a stated reason.
  2. Surviving candidates are ranked by expected constrained profit (`E[uplift] × margin − cost − risk_penalty`) with an uncertainty penalty, produced by the documented rule baseline policy, and the runner-up and its score gap are always reported.
  3. A marketing manager can read the `reasoning` paragraph and name the chosen action, the decisive constraint, and why the runner-up lost — with no LLM anywhere in the path and no surveillance-framed phrasing — and can reverse the call through `POST /v1/decisions/{id}/override`, which persists the alternative as an event.
  4. Across 10,000 randomized contexts the engine never emits an action a hard constraint excluded; conflicting constraints resolve by `compliance > inventory > campaign > preference`, and an unresolvable conflict or a fully-filtered candidate set returns `action: none` with the filter trace and `needs_human_review`.
  5. The same `(context, config hash, model versions, seed)` yields a byte-identical `Decision` every run with versions and config hash embedded in the response, and a new `Constraint` plus a new `ActionProvider` can be registered — YAML plus a plugin module — without editing any core package.

**Plans**: TBD

### Phase 3: The Evaluation Gateway

**Goal**: Nothing gets promoted on assertion. Every policy or variant change must survive an explicit Accept / Reject / Delay verdict, and any policy can be replayed against the same simulated horizon and compared on cumulative constrained profit.
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-06, EVAL-07, API-05
**Success Criteria** (what must be TRUE):

  1. `GET /v1/experiments/{id}` returns Accept, Reject, or **Delay** together with the metrics, MDE, indifference margin, effect size and the statistical rationale behind the verdict — and the fixture suite reproduces the correct verdict for clear-win, clear-loss, in-margin, and conflicting-metric (CR ↑ / AOV ↓) cases.
  2. A Delay verdict that exhausts its configured delay budget escalates into the `needs_human_review` queue instead of looping indefinitely.
  3. One command replays any registered policy over the same simulated horizon and emits a comparison of cumulative constrained profit with confidence intervals, covering do-nothing, always-discount, always-top-seller and the rules-only policy.
  4. The comparison states the measured share of decisions that withheld an incentive from customers the simulator says would have bought anyway, next to the naive discount policy's 0% — reported as measured, never invented.
  5. A manager override is stored as a high-weight labeled event and appears as a distinct signal in the next evaluation run, and the same engine that answers a single API call also materializes decisions across the whole population as a per-customer CSV action feed (action, timing, channel, explanation).

**Plans**: TBD

### Phase 4: The Learned Layer

**Goal**: Calibrated models and business-viable segments replace hand-written guesses inside the engine — and the gateway from Phase 3 decides whether they earned their place, with the honest negative allowed.
**Depends on**: Phase 3
**Requirements**: MODEL-02, MODEL-03, MODEL-04, MODEL-05, MODEL-06, MODEL-07, SEG-01, SEG-02, SEG-03, SEG-04, DEC-11, EXPL-04, ENG-07, EVAL-08
**Success Criteria** (what must be TRUE):

  1. Every decision-path model ships with a reliability curve and Brier score, and miscalibration beyond the configured bound fails the pipeline gate rather than shipping quietly.
  2. The comparison adds the GBM-driven policy and states, with confidence intervals, whether it beats the rule baseline on decision-level replay profit — and if it does not, the report says so and the baseline stays in place; every trained model has a model card and every training and evaluation run is an MLflow run whose ID is cited where its numbers appear.
  3. Explanations now cite the model's top attributions alongside the fired constraints; uplift is reported as `P(convert|action) − P(convert|none)` with its measured error against simulator ground truth as a headline section; and a sampled decision review scores median ≥ 4 on faithfulness, completeness, readability, framing and honesty with no faithfulness score below 3.
  4. `GET /v1/segments` returns segments produced by an MCDA-selected clustering method chosen from at least K-means, GMM and BIRCH under all four configured viability constraints — minimum size, maximum cluster count, activity diversity, compute cost — with the scorecard, weights, ranking and weight-sensitivity analysis attached.
  5. An anonymous or brand-new customer gets a deterministic cold-start route to the best generalized cluster's default with "cold-start" stated in the reasoning; a low-confidence context degrades to a safe default that says so rather than presenting a guess as certainty; and a simulated drift epoch triggers scheduled re-segmentation and retraining that flows back through the 3WD gateway.

**Plans**: TBD

### Phase 5: Portfolio Proof

**Goal**: A reviewer with a clean clone and five minutes can run the system, walk both flagship scenarios without touching code, and read an honest three-axis account of how well it actually works.
**Depends on**: Phase 4
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04, EVAL-05, ENG-05, ENG-06, DOC-02
**Success Criteria** (what must be TRUE):

  1. `make reproduce` on a clean clone completes end to end and reproduces the published metrics tables exactly, and CI runs the miniature version green on every push with `rules/`, `decisions/` and `evaluate/` above 85% line coverage and the suite above 75% overall.
  2. A reviewer following only the README walks UC1 through the demo surface — inspect customer → see decision → read explanation → override → see the override reflected in evaluation — in under five minutes without touching code.
  3. The same surface walks UC2: a recently-purchased, fatigued customer receives `action: none` with reasoning of the form "contact now raises churn risk (fatigue signal); next evaluation in 7 days" — and a manager can change the discount ceiling or frequency cap from documented config and watch the decision change.
  4. Everything the demo displays is obtainable from the public `/v1` API — the dashboard holds no privileged access and could be deleted without losing capability.
  5. The published three-axis report covers prediction, decision and system quality; every headline number traces to an MLflow run ID and carries its "in simulation" caveat; and a mandatory failure-analysis section names the worst decisions, constraint conflicts, delay-loop incidents and reward-hacking probes.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Reproducible World | 0/11 | Planned | - |
| 2. The Decision Spine | 0/TBD | Not started | - |
| 3. The Evaluation Gateway | 0/TBD | Not started | - |
| 4. The Learned Layer | 0/TBD | Not started | - |
| 5. Portfolio Proof | 0/TBD | Not started | - |

**Coverage:** 64 / 64 v1 requirements mapped · 0 orphans

**Deferred to v2** (ordered, see `.planning/REQUIREMENTS.md`): POL-01 contextual bandit + OPE →
POL-02 timing/channel as optimized dimensions → EXP-01 dynamic 3WD thresholds → POL-03 uplift
learners → LONG-01 longitudinal cohorts → CONT-01 guarded content plugin → ADPT-01/02 adapters and
public-dataset validation.
