# Status Log

Working log for the finish-and-polish loop (scope: [ADR-011](adr/011-portfolio-scope-for-hiring-market.md),
plan: [MILESTONES.md](MILESTONES.md)). An item is ticked only when `just ci` is green on the
commit that completes it.

## Checklist

### M-A — Contracts and baselines
- [x] A1 ADR-011, STATUS_LOG, DEBT, MILESTONES
- [x] A2 Decision contract + JSON schema + contract tests (AC-1, AC-4)
- [x] A3 Action catalog + ActionProvider registry
- [x] A4 Constraint registry + 10k property test (AC-2) + example plugin (AC-13)
- [x] A5 Baseline policies

### M-B — Models and segmentation
- [x] B1 Segmentation + viability + MCDA scorecard (AC-7)
- [x] B2 Response models, calibration gate (AC-5), attributions, model cards, MLflow, DVC stage
- [x] B3 Uplift delta + approximation-error analysis

### M-C — Decision engine and explanation
- [x] C1 Decision engine + golden determinism (AC-3)
- [x] C2 Templated explanations + style guide + phrasing scan

### M-D — Evaluation
- [x] D1 Three-axis report, replay profit CIs (AC-6), failure analysis
- [x] D2 3WD gateway fixtures (AC-8) + Delay escalation (AC-9)
- [x] D3 Policy comparison, one command (AC-10), wasted-discount share
- [x] D4 Override loop into evaluation (UC1)

### M-E — API, mart and reporting
- [x] E1 API + OpenAPI
- [x] E2 SQL mart + SQL tests + data-quality report
- [x] E3 Power BI build kit
- [x] E4 Demo surface + screenshots (AC-14)

### M-F — Engineering and docs
- [ ] F1 Clean-clone reproduce (AC-11)
- [ ] F2 Coverage gates (AC-12)
- [x] F3 Runbook, model cards, OpenAPI export, assumption log
- [x] F4 README rewrite, docs index, ADR table

## Log

- **2026-10-14** — Re-verified state locally: Phase 1 packages present, eight stub packages,
  `just` installed into the environment (not previously on PATH). A1: wrote ADR-011,
  `docs/MILESTONES.md`, `DEBT.md`, this log; `tests/unit/test_adr_structure.py` now derives the
  ADR count from disk (≥11) instead of hard-coding ten.
- **2026-10-14** — A2–A5 committed and pushed; draft PR #4 opened so GitHub CI runs the full
  suite (the local full suite exceeds 30 min on this container because the integration tests
  re-run the `demo` simulation; fast subsets plus lint run locally on every item).
- **2026-10-14** — Evaluation design recorded as ADR-012: randomized A/B/n experiment for
  training data, an outcome oracle on the simulator's documented response function, common
  random numbers, train/validation/test windows, `demo` as the published profile.
- **2026-10-14** — B1/B2/C1/C2: segmentation with TOPSIS scorecard (k-means k=3 wins on
  `demo`), logistic and LightGBM bootstrap ensembles with Platt calibration and the AC-5 gate
  (both pass on `demo` and `ci`), the decision engine with expected-value policy, templated
  explanations, explanation style guide, AC-2 through the full engine (10k cases), AC-3 golden
  file. Early finding (simulation only): the oracle-optimal policy chooses `none` for ~98% of
  test-window customer-weeks because the existing campaign calendar already fatigues
  customers; observable features carry weak signal (test AUC ≈ 0.51–0.53). Reported as is.
- **2026-10-14** — B3/D1–D4: evaluate stage (validation-window model selection, test-window
  replay of seven policies incl. a hindsight oracle, bootstrap CIs, uplift error, 3WD verdicts,
  overrides, report + model cards). Result on `demo` (run `demo-f8fb25c032`, simulation only):
  engine ≈ do-nothing, beats rules-only by €2,909 [€2,785, €3,042]; gateway Accept vs
  rules-only (needs sign-off), Reject (in-margin) vs do-nothing; oracle ceiling +€44.
- **2026-10-14** — E1/E2/E3: FastAPI app + OpenAPI export, demo pages, DuckDB star-schema mart
  with 5 SQL test files, data-quality report, Power BI kit with a column-reference test.
- **2026-10-14** — CI on 4b65de6 failed one golden storage test (`test_staging_part_files_
  roundtrip_and_isolation`: it iterates every `Zone`, and new zones were not seeded). Fixed by
  seeding every non-lineage zone; reproduced locally before and after.
- **2026-10-14** — F2: AC-12 gate (`just coverage`, `scripts/coverage_gate.py`) added to CI;
  decision-layer coverage 85% overall, rules/decisions/evaluate ≥ 92%.
- **2026-10-14** — Published run: `just reproduce` (demo, 30 min) produced run
  `demo-f8fb25c032`; re-running evaluate + mart reproduced the same run id and tables. The
  scratch run's id differed only because its feature grid carried an older config-hash stamp.
  Local full suite (`-m "not peak_rss"`) green. E4: demo screenshots captured with Playwright;
  F3: runbook, demo script, acceptance matrix, model cards, OpenAPI export, assumption log;
  F4: README rewritten decision-first. The README contract check still fails on the registry
  status (`braga-portfolio-docs/manifest/portfolio.yaml` says Foundation) — human item.
