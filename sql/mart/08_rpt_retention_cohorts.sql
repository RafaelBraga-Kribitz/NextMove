-- rpt_retention_cohorts: share of each first-seen cohort that ordered in each later month
-- (grain: cohort month x months since first seen). Built from the canonical event log.
CREATE TABLE rpt_retention_cohorts AS
WITH first_seen AS (
    SELECT customer_id, MIN(day_index) AS first_day
    FROM src_events
    GROUP BY customer_id
),
cohorts AS (
    SELECT
        f.customer_id,
        date_trunc('month', CAST(p.start_date + f.first_day * INTERVAL 1 DAY AS DATE))
            AS cohort_month
    FROM first_seen AS f
    CROSS JOIN src_params AS p
),
order_months AS (
    SELECT DISTINCT
        e.customer_id,
        date_trunc('month', CAST(p.start_date + e.day_index * INTERVAL 1 DAY AS DATE))
            AS order_month
    FROM src_events AS e
    CROSS JOIN src_params AS p
    WHERE e.event_type = 'order_placed'
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_customers
    FROM cohorts
    GROUP BY cohort_month
),
activity AS (
    SELECT
        c.cohort_month,
        CAST(date_diff('month', c.cohort_month, om.order_month) AS INTEGER)
            AS months_since_first_seen,
        COUNT(DISTINCT om.customer_id) AS ordering_customers
    FROM cohorts AS c
    INNER JOIN order_months AS om ON om.customer_id = c.customer_id
    WHERE om.order_month >= c.cohort_month
    GROUP BY c.cohort_month, months_since_first_seen
)
SELECT
    strftime(a.cohort_month, '%Y-%m') AS cohort_month,
    a.months_since_first_seen,
    s.cohort_customers,
    a.ordering_customers,
    ROUND(a.ordering_customers / s.cohort_customers, 6) AS retention_rate
FROM activity AS a
INNER JOIN cohort_sizes AS s ON s.cohort_month = a.cohort_month
ORDER BY cohort_month, months_since_first_seen;
