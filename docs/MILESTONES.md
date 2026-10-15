# Milestones

Delivery plan for the first finished release, scoped by
[ADR-011](adr/011-portfolio-scope-for-hiring-market.md). Progress is tracked item by item in
[`STATUS_LOG.md`](STATUS_LOG.md); every item ends with `just ci` green.

## M-A — Contracts and baselines

- **A1** ADR-011, `STATUS_LOG.md`, `DEBT.md`, this file.
- **A2** Typed `Decision` pydantic contract per `DECISION_ENGINE_DESIGN.md` §3, JSON-schema
  export, contract tests (AC-1, AC-4).
- **A3** Config-driven action catalog (ADR-010, eight archetypes incl. `none` and `wait`) and the
  `ActionProvider` registry.
- **A4** `rules/`: hard/soft `Constraint` registry (inventory scarcity, discount cap,
  frequency/fatigue cap, margin floor); property test over ≥10,000 randomized contexts with zero
  hard-constraint violations (AC-2); example plugin (AC-13).
- **A5** `policies/` baselines: do-nothing, always-discount, top-seller, rules-only.

## M-B — Models and segmentation

- **B1** `segmentation/`: candidate clusterings, viability constraints, MCDA scorecard (AC-7).
- **B2** `models/`: per-action response models (logistic baseline + gradient boosting), temporal
  split, calibration gate (AC-5), attributions, model cards, MLflow logging, DVC stage.
- **B3** Uplift as response-model delta (ADR-006) and its approximation error against simulator
  ground truth.

## M-C — Decision engine and explanation

- **C1** `decisions/`: constrained expected-value argmax with intervals, calibrated confidence,
  reasoning trace; golden-file determinism (AC-3).
- **C2** `explain/`: templated explanations, style guide, surveillance-phrasing scan.

## M-D — Evaluation

- **D1** `evaluate/`: three-axis report, replay profit with CIs (AC-6), failure analysis.
- **D2** Static 3WD gateway (ADR-008) with fixture suite (AC-8) and Delay escalation (AC-9).
- **D3** Policy comparison with intervals, one command (AC-10), incl. the wasted-discount share.
- **D4** Override loop: logged overrides visible in evaluation (UC1).

## M-E — API, mart and reporting

- **E1** `api/`: `POST /v1/decisions`, `GET /v1/customers/{id}`, `POST /v1/overrides`, OpenAPI.
- **E2** DuckDB SQL mart, SQL tests, data-quality report.
- **E3** Power BI build kit under `reporting/powerbi/`.
- **E4** Manager-facing demo surface completing UC1 without code edits (AC-14), screenshots.

## M-F — Engineering and docs

- **F1** `just reproduce` reproduces published tables from a clean clone (AC-11).
- **F2** Coverage gates (AC-12).
- **F3** Runbook, model cards, OpenAPI export, assumption log.
- **F4** README rewrite, docs index, ADR table.

## Later (explicitly out of scope for this release, per ADR-011)

- Dynamic, traffic/seasonality-aware 3WD thresholds (first post-MVP experiment per ADR-008).
- Dedicated uplift learners (T-/X-learner) replacing the propensity-delta approximation.
- Public-dataset validation of the data-engineering layer (OD-4 v2 track).
- Neural networks / two-tower models, even as comparison challengers.
- Contextual bandits beyond one simple epsilon-greedy comparator; the reward-hacking probe
  against the D-04 fatigue loophole.
- Timing and channel as optimized decision dimensions (POL-02).
- UC2-UC4 depth beyond what UC1 and the policy comparison need.
