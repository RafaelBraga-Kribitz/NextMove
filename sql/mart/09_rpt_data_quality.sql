-- rpt_data_quality: the ingest data-quality gates as a table (grain: gate or check).
CREATE TABLE rpt_data_quality AS
WITH rejects AS (
    SELECT
        r.stage,
        CASE
            WHEN r.reason LIKE 'semantic gate %' THEN regexp_extract(r.reason, '''([a-z_]+)''', 1)
            ELSE 'contract'
        END AS gate,
        COUNT(*) AS rejected_rows
    FROM src_rejects AS r
    GROUP BY r.stage, gate
),
totals AS (
    SELECT
        (SELECT COUNT(*) FROM src_events) AS landed_rows,
        (SELECT COUNT(*) FROM src_rejects) AS rejected_rows
)
SELECT
    'reject_rate' AS check_name,
    'all' AS stage,
    t.rejected_rows AS failing_rows,
    t.landed_rows + t.rejected_rows AS checked_rows,
    ROUND(t.rejected_rows / (t.landed_rows + t.rejected_rows), 6) AS failing_share,
    (SELECT max_reject_rate FROM src_params) AS threshold,
    t.rejected_rows / (t.landed_rows + t.rejected_rows) <= (SELECT max_reject_rate FROM src_params)
        AS passed
FROM totals AS t
UNION ALL
SELECT
    'gate:' || r.gate AS check_name,
    r.stage,
    r.rejected_rows AS failing_rows,
    t.landed_rows + t.rejected_rows AS checked_rows,
    ROUND(r.rejected_rows / (t.landed_rows + t.rejected_rows), 6) AS failing_share,
    NULL AS threshold,
    NULL AS passed
FROM rejects AS r
CROSS JOIN totals AS t
ORDER BY check_name;
