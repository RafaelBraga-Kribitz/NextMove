-- Primary keys are unique (every row returned is a violation).
SELECT 'dim_date' AS table_name, CAST(date_key AS VARCHAR) AS key FROM dim_date GROUP BY date_key HAVING COUNT(*) > 1
UNION ALL
SELECT 'dim_customer', customer_id FROM dim_customer GROUP BY customer_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'dim_action', candidate_id FROM dim_action GROUP BY candidate_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'dim_policy', policy FROM dim_policy GROUP BY policy HAVING COUNT(*) > 1
UNION ALL
SELECT 'fct_decisions', CAST(decision_key AS VARCHAR) FROM fct_decisions GROUP BY decision_key HAVING COUNT(*) > 1
UNION ALL
SELECT 'fct_decisions_grain', CAST(policy_key AS VARCHAR) || '|' || CAST(customer_key AS VARCHAR) || '|' || CAST(date_key AS VARCHAR)
FROM fct_decisions GROUP BY policy_key, customer_key, date_key HAVING COUNT(*) > 1
UNION ALL
SELECT 'fct_outcomes', CAST(decision_key AS VARCHAR) FROM fct_outcomes GROUP BY decision_key HAVING COUNT(*) > 1;
