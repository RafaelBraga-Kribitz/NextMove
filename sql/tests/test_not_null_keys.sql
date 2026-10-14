-- Keys are never null.
SELECT 'fct_decisions' AS table_name, CAST(decision_key AS VARCHAR) AS key
FROM fct_decisions
WHERE decision_key IS NULL OR policy_key IS NULL OR customer_key IS NULL
   OR date_key IS NULL OR action_key IS NULL
UNION ALL
SELECT 'fct_outcomes', CAST(decision_key AS VARCHAR) FROM fct_outcomes WHERE decision_key IS NULL
UNION ALL
SELECT 'dim_customer', customer_id FROM dim_customer WHERE customer_key IS NULL OR customer_id IS NULL
UNION ALL
SELECT 'dim_date', CAST(day_index AS VARCHAR) FROM dim_date WHERE date_key IS NULL;
