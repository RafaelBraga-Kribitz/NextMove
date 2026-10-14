-- Row counts reconcile with the pipeline outputs: nothing dropped or duplicated by the joins.
SELECT 'fct_decisions vs source' AS check_name,
       (SELECT COUNT(*) FROM fct_decisions) AS mart_rows,
       (SELECT COUNT(*) FROM src_replay_decisions) AS source_rows
WHERE (SELECT COUNT(*) FROM fct_decisions) <> (SELECT COUNT(*) FROM src_replay_decisions)
UNION ALL
SELECT 'fct_outcomes vs fct_decisions',
       (SELECT COUNT(*) FROM fct_outcomes), (SELECT COUNT(*) FROM fct_decisions)
WHERE (SELECT COUNT(*) FROM fct_outcomes) <> (SELECT COUNT(*) FROM fct_decisions)
UNION ALL
SELECT 'dim_date vs horizon', (SELECT COUNT(*) FROM dim_date), (SELECT horizon_days FROM src_params)
WHERE (SELECT COUNT(*) FROM dim_date) <> (SELECT horizon_days FROM src_params)
UNION ALL
SELECT 'dim_policy vs summary', (SELECT COUNT(*) FROM dim_policy), (SELECT COUNT(*) FROM src_policy_summary)
WHERE (SELECT COUNT(*) FROM dim_policy) <> (SELECT COUNT(*) FROM src_policy_summary)
UNION ALL
SELECT 'fct_decisions empty', 0, 1 WHERE (SELECT COUNT(*) FROM fct_decisions) = 0;
