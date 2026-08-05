"""Config-driven feature specs, the transform registry, and the feature-set version (D-19,
FEAT-01, ADR 002).

Every FEAT-01 family (RFM, session dynamics, category affinity, price-sensitivity proxy,
message-fatigue counters, cart state, abandonment history, micro-conversion aggregates) is one
registered `FeatureTransform`: a versioned SQL fragment plus the metadata (`output_column`,
`dtype`, `empty_default`) that makes a customer with zero qualifying events at an `as_of_ts`
carry a documented default rather than a missing row or a silently imputed value
(`DECISION_ENGINE_DESIGN`'s observation-stage requirement).

**Executor interpretation: `window_days` is a per-transform module constant, not read from
`FeaturesConfig`'s per-spec `params` at resolve time (deviation from a literal reading of
`resolve_feature_set`'s inputs).** `config/features.yaml` also carries a `window_days` value per
family, authored in plan 01-03, and the two are kept numerically identical by hand. This plan's
own `<action>` text describes `FEATURE_SET_VERSION` as a plain module constant used directly
(never called) at `compute.py`'s `extra_metadata={"feature_set_version": FEATURE_SET_VERSION}`
call site -- which is only possible if every registered transform (including its `sql_expression`,
which embeds `window_days`) is fully resolved at import time, independent of which config object a
caller later passes to `resolve_feature_set`. Since every profile in this repository shares the
same base `features.yaml` (profiles override only `simulator:`), `resolve_feature_set(config)`
for every profile in practice returns exactly the twelve module-level transforms below, in the
config's declared order -- so this interpretation changes no observable behavior for any config
this repository ships, while keeping `FEATURE_SET_VERSION` a genuine constant. `resolve_feature_set`
still raises `KeyError` naming any config-declared spec with no registered implementation, which is
what makes the config the source of truth for *which* families are active and in what order.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from nextmove.config.models import FeaturesConfig

__all__ = [
    "FEATURE_SET_VERSION",
    "FEATURE_TRANSFORMS",
    "FeatureTransform",
    "register_transform",
    "resolve_feature_set",
]


def normalize_identifier(value: str) -> str:
    """NFC-normalize a category or sku identifier before it is used as a comparison or grouping
    key. Never case-folds and never trims whitespace: the catalog (plan 01-08) holds the single
    canonical spelling, and folding case or stripping whitespace here would silently merge two
    distinct catalog entries.
    """
    return unicodedata.normalize("NFC", value)


class FeatureTransform(BaseModel):
    """One registered feature family: a versioned SQL fragment plus the metadata that makes its
    empty-customer default explicit and its dtype declared rather than inferred.

    `sql_expression` is a scalar SQL expression, correlated on `grid_anchor.customer_id` and
    `grid_anchor.as_of_ts` (see `nextmove.features.compute._build_asof_sql`), that a caller
    composes into one ASOF-joined statement alongside every other registered transform. It
    always enforces `<= grid_anchor.as_of_ts` itself (and, when `window_days` is set, `>
    grid_anchor.as_of_ts - INTERVAL window_days DAY`) so point-in-time correctness does not
    depend on any join clause outside this expression -- the ASOF join in `_build_asof_sql`
    establishes the same inclusive boundary structurally, but each transform's own boundary is
    what a leakage test actually exercises.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    output_column: str = Field(min_length=1)
    dtype: str = Field(min_length=1)
    empty_default: float | int | str | None
    window_days: int | None = Field(default=None, gt=0)
    sql_expression: str = Field(min_length=1)


FEATURE_TRANSFORMS: dict[str, FeatureTransform] = {}


def register_transform(
    factory: Callable[[], FeatureTransform],
) -> Callable[[], FeatureTransform]:
    """Decorator: call `factory()` once at decoration time and register the resulting
    `FeatureTransform` under its own `.name`. Raises `ValueError` naming the duplicate rather
    than silently overwriting an existing registration."""
    transform = factory()
    if transform.name in FEATURE_TRANSFORMS:
        raise ValueError(
            f"transform {transform.name!r} is already registered; register_transform never "
            "silently overwrites an existing registration"
        )
    FEATURE_TRANSFORMS[transform.name] = transform
    return factory


def resolve_feature_set(config: FeaturesConfig) -> list[FeatureTransform]:
    """Return one resolved `FeatureTransform` per spec named in `config.features`, in the
    config's declared list order. Raises `KeyError` naming any spec with no registered
    implementation."""
    resolved: list[FeatureTransform] = []
    for spec in config.features:
        transform = FEATURE_TRANSFORMS.get(spec.name)
        if transform is None:
            raise KeyError(
                f"no registered transform for feature spec {spec.name!r}; registered names are "
                f"{sorted(FEATURE_TRANSFORMS)!r}"
            )
        resolved.append(transform)
    return resolved


def _compute_feature_set_version(transforms: list[FeatureTransform]) -> str:
    """Stable sha256 over the canonical JSON of `transforms`' names, output columns, dtypes and
    SQL expressions -- the same canonicalization discipline `nextmove.config.loader.config_hash`
    uses (sorted keys, tight separators), so the hash is immune to registration order."""
    canonical = json.dumps(
        [
            {
                "name": t.name,
                "output_column": t.output_column,
                "dtype": t.dtype,
                "sql_expression": t.sql_expression,
            }
            for t in transforms
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------
# Twelve FEAT-01 family transforms, one per name in config/features.yaml. Every window_days
# value below is kept numerically identical, by hand, to config/features.yaml's per-feature
# `params.window_days` -- see the module docstring's "Executor interpretation" note for why
# this is a module constant rather than a value threaded through resolve_feature_set.
# ---------------------------------------------------------------------------------------


@register_transform
def _rfm_recency() -> FeatureTransform:
    return FeatureTransform(
        name="rfm_recency",
        output_column="rfm_recency_days",
        dtype="int64",
        empty_default=None,  # documented: null means "no prior order"
        window_days=None,
        sql_expression=(
            "(SELECT date_diff('day', MAX(e.ts), grid_anchor.as_of_ts) FROM events e "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'order_placed' "
            "AND e.ts <= grid_anchor.as_of_ts)"
        ),
    )


@register_transform
def _rfm_frequency() -> FeatureTransform:
    window_days = 90
    return FeatureTransform(
        name="rfm_frequency",
        output_column="rfm_frequency_count",
        dtype="int64",
        empty_default=0,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT COUNT(*)::BIGINT FROM events e "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'order_placed' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0)"
        ),
    )


@register_transform
def _rfm_monetary() -> FeatureTransform:
    window_days = 90
    return FeatureTransform(
        name="rfm_monetary",
        output_column="rfm_monetary_cents",
        dtype="int64",
        empty_default=0,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT "
            "SUM(json_extract_string(e.payload, '$.order_total_cents')::BIGINT)::BIGINT "
            "FROM events e WHERE e.customer_id = grid_anchor.customer_id "
            "AND e.type = 'order_placed' AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0)"
        ),
    )


@register_transform
def _session_visits() -> FeatureTransform:
    window_days = 30
    return FeatureTransform(
        name="session_visits",
        output_column="session_visits_count",
        dtype="int64",
        empty_default=0,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT COUNT(*)::BIGINT FROM events e "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'session_start' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0)"
        ),
    )


@register_transform
def _session_depth() -> FeatureTransform:
    window_days = 30
    return FeatureTransform(
        name="session_depth",
        output_column="session_depth_mean_views",
        dtype="float64",
        empty_default=0.0,
        window_days=window_days,
        sql_expression=(
            "COALESCE(round_even("
            "(SELECT COUNT(*) FROM events e WHERE e.customer_id = grid_anchor.customer_id "
            "AND e.type = 'product_view' AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY)::DOUBLE "
            "/ NULLIF((SELECT COUNT(DISTINCT e.session_id) FROM events e "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'session_start' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0), 6), 0.0)"
        ),
    )


@register_transform
def _session_dwell() -> FeatureTransform:
    window_days = 30
    # Key order and separators matter here: this string must be byte-identical to what the SQL
    # expression's own `json_object(...)` call below produces for a customer with zero matching
    # rows (DuckDB's json_object is never null, so the SQL's COALESCE fallback never actually
    # fires -- this literal exists to document the shape, and the leakage suite's empty-case
    # test asserts the two agree byte for byte). `json.dumps` with `sort_keys=True` would
    # alphabetize and add spaces, producing a different (still valid, but non-identical) string.
    empty_json = json.dumps({"short": 0, "medium": 0, "long": 0}, separators=(",", ":"))
    return FeatureTransform(
        name="session_dwell",
        output_column="session_dwell_counts_json",
        dtype="string",
        empty_default=empty_json,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT json_object("
            "'short', COUNT(*) FILTER (WHERE json_extract_string(e.payload, '$.dwell_class') "
            "= 'short'), "
            "'medium', COUNT(*) FILTER (WHERE json_extract_string(e.payload, '$.dwell_class') "
            "= 'medium'), "
            "'long', COUNT(*) FILTER (WHERE json_extract_string(e.payload, '$.dwell_class') "
            "= 'long')) "
            "FROM events e WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'dwell' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), "
            f"'{empty_json}')"
        ),
    )


@register_transform
def _category_affinity() -> FeatureTransform:
    window_days = 90
    return FeatureTransform(
        name="category_affinity",
        output_column="category_affinity_json",
        dtype="string",
        empty_default="{}",
        window_days=window_days,
        sql_expression=(
            "(SELECT COALESCE(json_group_object("
            "nfc_normalize(cat), round_even(cnt::DOUBLE / NULLIF(total, 0), 6)), '{}') "
            "FROM (SELECT json_extract_string(e.payload, '$.category') AS cat, "
            "COUNT(*) AS cnt, SUM(COUNT(*)) OVER () AS total "
            "FROM events e WHERE e.customer_id = grid_anchor.customer_id "
            "AND e.type = 'product_view' AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY "
            "GROUP BY cat) sub)"
        ),
    )


@register_transform
def _price_sensitivity_proxy() -> FeatureTransform:
    window_days = 90
    return FeatureTransform(
        name="price_sensitivity_proxy",
        output_column="price_sensitivity_proxy",
        dtype="float64",
        empty_default=0.0,
        window_days=window_days,
        sql_expression=(
            "COALESCE(round_even("
            "(SELECT COUNT(*) FROM events e, json_each(e.payload::JSON -> '$.line_items') li "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'order_placed' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY "
            "AND (li.value ->> 'discount_cents')::BIGINT > 0)::DOUBLE "
            "/ NULLIF((SELECT COUNT(*) FROM events e, "
            "json_each(e.payload::JSON -> '$.line_items') li "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'order_placed' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0), 6), 0.0)"
        ),
    )


@register_transform
def _message_fatigue_count() -> FeatureTransform:
    window_days = 14
    return FeatureTransform(
        name="message_fatigue_count",
        output_column="message_fatigue_count",
        dtype="int64",
        empty_default=0,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT COUNT(*)::BIGINT FROM events e "
            "WHERE e.customer_id = grid_anchor.customer_id "
            "AND e.type IN ('campaign_exposure', 'action_delivered') "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0)"
        ),
    )


@register_transform
def _cart_state() -> FeatureTransform:
    return FeatureTransform(
        name="cart_state",
        output_column="cart_state_units",
        dtype="int64",
        empty_default=0,
        window_days=None,
        sql_expression=(
            "GREATEST(COALESCE(("
            "SELECT (COALESCE(SUM(CASE WHEN e.type = 'add_to_cart' "
            "THEN (e.payload::JSON ->> 'quantity')::BIGINT ELSE 0 END), 0) "
            "- COALESCE(SUM(CASE WHEN e.type = 'cart_remove' "
            "THEN (e.payload::JSON ->> 'quantity')::BIGINT ELSE 0 END), 0))::BIGINT "
            "FROM events e WHERE e.customer_id = grid_anchor.customer_id "
            "AND e.type IN ('add_to_cart', 'cart_remove') AND e.ts <= grid_anchor.as_of_ts "
            "AND e.ts > COALESCE((SELECT MAX(c.ts) FROM events c "
            "WHERE c.customer_id = grid_anchor.customer_id "
            "AND c.type IN ('cart_abandon', 'order_placed') "
            "AND c.ts <= grid_anchor.as_of_ts), TIMESTAMPTZ '1970-01-01+00')"
            "), 0), 0)"
        ),
    )


@register_transform
def _abandonment_history() -> FeatureTransform:
    window_days = 90
    return FeatureTransform(
        name="abandonment_history",
        output_column="abandonment_history_count",
        dtype="int64",
        empty_default=0,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT COUNT(*)::BIGINT FROM events e "
            "WHERE e.customer_id = grid_anchor.customer_id AND e.type = 'cart_abandon' "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), 0)"
        ),
    )


@register_transform
def _micro_conversion_aggregates() -> FeatureTransform:
    window_days = 30
    # Key order/separators pinned to match the SQL's own json_object(...) output byte for byte --
    # see _session_dwell's comment for why this matters even though the SQL fallback never fires.
    empty_json = json.dumps({"scroll": 0, "filter_apply": 0, "dwell": 0}, separators=(",", ":"))
    return FeatureTransform(
        name="micro_conversion_aggregates",
        output_column="micro_conversion_counts_json",
        dtype="string",
        empty_default=empty_json,
        window_days=window_days,
        sql_expression=(
            "COALESCE((SELECT json_object("
            "'scroll', COUNT(*) FILTER (WHERE e.type = 'scroll'), "
            "'filter_apply', COUNT(*) FILTER (WHERE e.type = 'filter_apply'), "
            "'dwell', COUNT(*) FILTER (WHERE e.type = 'dwell')) "
            "FROM events e WHERE e.customer_id = grid_anchor.customer_id "
            "AND e.type IN ('scroll', 'filter_apply', 'dwell') "
            "AND e.ts <= grid_anchor.as_of_ts "
            f"AND e.ts > grid_anchor.as_of_ts - INTERVAL {window_days} DAY), "
            f"'{empty_json}')"
        ),
    )


# Computed once at import time from every registered transform, sorted by name for an order
# independent of registration order -- the module constant `compute.py` stamps directly into
# `extra_metadata`, never called.
FEATURE_SET_VERSION: str = _compute_feature_set_version(
    sorted(FEATURE_TRANSFORMS.values(), key=lambda t: t.name)
)
