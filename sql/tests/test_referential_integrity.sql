-- Every foreign key resolves to its dimension.
SELECT 'fct_decisions.customer_key' AS relation, CAST(f.decision_key AS VARCHAR) AS key
FROM fct_decisions AS f LEFT JOIN dim_customer AS d ON d.customer_key = f.customer_key
WHERE d.customer_key IS NULL
UNION ALL
SELECT 'fct_decisions.action_key', CAST(f.decision_key AS VARCHAR)
FROM fct_decisions AS f LEFT JOIN dim_action AS d ON d.action_key = f.action_key
WHERE d.action_key IS NULL
UNION ALL
SELECT 'fct_decisions.date_key', CAST(f.decision_key AS VARCHAR)
FROM fct_decisions AS f LEFT JOIN dim_date AS d ON d.date_key = f.date_key
WHERE d.date_key IS NULL
UNION ALL
SELECT 'fct_decisions.policy_key', CAST(f.decision_key AS VARCHAR)
FROM fct_decisions AS f LEFT JOIN dim_policy AS d ON d.policy_key = f.policy_key
WHERE d.policy_key IS NULL
UNION ALL
SELECT 'fct_outcomes.decision_key', CAST(o.decision_key AS VARCHAR)
FROM fct_outcomes AS o LEFT JOIN fct_decisions AS f ON f.decision_key = o.decision_key
WHERE f.decision_key IS NULL;
