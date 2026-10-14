# Technical Debt Register

Every accepted shortcut, per `docs/QUALITY_BAR.md` §4: what, why, blast radius, removal trigger.
Unacceptable shortcuts (skipping calibration or leakage tests, unseeded randomness, silent
constraint bypasses) are never logged here — they are not allowed at all.

| ID | What | Why | Blast radius | Removal trigger |
|----|------|-----|--------------|-----------------|
| DEBT-001 | Uplift approximated as `P(convert\|action) − P(convert\|none)` from response models (ADR-006) | Uplift learners are data-hungry and slow the MVP loop | Ranking can misattribute baseline heterogeneity as treatment effect; size measured in the uplift-approximation-error report | T-/X-learner track starts, or measured approximation error exceeds the bound in the report |
| DEBT-002 | Static 3WD thresholds (ADR-008) | Predictable and auditable; dynamic thresholds multiply validation surface | Low-traffic windows may Delay longer than needed | First post-MVP experiment: traffic-aware thresholds behind the existing interface |
| DEBT-003 | Single-machine storage (Parquet + DuckDB) | Local-first portfolio scope (ENG-08) | Default profile is bounded by laptop memory | A dataset that no longer fits the stated memory budget |
