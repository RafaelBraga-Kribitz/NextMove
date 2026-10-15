"""A5: the four AC-10 baselines choose only among survivors, deterministically."""

from datetime import UTC, datetime

import pytest

from nextmove.config.loader import load_config
from nextmove.decisions.actions import build_providers, generate_candidates
from nextmove.decisions.context import BusinessState, DecisionContext
from nextmove.policies.base import pick
from nextmove.policies.baselines import (
    AlwaysDiscountPolicy,
    DoNothingPolicy,
    RulesOnlyPolicy,
    TopSellerPolicy,
    baseline_policies,
)
from nextmove.rules import RuleSet

CONFIG = load_config("tiny").config
RULES = RuleSet.from_config(CONFIG.constraints)
BASELINES = CONFIG.policies.baselines


def _context(stock: int = 100, contacts=(), **features) -> DecisionContext:
    return DecisionContext(
        customer_id="c1",
        as_of=datetime(2024, 3, 1, tzinfo=UTC),
        primary_category="fashion_apparel",
        features=features,
        contact_days_ago=contacts,
        business=BusinessState(
            category_min_stock_units={"fashion_apparel": stock},
            low_stock_threshold=20,
            category_margin_rate={"fashion_apparel": 0.45},
            category_avg_price_cents={"fashion_apparel": 10000},
            top_seller_category="fashion_apparel",
        ),
    )


def _choose(policy, context) -> str:
    candidates = generate_candidates(
        context, build_providers(CONFIG.actions, ["catalog"]), CONFIG.actions
    )
    outcome = RULES.apply(candidates, context)
    ranked = pick(
        policy.score(context, outcome.survivors, outcome.penalties_cents), outcome.survivors
    )
    return ranked[0].candidate.id


def test_do_nothing() -> None:
    assert _choose(DoNothingPolicy(), _context()) == "none"


def test_always_discount_takes_largest_allowed() -> None:
    # 3000 bps is above the ceiling, so 2000 bps is the largest allowed.
    assert _choose(AlwaysDiscountPolicy(), _context()) == "discount_high__2000bps"


def test_always_discount_falls_back_to_none_when_scarce() -> None:
    assert _choose(AlwaysDiscountPolicy(), _context(stock=3)) == "none"


def test_top_seller() -> None:
    assert _choose(TopSellerPolicy(BASELINES), _context()) == "recommend__top_seller"


def test_top_seller_respects_frequency_cap() -> None:
    assert _choose(TopSellerPolicy(BASELINES), _context(contacts=(0, 1))) == "none"


@pytest.mark.parametrize(
    ("features", "expected"),
    [
        ({"cart_state_units": 2, "price_sensitivity_proxy": 0.5}, "discount_low__1000bps"),
        ({"cart_state_units": 2, "price_sensitivity_proxy": 0.0}, "none"),
        ({"session_visits_count": 6}, "recommend__affinity"),
        ({"rfm_recency_days": 90}, "email_delayed"),
        ({"rfm_recency_days": None}, "none"),
    ],
)
def test_rules_only_playbook(features, expected) -> None:
    assert _choose(RulesOnlyPolicy(BASELINES), _context(**features)) == expected


def test_baseline_names_are_unique() -> None:
    names = [policy.name for policy in baseline_policies(BASELINES)]
    assert names == ["do_nothing", "always_discount", "top_seller", "rules_only"]
