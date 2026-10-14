# Power BI build kit

Everything needed to build the one-page NextMove report in Power BI Desktop. **The `.pbix`
file itself is not in this repository: it is built by hand from this kit** (a `.pbix` cannot
be generated reproducibly from code). Every number the report shows comes from the seeded
simulation (ADR-004) — keep the "Simulated data" subtitle on the page.

| File | What it is |
|---|---|
| [`model.md`](model.md) | Star-schema data model: tables, keys, relationships, cardinality |
| [`measures.dax`](measures.dax) | All DAX measures, with display folders and formats |
| [`theme.json`](theme.json) | Report theme (colors, fonts) — *View → Themes → Browse for themes* |
| [`layout.md`](layout.md) | The one-page layout: every visual, its fields, title and position |

## Data

The mart is produced by the pipeline (`just reproduce`, stage `mart`) and exported to
[`../../reports/demo/mart/`](../../reports/demo/mart/):

| Table | Grain | Format |
|---|---|---|
| `fct_decisions` | one replayed decision (policy × customer × decision day) | Parquet |
| `fct_outcomes` | the simulated outcome of each decision | Parquet |
| `dim_customer` | customer, as of the test-window start (segment, lifecycle, fatigue risk, CLV estimate) | Parquet, CSV |
| `dim_action` | action catalog candidate | Parquet, CSV |
| `dim_policy` | evaluated policy | Parquet, CSV |
| `dim_date` | simulated calendar day | Parquet, CSV |
| `rpt_policy_kpis` | KPI table per policy (cross-check for the measures) | Parquet, CSV |
| `rpt_retention_cohorts` | cohort month × months since first seen | Parquet, CSV |
| `rpt_data_quality` | ingest gates | Parquet, CSV |

Model-quality numbers (Brier, ECE) come from
[`../../reports/demo/evaluation/model_metrics.csv`](../../reports/demo/evaluation/model_metrics.csv).

## Build steps (about 30 minutes)

1. Run `just reproduce` (or use the committed exports) so `reports/demo/mart/` is current.
2. Power BI Desktop → *Get data → Parquet* for the four `dim_*` and two `fct_*` files; *Text/CSV*
   for `rpt_retention_cohorts.csv`, `rpt_data_quality.csv` and
   `../../reports/demo/evaluation/model_metrics.csv`.
3. In Power Query, confirm the data types listed in [`model.md`](model.md) (keys as whole
   numbers, `calendar_date` as date, flags as true/false).
4. *Model view*: create the relationships in [`model.md`](model.md); mark `dim_date` as the
   date table on `calendar_date`.
5. Create a measures table named `_Measures` and paste every measure from
   [`measures.dax`](measures.dax).
6. Apply [`theme.json`](theme.json).
7. Build the page following [`layout.md`](layout.md).
8. Check: the *Profit vs. doing nothing* card for the ML policy must match
   `rpt_policy_kpis.csv` (`expected_profit_vs_nothing_eur`) to the cent; then save as
   `NextMove.pbix` (keep it out of git; publish screenshots instead).
