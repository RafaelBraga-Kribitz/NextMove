# Constraints (SPEC intel)

Extracted from classified SPEC sources. Paths are relative to project root.

Source SPECs:
- `DECISION_ENGINE_DESIGN.md` — decision engine contract and pipeline
- `QUALITY_BAR.md` — acceptance criteria, definition of done, anti-patterns, debt policy, docs standards, rubric

---

## Decision objective function
- source: DECISION_ENGINE_DESIGN.md (§1)
- type: protocol
- content: The system does not answer "Will this customer buy?" — it answers "What should the company do next, and is doing nothing the best option?" Formally, for customer *c* at time *t* with business state *B*: `a* = argmax over a ∈ A_eligible(c, t, B) of: E[uplift(a | c, t)] × margin(a, B) − cost(a) − risk_penalty(a, c)`, subject to hard constraints `C(c, t, B)`.

## Restraint is a first-class action
- source: DECISION_ENGINE_DESIGN.md (§1)
- type: protocol
- content: The action set `A` always includes `none` and `wait(Δt)`. Stated rationale: a system that cannot recommend "do nothing" cannot be trusted with discounts.

## Counterfactual, not observational scoring
- source: DECISION_ENGINE_DESIGN.md (§1)
- type: protocol
- content: The score is expected *incremental* value, not raw purchase probability. MVP approximates uplift via response models conditioned on action (assumption: simulator ground truth lets us quantify how wrong this approximation is); stretch replaces it with explicit uplift learners.

## Hard vs. soft constraint separation is declarative
- source: DECISION_ENGINE_DESIGN.md (§1)
- type: protocol
- content: Hard constraints remove actions before ranking; soft constraints penalize within ranking. The distinction is declarative config, never code.

## Uncertainty is carried on every score
- source: DECISION_ENGINE_DESIGN.md (§1)
- type: protocol
- content: Every score carries an interval; the decision confidence derives from model calibration plus score gap to the runner-up.

## Decision inputs: customer context
- source: DECISION_ENGINE_DESIGN.md (§2)
- type: schema
- content: Identity and tenure; segment assignment (with cold-start flag); behavior features (RFM, session dynamics — visits, depth, dwell — category affinity, cart state, abandonment history, micro-conversion aggregates); history (past actions received, responses, overrides, fatigue counters); modeled values (propensity per action, price sensitivity, churn/fatigue risk, LTV estimate).

## Decision inputs: business context
- source: DECISION_ENGINE_DESIGN.md (§2)
- type: schema
- content: Inventory levels and scarcity flags per SKU/category; margin per product/bundle and incentive cost schedule; active campaigns, mandated promotions and brand-safety rules; seasonality calendar (e.g. pre-Christmas peak).

## Decision inputs: environmental context
- source: DECISION_ENGINE_DESIGN.md (§2)
- type: schema
- content: Time (hour/day/season), device/channel availability; optional exogenous signals (e.g. weather) — simulator-provided, adapter-shaped, modeled as a generic `context_signal` event so real integrations slot in later.

## Decision object — the public contract
- source: DECISION_ENGINE_DESIGN.md (§3)
- type: api-contract
- content: Fields — `decision_id` (uuid), `customer_id`, `as_of` (timestamp), `action` {`type` from the action catalog, `params` e.g. {bundle_id, send_delay_hours, channel}}, `expected_outcome` {`metric`, `estimate`, `interval`, `horizon_days`}, `confidence` (calibrated), `reasoning` (manager-readable paragraph), `reasoning_trace` {`candidates_considered`, `filtered` [{action, rule, detail}], `scores`, `runner_up` {action, score_gap}, `model_attributions` [{feature, weight}]}, `constraints_considered` (list), `policy` {`name`, `model_versions`, `config_hash`}.

## Decision contract rules
- source: DECISION_ENGINE_DESIGN.md (§3)
- type: api-contract
- content: No field may be fabricated; if a value is unavailable, it is `null` with a reason; `reasoning` must be renderable to a marketing manager without edits.

## Decision pipeline stages
- source: DECISION_ENGINE_DESIGN.md (§4)
- type: protocol
- content: Observation → Prediction → Action generation → Constraint filtering → Ranking → Explanation → (Feedback). (1) Observation assembles point-in-time context (feature lookup plus business state); missing data is explicit, never silently imputed at this layer. (2) Prediction scores each (customer, action) pair with calibrated models and attaches attributions. (3) Action generation: the `ActionProvider` registry expands the action catalog into concrete parameterized candidates (which bundle, which discount tier, which delay) and always appends `none` and `wait`. (4) Constraint filtering: hard rules eliminate candidates and record why. (5) Decision ranking: the active `Policy` ranks survivors by expected constrained profit with uncertainty penalty; the bandit policy (stretch) may explore only within survivors. (6) Explanation composes reasoning from attributions (relevance-framed), fired constraints, and runner-up counterfactual. (7) Feedback: outcomes, overrides, and experiment verdicts flow to the evaluation store; overrides are high-weight labeled events; scheduled jobs re-segment/retrain and route material policy changes through the 3WD gateway.

## Constraint conflict precedence
- source: DECISION_ENGINE_DESIGN.md (§4.4)
- type: protocol
- content: Conflicting constraints resolve by declared precedence: `compliance > inventory > campaign > preference`. Unresolvable conflicts emit `action: none` plus `needs_human_review`.

## Engine design rules
- source: DECISION_ENGINE_DESIGN.md (§5)
- type: protocol
- content: Rules bound learning, never the reverse — no learned component may emit an action a rule has excluded (property-tested). The engine is deterministic given (context, config, model versions, seed); exploration randomness is seeded and logged. Every decision is replayable — the trace plus versions suffice to reproduce it byte-for-byte. The utility function is config, not code — margin weights, fatigue penalty, and risk aversion live in reviewed YAML, so changing business posture must not require a deploy. Human-in-the-loop surfaces: override endpoint, `needs_human_review` queue, 3WD Delay escalation after budget exhaustion. Failure honesty: low confidence ⇒ safe default plus explicit statement; the engine must never present a guess as certainty.

---

## AC-1: Decision endpoint returns a schema-valid Decision
- source: QUALITY_BAR.md (§1)
- type: api-contract
- content: For any valid context, `POST /v1/decisions` returns a schema-valid Decision including `none`/`wait` in `candidates_considered`; verified by contract tests.

## AC-2: No decision contains a hard-constraint-excluded action
- source: QUALITY_BAR.md (§1)
- type: protocol
- content: No decision ever contains an action excluded by a hard constraint; property-based test over randomized contexts, >= 10k cases, zero violations.

## AC-3: Decision determinism
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: Given fixed (context, config hash, model versions, seed), the decision is byte-identical across runs (golden-file test).

## AC-4: Reasoning completeness
- source: QUALITY_BAR.md (§1)
- type: api-contract
- content: 100% of decisions include non-empty `reasoning` and structured `reasoning_trace` with fired rules and runner-up.

## AC-5: Calibration gate
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: A calibration report (reliability curve plus Brier) exists for every decision-path model; miscalibration beyond a configured bound fails the pipeline gate.

## AC-6: GBM vs. baseline, with an honest-negative escape hatch
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: GBM models beat the rule baseline on decision-level replay profit with reported confidence intervals — or the report explicitly states they don't and the baseline ships.

## AC-7: Segmentation viability and MCDA scorecard
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: Every produced segmentation satisfies configured viability constraints (min size, max clusters); the MCDA scorecard (criteria matrix, weights, ranking) is emitted per run. (Note: ARCHITECTURAL_DIRECTION.md §2.3, a locked ADR, additionally mandates activity diversity and compute cost as configured constraints. See INGEST-CONFLICTS.md INFO.)

## AC-8: 3WD verdict fixture suite
- source: QUALITY_BAR.md (§1)
- type: protocol
- content: The 3WD gateway reproduces correct Accept/Reject/Delay verdicts on a fixture suite covering clear-win, clear-loss, in-margin, and conflicting-metric cases.

## AC-9: Delay budget escalation
- source: QUALITY_BAR.md (§1)
- type: protocol
- content: A Delay verdict past its configured budget escalates to `needs_human_review` (integration test).

## AC-10: Policy comparison report
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: The policy comparison report shows cumulative constrained profit for {do-nothing, always-discount, top-seller, rules-only, ML policy} over the same simulated horizon with intervals; regenerable by one command.

## AC-11: One-command reproduction
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: `make reproduce` on a clean clone completes end-to-end and reproduces the published metrics tables exactly (seeded); CI runs the miniature version green.

## AC-12: Test coverage thresholds
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: Test coverage of `rules/`, `decisions/`, `evaluate/` >= 85% lines; overall >= 75%.

## AC-13: Registry extensibility without core edits
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: Adding a new Constraint and a new ActionProvider via the registries requires zero core-module edits, demonstrated by an example plugin in-repo.

## AC-14: UC1 walkthrough via the demo surface
- source: QUALITY_BAR.md (§1)
- type: nfr
- content: The UC1 walkthrough (inspect → decision → explanation → override → override visible in evaluation) completes via the demo surface without touching code.

## Definition of Done
- source: QUALITY_BAR.md (§2)
- type: nfr
- content: Product — UC1–UC4 implemented and demoable; override loop closed; constraint config documented for the manager persona. Engineering — all ACs green in CI; API OpenAPI-documented; runbook for the pipeline; no unreviewed TODOs in decision-path code. Data science — three-axis evaluation report (prediction / decision / system) published; baseline comparison honest; simulator assumption log complete; failure-analysis section written; model cards for all trained models. Portfolio — README with 90-second pitch, architecture diagram, quickstart, and results table; ADR log covering every resolved open decision; demo script or recording; explanation style guide.

## Prohibited anti-patterns
- source: QUALITY_BAR.md (§3)
- type: nfr
- content: (1) Notebook-only implementation — notebooks allowed for exploration under `notebooks/`, never as pipeline. (2) Magic AI components — no component whose behavior cannot be explained by its inputs, config, and versioned artifacts; no LLM in the decision or explanation path. (3) Unexplained models — a model without attributions and a model card cannot enter the decision path. (4) Hardcoded business rules — business numbers in code = rejected change; all thresholds/weights in schema-validated config. (5) Fake metrics — no business impact stated without its simulation caveat; no invented percentages; every headline number traces to a run ID. (6) Single-metric victory laps — any claim of improvement must cite the three-axis report. (7) Leakage-tolerant evaluation — random splits on temporal behavior data are banned; leakage tests are mandatory. (8) Unnecessary complexity ("architecture astronautics") — no Kafka/K8s/microservices/vector DBs without a load-bearing, ADR-documented reason. (9) Fully autonomous adaptation — no decision path that bypasses constraints, override capability, or the 3WD gateway. (10) Surveillance-framed explanations — explanations referencing raw granular tracking violate the style guide.

## Technical debt policy
- source: QUALITY_BAR.md (§4)
- type: nfr
- content: Acceptable shortcuts, each logged in `DEBT.md` with a removal trigger — propensity-as-uplift approximation (until stretch uplift models); static 3WD thresholds (until dynamic thresholds); single-machine storage; hand-tuned MCDA weights (with sensitivity analysis); demo dashboard shortcuts. Unacceptable shortcuts — skipping calibration; skipping leakage tests; unseeded randomness; contract-breaking API changes without version bump; simulator assumptions leaking into models; silent constraint bypasses. Documentation requirement — every accepted debt item records what, why, blast radius, removal trigger. Refactoring triggers — a registry interface violated twice ⇒ redesign interface; a config schema changed incompatibly ⇒ migration note plus version; any anti-pattern found in review ⇒ fix before merge, no exceptions for the decision path.

## Documentation standards
- source: QUALITY_BAR.md (§5)
- type: nfr
- content: Required artifacts — `README.md` (pitch, diagram, quickstart, results); `docs/` (the foundation docs plus DECISION_ENGINE_DESIGN); architecture diagram (C4-ish, one page); ADRs (`docs/adr/NNN-*.md`) for every resolved open decision and every debt exception; experiment logs (MLflow plus a human-readable `EXPERIMENTS.md` index); OpenAPI reference; model cards per model (data, features, metrics, calibration, limitations, intended use); `SIMULATOR_ASSUMPTIONS.md`; explanation style guide; `DEBT.md`.

## Human evaluation rubric for explanations
- source: QUALITY_BAR.md (§6)
- type: nfr
- content: Sampled decisions scored 1–5 on faithfulness (matches the trace), completeness (mentions the decisive constraint), readability (manager-ready), framing (relevance not surveillance), and honesty (uncertainty stated). Release requires median >= 4 with no faithfulness score < 3.
