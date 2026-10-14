-- dim_action: one row per concrete candidate in the action catalog (grain: candidate).
CREATE TABLE dim_action AS
SELECT
    CAST(row_number() OVER (ORDER BY a.catalog_order) AS INTEGER) AS action_key,
    a.candidate_id,
    a.archetype,
    a.description,
    a.is_contact,
    a.cost_cents,
    a.discount_bps,
    a.archetype IN ('none', 'wait') AS is_restraint,
    a.discount_bps > 0 AS is_discount
FROM src_actions AS a
ORDER BY action_key;
