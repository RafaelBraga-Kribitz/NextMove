"""The model-facing feature vector built from a `DecisionContext`, and the action encoding.

One function, `context_row`, is used both when the experiment log is written (training) and
when a decision is made (serving), so train/serve skew is structurally impossible. Missing
values are handled here, explicitly: `rfm_recency_days` is null for a customer with no order,
which becomes `has_ordered = 0` plus a recency equal to the cap (documented in each model card).
"""

from __future__ import annotations

import math

from nextmove.decisions.context import DecisionContext

__all__ = [
    "ACTION_COLUMNS_PREFIX",
    "CONTEXT_FEATURES",
    "RECENCY_CAP_DAYS",
    "action_columns",
    "action_row",
    "context_row",
    "context_feature_names",
]

#: Recency assigned to customers who never ordered (alongside has_ordered = 0).
RECENCY_CAP_DAYS = 365.0

CONTEXT_FEATURES: tuple[str, ...] = (
    "has_ordered",
    "rfm_recency_days",
    "rfm_frequency_count",
    "rfm_monetary_cents",
    "session_visits_count",
    "session_depth_mean_views",
    "price_sensitivity_proxy",
    "message_fatigue_count",
    "cart_state_units",
    "abandonment_history_count",
    "dwell_long_count",
    "dwell_medium_count",
    "scroll_count",
    "filter_apply_count",
    "primary_affinity_share",
    "contacts_7d",
    "contacts_total",
    "tenure_days",
    "month_sin",
    "month_cos",
    "low_stock",
)

#: Action encoding appended to the context features: one indicator per archetype plus the
#: discount depth, so discount variants share one arm with a magnitude.
ACTION_COLUMNS_PREFIX = "action_is_"


def context_feature_names(categories: list[str]) -> list[str]:
    return [*CONTEXT_FEATURES, *(f"primary_is_{c}" for c in categories)]


def context_row(context: DecisionContext, categories: list[str]) -> list[float]:
    f = context.features
    recency = f.get("rfm_recency_days")
    month = float(f.get("month") or context.as_of.month)
    values = {
        "has_ordered": 0.0 if recency is None else 1.0,
        "rfm_recency_days": RECENCY_CAP_DAYS if recency is None else min(recency, RECENCY_CAP_DAYS),
        "month_sin": math.sin(2 * math.pi * month / 12),
        "month_cos": math.cos(2 * math.pi * month / 12),
        "low_stock": 1.0 if context.business.is_scarce(context.primary_category) else 0.0,
    }
    row = []
    for name in CONTEXT_FEATURES:
        if name in values:
            row.append(float(values[name]))
        else:
            value = f.get(name)
            row.append(0.0 if value is None else float(value))
    row.extend(1.0 if context.primary_category == c else 0.0 for c in categories)
    return row


def action_columns(archetypes: list[str]) -> list[str]:
    return [*(f"{ACTION_COLUMNS_PREFIX}{a}" for a in archetypes), "discount_depth"]


def action_row(archetype: str, discount_bps: int, archetypes: list[str]) -> list[float]:
    return [*(1.0 if archetype == a else 0.0 for a in archetypes), discount_bps / 10_000]
