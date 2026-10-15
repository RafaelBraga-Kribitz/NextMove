-- Staging: typed, flattened views over the raw pipeline tables the builder binds
-- (raw_events = canonical events, raw_catalog = product catalog).
CREATE VIEW src_events AS
SELECT
    e.customer_id,
    e.type AS event_type,
    CAST(date_diff('day', p.start_date, CAST(e.ts AS DATE)) AS INTEGER) AS day_index,
    CAST(json_extract_string(e.payload, '$.order_total_cents') AS BIGINT) AS order_total_cents,
    c.category
FROM raw_events AS e
CROSS JOIN src_params AS p
LEFT JOIN raw_catalog AS c ON c.sku = json_extract_string(e.payload, '$.line_items[0].sku');

CREATE VIEW src_category AS
SELECT
    c.category,
    AVG(c.margin_rate) AS margin_rate,
    COUNT(*) AS sku_count
FROM raw_catalog AS c
GROUP BY c.category;
