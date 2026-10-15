-- fct_decisions: one row per replayed decision (grain: policy x customer x decision day).
CREATE TABLE fct_decisions AS
WITH decisions AS (
    SELECT
        r.policy,
        r.customer_id,
        r.day AS day_index,
        r.candidate_id,
        r.decision_id,
        r.confidence,
        r.uplift_estimate,
        r.expected_profit_estimate_cents,
        r.n_survivors,
        r.n_filtered,
        r.fired_rules,
        r.needs_human_review,
        r.runner_up,
        r.recent_contacts_7d,
        r.reasoning
    FROM src_replay_decisions AS r
),
overrides AS (
    SELECT
        o.decision_id,
        o.override_candidate,
        o.reason AS override_reason,
        row_number() OVER (PARTITION BY o.decision_id ORDER BY o.created_at DESC) AS rn
    FROM src_overrides AS o
)
SELECT
    CAST(row_number() OVER (ORDER BY dp.policy_key, d.day_index, dc.customer_key) AS BIGINT)
        AS decision_key,
    dp.policy_key,
    dc.customer_key,
    dd.date_key,
    da.action_key,
    d.decision_id,
    d.confidence,
    d.uplift_estimate,
    ROUND(d.expected_profit_estimate_cents / 100.0, 6) AS expected_profit_estimate_eur,
    d.n_survivors,
    d.n_filtered,
    d.fired_rules,
    d.needs_human_review,
    d.runner_up,
    d.recent_contacts_7d,
    ov.override_candidate IS NOT NULL AS is_overridden,
    ov.override_candidate,
    ov.override_reason,
    d.reasoning
FROM decisions AS d
INNER JOIN dim_policy AS dp ON dp.policy = d.policy
INNER JOIN dim_customer AS dc ON dc.customer_id = d.customer_id
INNER JOIN dim_date AS dd ON dd.day_index = d.day_index
INNER JOIN dim_action AS da ON da.candidate_id = d.candidate_id
LEFT JOIN overrides AS ov ON ov.decision_id = d.decision_id AND d.decision_id <> '' AND ov.rn = 1
ORDER BY decision_key;
