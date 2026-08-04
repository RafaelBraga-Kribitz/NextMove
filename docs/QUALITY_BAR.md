# QUALITY_BAR.md

---

## 1. Acceptance Criteria (testable · observable · specific)

**Decision engine**
- AC-1: For any valid context, `POST /v1/decisions` returns a schema-valid Decision including `none`/`wait` in `candidates_considered`; verified by contract tests.
- AC-2: No decision ever contains an action excluded by a hard constraint (property-based test over randomized contexts, ≥10k cases, zero violations).
- AC-3: Given fixed (context, config hash, model versions, seed), the decision is byte-identical across runs (golden-file test).
- AC-4: 100% of decisions include non-empty `reasoning` and structured `reasoning_trace` with fired rules and runner-up.

**Models & segmentation**
- AC-5: Calibration report (reliability curve + Brier) exists for every decision-path model; miscalibration beyond a configured bound fails the pipeline gate.
- AC-6: GBM models beat the rule baseline on decision-level replay profit with reported confidence intervals — or the report explicitly states they don't and the baseline ships.
- AC-7: Every produced segmentation satisfies configured viability constraints (min size, max clusters); the MCDA scorecard (criteria matrix, weights, ranking) is emitted per run.

**Experimentation**
- AC-8: The 3WD gateway reproduces correct Accept/Reject/Delay verdicts on a fixture suite covering clear-win, clear-loss, in-margin, and conflicting-metric cases.
- AC-9: A Delay verdict past its configured budget escalates to `needs_human_review` (integration test).

**Policy evaluation**
- AC-10: The policy comparison report shows cumulative constrained profit for {do-nothing, always-discount, top-seller, rules-only, ML policy} over the same simulated horizon with intervals; regenerable by one command.

**Engineering**
- AC-11: `make reproduce` on a clean clone completes end-to-end and reproduces the published metrics tables exactly (seeded); CI runs the miniature version green.
- AC-12: Test coverage of `rules/`, `decisions/`, `evaluate/` ≥ 85% lines; overall ≥ 75%.
- AC-13: Adding a new Constraint and a new ActionProvider via the registries requires zero core-module edits (demonstrated by an example plugin in-repo).

**Product/demo**
- AC-14: The UC1 walkthrough (inspect → decision → explanation → override → override visible in evaluation) completes via the demo surface without touching code.

## 2. Definition of Done

**Product:** UC1–UC4 implemented and demoable; override loop closed; constraint config documented for the manager persona.
**Engineering:** all ACs green in CI; API OpenAPI-documented; runbook for the pipeline; no unreviewed TODOs in decision-path code.
**Data science:** three-axis evaluation report (prediction / decision / system) published; baseline comparison honest; simulator assumption log complete; failure-analysis section written; model cards for all trained models.
**Portfolio:** README with 90-second pitch, architecture diagram, quickstart, and results table; ADR log covering every resolved open decision; demo script or recording; explanation style guide.

## 3. Anti-Patterns (explicitly prohibited)

1. **Notebook-only implementation.** Notebooks allowed for exploration under `notebooks/`, never as pipeline.
2. **Magic AI components.** No component whose behavior cannot be explained by its inputs, config, and versioned artifacts; no LLM in the decision or explanation path.
3. **Unexplained models.** A model without attributions and a model card cannot enter the decision path.
4. **Hardcoded business rules.** Business numbers in code = rejected change; all thresholds/weights in schema-validated config.
5. **Fake metrics.** No business impact stated without its simulation caveat; no invented percentages; every headline number traces to a run ID.
6. **Single-metric victory laps.** Any claim of improvement must cite the three-axis report; "AUC went up" is not a result.
7. **Leakage-tolerant evaluation.** Random splits on temporal behavior data are banned; leakage tests are mandatory.
8. **Unnecessary complexity ("architecture astronautics").** No Kafka/K8s/microservices/vector DBs without a load-bearing, ADR-documented reason.
9. **Fully autonomous adaptation.** No decision path that bypasses constraints, override capability, or the 3WD gateway.
10. **Surveillance-framed explanations.** Explanations referencing raw granular tracking ("you viewed X at 02:13") violate the style guide.

## 4. Technical Debt Policy

- **Acceptable shortcuts (must be logged in `DEBT.md` with removal trigger):** propensity-as-uplift approximation (until stretch uplift models); static 3WD thresholds (until dynamic thresholds); single-machine storage; hand-tuned MCDA weights (with sensitivity analysis); demo dashboard shortcuts.
- **Unacceptable shortcuts:** skipping calibration; skipping leakage tests; unseeded randomness; contract-breaking API changes without version bump; simulator assumptions leaking into models; silent constraint bypasses.
- **Documentation requirement:** every accepted debt item records: what, why, blast radius, removal trigger.
- **Refactoring triggers:** a registry interface violated twice → redesign interface; a config schema changed incompatibly → migration note + version; any anti-pattern found in review → fix before merge, no exceptions for the decision path.

## 5. Documentation Standards

Required artifacts: `README.md` (pitch, diagram, quickstart, results); `docs/` (these nine + DECISION_ENGINE_DESIGN); architecture diagram (C4-ish, one page); **ADRs** (`docs/adr/NNN-*.md`) for every resolved open decision and every debt exception; experiment logs (MLflow + a human-readable `EXPERIMENTS.md` index); OpenAPI reference; **model cards** per model (data, features, metrics, calibration, limitations, intended use); `SIMULATOR_ASSUMPTIONS.md`; explanation style guide; `DEBT.md`.

## 6. Human Evaluation Rubric (explanations)

Sampled decisions scored 1–5 on: faithfulness (matches the trace), completeness (mentions the decisive constraint), readability (manager-ready), framing (relevance not surveillance), and honesty (uncertainty stated). Release requires median ≥4 with no faithfulness score <3.
