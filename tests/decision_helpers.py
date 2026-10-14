"""Shared builders for decision-layer tests."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from nextmove.config.loader import load_config
from nextmove.decisions.actions import build_providers
from nextmove.decisions.context import BusinessState, DecisionContext
from nextmove.decisions.engine import DecisionEngine
from nextmove.rules import RuleSet

CONFIG = load_config("tiny")
CATEGORIES = ["fashion_apparel", "home_basics"]


def make_context(
    customer_id: str = "7",
    day: int = 3,
    stock: int = 100,
    contacts: tuple[int, ...] = (),
    category: str = "fashion_apparel",
    **features: float | None,
) -> DecisionContext:
    base: dict[str, float | None] = {
        "rfm_recency_days": 20.0,
        "rfm_frequency_count": 1.0,
        "rfm_monetary_cents": 4000.0,
        "session_visits_count": 3.0,
        "session_depth_mean_views": 2.5,
        "price_sensitivity_proxy": 0.3,
        "message_fatigue_count": 2.0,
        "cart_state_units": 0.0,
        "abandonment_history_count": 1.0,
        "dwell_long_count": 1.0,
        "dwell_medium_count": 2.0,
        "scroll_count": 3.0,
        "filter_apply_count": 1.0,
        "primary_affinity_share": 0.7,
        "contacts_7d": float(sum(1 for d in contacts if d < 7)),
        "contacts_total": float(len(contacts)),
        "tenure_days": 40.0,
        "month": 3.0,
    }
    base.update(features)
    return DecisionContext(
        customer_id=customer_id,
        as_of=datetime(2024, 3, 1 + day, tzinfo=UTC),
        primary_category=category,
        features=base,
        contact_days_ago=contacts,
        business=BusinessState(
            category_min_stock_units={c: stock for c in CATEGORIES},
            low_stock_threshold=20,
            category_margin_rate={"fashion_apparel": 0.45, "home_basics": 0.35},
            category_avg_price_cents={"fashion_apparel": 3049, "home_basics": 4409},
            top_seller_category="fashion_apparel",
        ),
    )


class StubResponseModel:
    """A deterministic, BLAS-free response model for golden files: a fixed logit per
    archetype plus a small linear effect of two features, identical on every platform."""

    family = "stub"
    version = "stub-1"
    archetypes = [a.name for a in CONFIG.config.actions.catalog]
    _base = {
        "none": -3.2,
        "wait": -3.2,
        "recommend": -3.0,
        "bundle": -3.1,
        "discount_low": -3.05,
        "discount_high": -2.9,
        "email_now": -3.15,
        "email_delayed": -3.18,
    }

    def predict_members(self, x, archetypes, depth) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        logits = np.array([self._base[a] for a in archetypes]) + 0.01 * x[:, 6] - 0.02 * x[:, 16]
        logits = logits + 2.0 * np.asarray(depth, dtype=float)
        members = np.stack([logits + shift for shift in (-0.05, 0.0, 0.05, 0.1)], axis=1)
        return np.round(1.0 / (1.0 + np.exp(-members)), 9)

    def uplift_attributions(self, x_row, archetype, depth):
        x_row = np.asarray(x_row, dtype=float)
        return [
            ("price_sensitivity_proxy", round(0.01 * x_row[6], 6)),
            ("contacts_total", round(-0.02 * x_row[16], 6)),
            (f"action:{archetype}", round(self._base[archetype] - self._base["none"], 6)),
        ]


def engine_for(policy, config=CONFIG, min_confidence=None) -> DecisionEngine:
    cfg = config.config
    return DecisionEngine(
        policy,
        RuleSet.from_config(cfg.constraints),
        build_providers(cfg.actions, ["catalog"]),
        cfg.actions,
        config.config_hash,
        min_confidence,
    )
