-- dim_date: one row per simulated calendar day (grain: day).
CREATE TABLE dim_date AS
WITH days AS (
    SELECT
        CAST(d.day_index AS INTEGER) AS day_index,
        CAST(p.start_date + d.day_index * INTERVAL 1 DAY AS DATE) AS calendar_date
    FROM src_params AS p
    CROSS JOIN range(0, (SELECT horizon_days FROM src_params)) AS d(day_index)
)
SELECT
    CAST(strftime(days.calendar_date, '%Y%m%d') AS INTEGER) AS date_key,
    days.calendar_date,
    days.day_index,
    CAST(year(days.calendar_date) AS INTEGER) AS year,
    CAST(month(days.calendar_date) AS INTEGER) AS month,
    strftime(days.calendar_date, '%Y-%m') AS year_month,
    CAST(weekofyear(days.calendar_date) AS INTEGER) AS iso_week,
    strftime(days.calendar_date, '%A') AS weekday_name,
    month(days.calendar_date) = 12 AS is_peak_month,
    CASE
        WHEN days.day_index < p.train_end_day THEN 'train'
        WHEN days.day_index < p.validation_end_day THEN 'validation'
        ELSE 'test'
    END AS evaluation_window
FROM days
CROSS JOIN src_params AS p
ORDER BY days.day_index;
