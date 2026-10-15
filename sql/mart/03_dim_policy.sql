-- dim_policy: one row per evaluated policy (grain: policy).
CREATE TABLE dim_policy AS
SELECT
    CAST(row_number() OVER (ORDER BY s.policy) AS INTEGER) AS policy_key,
    s.policy,
    s.label AS policy_label,
    s.is_ml_policy,
    s.policy = 'oracle_upper_bound' AS is_reference_only
FROM src_policy_summary AS s
ORDER BY policy_key;
