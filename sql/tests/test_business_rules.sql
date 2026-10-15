-- Business invariants: no chosen action breaks the discount ceiling, KPIs reconcile with
-- the Python evaluation, and a wasted discount is always a redeemed discount.
SELECT 'discount above ceiling' AS check_name, CAST(f.decision_key AS VARCHAR) AS key
FROM fct_decisions AS f INNER JOIN dim_action AS a ON a.action_key = f.action_key
WHERE a.discount_bps > (SELECT max_discount_bps FROM src_params)
UNION ALL
SELECT 'kpi profit mismatch', k.policy
FROM rpt_policy_kpis AS k INNER JOIN src_policy_summary AS s ON s.policy = k.policy
WHERE abs(k.profit_eur - s.profit_eur) > 0.05
UNION ALL
SELECT 'wasted discount not redeemed', CAST(o.decision_key AS VARCHAR)
FROM fct_outcomes AS o WHERE o.is_wasted_discount AND NOT o.converted;
