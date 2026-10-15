-- rpt_policy_kpis: the KPI (Kennzahlen) table behind the Power BI page (grain: policy).
CREATE TABLE rpt_policy_kpis AS
WITH joined AS (
    SELECT
        dp.policy,
        dp.policy_label,
        dp.is_ml_policy,
        da.is_contact,
        da.is_discount,
        da.is_restraint,
        o.converted,
        o.would_buy_anyway,
        o.is_wasted_discount,
        o.discount_cost_eur,
        o.profit_eur,
        o.expected_profit_eur,
        o.expected_profit_if_nothing_eur,
        o.regret_eur,
        f.is_overridden
    FROM fct_decisions AS f
    INNER JOIN fct_outcomes AS o ON o.decision_key = f.decision_key
    INNER JOIN dim_policy AS dp ON dp.policy_key = f.policy_key
    INNER JOIN dim_action AS da ON da.action_key = f.action_key
)
SELECT
    policy,
    policy_label,
    is_ml_policy,
    COUNT(*) AS decisions,
    ROUND(AVG(CASE WHEN is_contact THEN 1 ELSE 0 END), 6) AS contact_rate,
    ROUND(AVG(CASE WHEN is_restraint THEN 1 ELSE 0 END), 6) AS restraint_rate,
    ROUND(AVG(CASE WHEN is_discount THEN 1 ELSE 0 END), 6) AS discount_rate,
    SUM(CASE WHEN converted THEN 1 ELSE 0 END) AS conversions,
    ROUND(AVG(CASE WHEN converted THEN 1 ELSE 0 END), 6) AS conversion_rate,
    ROUND(SUM(profit_eur), 2) AS profit_eur,
    ROUND(SUM(expected_profit_eur - expected_profit_if_nothing_eur), 2)
        AS expected_profit_vs_nothing_eur,
    ROUND(SUM(discount_cost_eur), 2) AS discount_cost_eur,
    ROUND(
        SUM(CASE WHEN is_wasted_discount THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN is_discount AND converted THEN 1 ELSE 0 END), 0),
        6
    ) AS wasted_discount_share,
    ROUND(
        AVG(CASE WHEN would_buy_anyway THEN CASE WHEN is_discount THEN 0 ELSE 1 END END), 6
    ) AS no_incentive_rate_would_buy_anyway,
    ROUND(AVG(regret_eur) * 100, 6) AS mean_regret_cents,
    SUM(CASE WHEN is_overridden THEN 1 ELSE 0 END) AS overrides
FROM joined
GROUP BY policy, policy_label, is_ml_policy
ORDER BY policy;
