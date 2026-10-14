-- dim_customer: one row per simulated customer, described as of the test-window start
-- (grain: customer). CRM attributes are simple, documented
-- heuristics, not models:
--   lifecycle_stage  joined_during_test | never_bought | active (last order <= 60 days) | lapsing (61-120) | churned
--   fatigue_risk     high (>= 4 messages in the last 14 days) | medium (2-3) | low
--   clv_12m_estimate_eur  margin earned so far, per active month, times 12 (heuristic)
CREATE TABLE dim_customer AS
WITH params AS (
    SELECT test_start_day FROM src_params
),
events AS (
    SELECT
        e.customer_id,
        e.event_type,
        e.day_index,
        e.order_total_cents,
        e.category
    FROM src_events AS e
),
first_seen AS (
    SELECT customer_id, MIN(day_index) AS first_day
    FROM events
    GROUP BY customer_id
),
orders AS (
    SELECT
        ev.customer_id,
        COUNT(*) AS orders_before_test,
        SUM(ev.order_total_cents) AS revenue_before_test_cents,
        SUM(ev.order_total_cents * c.margin_rate) AS margin_before_test_cents,
        MAX(ev.day_index) AS last_order_day
    FROM events AS ev
    INNER JOIN src_category AS c ON c.category = ev.category
    CROSS JOIN params AS p
    WHERE ev.event_type = 'order_placed' AND ev.day_index < p.test_start_day
    GROUP BY ev.customer_id
),
recent_contacts AS (
    SELECT ev.customer_id, COUNT(*) AS messages_last_14d
    FROM events AS ev
    CROSS JOIN params AS p
    WHERE ev.event_type = 'campaign_exposure'
      AND ev.day_index >= p.test_start_day - 14
      AND ev.day_index < p.test_start_day
    GROUP BY ev.customer_id
),
active AS (
    SELECT f.customer_id, f.first_day
    FROM first_seen AS f
)
SELECT
    CAST(row_number() OVER (ORDER BY length(a.customer_id), a.customer_id) AS INTEGER)
        AS customer_key,
    a.customer_id,
    CAST(sp.start_date + a.first_day * INTERVAL 1 DAY AS DATE) AS first_seen_date,
    strftime(CAST(sp.start_date + a.first_day * INTERVAL 1 DAY AS DATE), '%Y-%m') AS cohort_month,
    COALESCE(s.segment_name, 'unsegmented') AS segment_name,
    COALESCE(o.orders_before_test, 0) AS orders_before_test,
    ROUND(COALESCE(o.revenue_before_test_cents, 0) / 100.0, 2) AS revenue_before_test_eur,
    CASE
        WHEN a.first_day >= p.test_start_day THEN 'joined_during_test'
        WHEN o.last_order_day IS NULL THEN 'never_bought'
        WHEN p.test_start_day - o.last_order_day <= 60 THEN 'active'
        WHEN p.test_start_day - o.last_order_day <= 120 THEN 'lapsing'
        ELSE 'churned'
    END AS lifecycle_stage,
    COALESCE(r.messages_last_14d, 0) AS messages_last_14d,
    CASE
        WHEN COALESCE(r.messages_last_14d, 0) >= 4 THEN 'high'
        WHEN COALESCE(r.messages_last_14d, 0) >= 2 THEN 'medium'
        ELSE 'low'
    END AS fatigue_risk,
    ROUND(
        COALESCE(o.margin_before_test_cents, 0) / 100.0
        / GREATEST((p.test_start_day - a.first_day) / 30.0, 1.0) * 12,
        2
    ) AS clv_12m_estimate_eur
FROM active AS a
CROSS JOIN params AS p
CROSS JOIN src_params AS sp
LEFT JOIN orders AS o ON o.customer_id = a.customer_id
LEFT JOIN recent_contacts AS r ON r.customer_id = a.customer_id
LEFT JOIN src_segments AS s ON s.customer_id = a.customer_id
ORDER BY customer_key;
