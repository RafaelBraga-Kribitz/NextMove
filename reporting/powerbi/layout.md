# One-page layout: "Restraint pays — simulated next-best-action evaluation"

Canvas 1280 × 720 (16:9). Grid units below are in pixels from the top-left. Page subtitle,
always visible: **"Simulated data · run `<run_id>` · NextMove simulator (ADR-004)"** — take the
run id from `reports/demo/evaluation/summary.json`.

| # | Visual | Position (x, y, w, h) | Fields | Title (exact) |
|---|---|---|---|---|
| 1 | Text box | 16, 8, 900, 56 | — | **Restraint pays: what should we do for each customer this week?** + subtitle above |
| 2 | Slicer (dropdown) | 940, 16, 320, 48 | `dim_policy[policy_label]` (filter `is_reference_only = FALSE`) | Policy |
| 3 | Card | 16, 76, 300, 110 | `[Profit vs Doing Nothing]` | Profit vs. doing nothing (€) |
| 4 | Card | 332, 76, 300, 110 | `[Wasted Discount Share]` | Discounts given to would-buy-anyway customers |
| 5 | Card | 648, 76, 300, 110 | `[Restraint Rate]` | Customer-weeks with no contact |
| 6 | Card | 964, 76, 300, 110 | `[Brier Score (test)]` | Model calibration (Brier, test) |
| 7 | Clustered bar | 16, 200, 620, 300 | Axis `dim_policy[policy_label]`, value `[Profit vs Doing Nothing]`; highlight the ML policy with conditional formatting on `dim_policy[is_ml_policy]` | Expected profit vs. doing nothing, by policy (€) |
| 8 | Stacked column | 652, 200, 612, 300 | Axis `dim_date[year_month]`, legend `dim_action[archetype]`, value `[Decisions]`; page filter `dim_date[evaluation_window] = "test"` | What each policy did, by month |
| 9 | Matrix | 16, 514, 620, 190 | Rows `dim_customer[segment_name]`, columns `dim_customer[lifecycle_stage]`, value `[Profit vs Doing Nothing]` | Where restraint matters: segment × lifecycle (€) |
| 10 | Line chart | 652, 514, 300, 190 | Axis `rpt_retention_cohorts[months_since_first_seen]`, legend `rpt_retention_cohorts[cohort_month]` (top 6), value `retention_rate` | Retention by first-seen cohort |
| 11 | Table | 964, 514, 300, 190 | `dim_policy[policy_label]`, `[Override Rate]`, `[Avg Confidence]`, `[Mean Regret (cents)]` | Governance: overrides, confidence, regret |

Interaction notes: visual 2 filters every visual except 7 (edit interactions → none on 7), so
the bar chart always compares all policies. Tooltips on 7 add `[Contact Rate]`,
`[Conversion Rate]` and `[Discount Cost]`. Use the theme's first color for the ML policy and
`#9a9890` for baselines; never color by rank.

Accessibility: alt text on every visual (its title plus the main number); no information by
color alone (the ML policy is also labeled "(ML policy)" in `policy_label` tooltips).
