# Status Log

Working log for the finish-and-polish loop (scope: [ADR-011](adr/011-portfolio-scope-for-hiring-market.md),
plan: [MILESTONES.md](MILESTONES.md)). An item is ticked only when `just ci` is green on the
commit that completes it.

## Checklist

### M-A — Contracts and baselines
- [x] A1 ADR-011, STATUS_LOG, DEBT, MILESTONES
- [ ] A2 Decision contract + JSON schema + contract tests (AC-1, AC-4)
- [ ] A3 Action catalog + ActionProvider registry
- [ ] A4 Constraint registry + 10k property test (AC-2) + example plugin (AC-13)
- [ ] A5 Baseline policies

### M-B — Models and segmentation
- [ ] B1 Segmentation + viability + MCDA scorecard (AC-7)
- [ ] B2 Response models, calibration gate (AC-5), attributions, model cards, MLflow, DVC stage
- [ ] B3 Uplift delta + approximation-error analysis

### M-C — Decision engine and explanation
- [ ] C1 Decision engine + golden determinism (AC-3)
- [ ] C2 Templated explanations + style guide + phrasing scan

### M-D — Evaluation
- [ ] D1 Three-axis report, replay profit CIs (AC-6), failure analysis
- [ ] D2 3WD gateway fixtures (AC-8) + Delay escalation (AC-9)
- [ ] D3 Policy comparison, one command (AC-10), wasted-discount share
- [ ] D4 Override loop into evaluation (UC1)

### M-E — API, mart and reporting
- [ ] E1 API + OpenAPI
- [ ] E2 SQL mart + SQL tests + data-quality report
- [ ] E3 Power BI build kit
- [ ] E4 Demo surface + screenshots (AC-14)

### M-F — Engineering and docs
- [ ] F1 Clean-clone reproduce (AC-11)
- [ ] F2 Coverage gates (AC-12)
- [ ] F3 Runbook, model cards, OpenAPI export, assumption log
- [ ] F4 README rewrite, docs index, ADR table

## Log

- **2026-10-14** — Re-verified state locally: Phase 1 packages present, eight stub packages,
  `just` installed into the environment (not previously on PATH). A1: wrote ADR-011,
  `docs/MILESTONES.md`, `DEBT.md`, this log; `tests/unit/test_adr_structure.py` now derives the
  ADR count from disk (≥11) instead of hard-coding ten.
