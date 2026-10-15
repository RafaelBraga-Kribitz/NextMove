# Data-quality report

> **Simulated data only.** Built from the ingest gates and the mart's SQL tests (ADR-004).

## Ingest gates (contract validation, semantic gates, reject-rate threshold)

| Check | Stage | Failing rows | Checked rows | Failing share | Threshold | Passed |
|---|---|---:|---:|---:|---:|---|
| gate:monotonic_session_timestamps | semantic | 170 | 986,723 | 0.0172% |  |  |
| reject_rate | all | 170 | 986,723 | 0.0172% | 0.1000% | yes |

Rejected rows are quarantined with their reason (`data/canonical/rejects.parquet`), never silently dropped.

## Mart SQL tests (`sql/tests/`)

| Test | Violating rows |
|---|---:|
| test_business_rules | 0 |
| test_not_null_keys | 0 |
| test_referential_integrity | 0 |
| test_row_counts | 0 |
| test_unique_keys | 0 |

## Mart row counts

| Table | Rows |
|---|---:|
| dim_date | 548 |
| dim_action | 11 |
| dim_policy | 7 |
| dim_customer | 1,993 |
| fct_decisions | 240,961 |
| fct_outcomes | 240,961 |
| rpt_policy_kpis | 7 |
| rpt_retention_cohorts | 150 |
| rpt_data_quality | 2 |
