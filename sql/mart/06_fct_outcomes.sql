-- fct_outcomes: the simulated outcome of each decision (grain: one row per fct_decisions row).
-- Ground-truth columns (true_uplift, would_buy_anyway) exist only because this is simulation.
CREATE TABLE fct_outcomes AS
SELECT
    f.decision_key,
    r.converted,
    r.would_buy_anyway,
    r.converted AND r.would_buy_anyway AND r.discount_bps > 0 AS is_wasted_discount,
    ROUND(CASE WHEN r.converted THEN r.order_value_cents ELSE 0 END / 100.0, 6) AS revenue_eur,
    ROUND(
        CASE WHEN r.converted THEN r.order_value_cents * r.discount_bps / 10000.0 ELSE 0 END
        / 100.0,
        6
    ) AS discount_cost_eur,
    ROUND(r.profit_cents / 100.0, 6) AS profit_eur,
    ROUND(r.profit_none_cents / 100.0, 6) AS profit_if_nothing_eur,
    ROUND(r.expected_profit_cents / 100.0, 6) AS expected_profit_eur,
    ROUND(r.expected_profit_none_cents / 100.0, 6) AS expected_profit_if_nothing_eur,
    ROUND(r.regret_cents / 100.0, 6) AS regret_eur,
    r.p_action - r.p_none AS true_uplift,
    r.p_action AS true_purchase_probability
FROM src_replay_decisions AS r
INNER JOIN dim_policy AS dp ON dp.policy = r.policy
INNER JOIN dim_customer AS dc ON dc.customer_id = r.customer_id
INNER JOIN dim_date AS dd ON dd.day_index = r.day
INNER JOIN fct_decisions AS f
    ON f.policy_key = dp.policy_key
    AND f.customer_key = dc.customer_key
    AND f.date_key = dd.date_key
ORDER BY f.decision_key;
