"""A4: constraint registry semantics, the AC-2 property test, and the AC-13 example plugin."""

import ast
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nextmove.config.loader import load_config
from nextmove.config.models import ConstraintsConfig, ConstraintSpec
from nextmove.decisions.actions import (
    Candidate,
    build_providers,
    generate_candidates,
)
from nextmove.decisions.context import BusinessState, DecisionContext
from nextmove.rules import RuleSet

REPO = Path(__file__).resolve().parents[2]
CONFIG = load_config("tiny").config
CATEGORIES = ("fashion_apparel", "home_basics")


def _context(
    stock: int = 100,
    contacts: tuple[int, ...] = (),
    category: str = "fashion_apparel",
    margin: float = 0.45,
    recency: float | None = None,
) -> DecisionContext:
    return DecisionContext(
        customer_id="c1",
        as_of=datetime(2024, 3, 1, tzinfo=UTC),
        primary_category=category,
        features={"rfm_recency_days": recency},
        contact_days_ago=contacts,
        business=BusinessState(
            category_min_stock_units={c: stock for c in CATEGORIES},
            low_stock_threshold=20,
            category_margin_rate={c: margin for c in CATEGORIES},
            category_avg_price_cents={c: 10000 for c in CATEGORIES},
            top_seller_category="fashion_apparel",
        ),
    )


def _candidates(context: DecisionContext) -> list[Candidate]:
    return generate_candidates(
        context, build_providers(CONFIG.actions, ["catalog"]), CONFIG.actions
    )


RULES = RuleSet.from_config(CONFIG.constraints)


def test_precedence_order_is_compliance_first() -> None:
    precedences = [c.spec.precedence for c in RULES.constraints]
    order = ["compliance", "inventory", "campaign", "preference"]
    assert precedences == sorted(precedences, key=order.index)


def test_discount_ceiling_filters_large_discount() -> None:
    outcome = RULES.apply(_candidates(_context()), _context())
    filtered = {r.candidate_id: r.rule for r in outcome.filtered}
    assert filtered["discount_high__3000bps"] == "discount_ceiling"
    assert "discount_high__2000bps" not in filtered
    assert "discount_ceiling" in outcome.fired_rules


def test_scarcity_suppresses_discounts_and_bundles() -> None:
    context = _context(stock=5)
    outcome = RULES.apply(_candidates(context), context)
    filtered = {r.candidate_id: r.rule for r in outcome.filtered}
    assert filtered["discount_low__500bps"] == "inventory_scarcity_gate"
    assert filtered["bundle"] == "inventory_scarcity_gate"
    assert "email_now" not in filtered


def test_margin_floor_on_low_margin_category() -> None:
    context = _context(margin=0.35, category="home_basics")
    outcome = RULES.apply(_candidates(context), context)
    filtered = {r.candidate_id: r.rule for r in outcome.filtered}
    assert filtered["discount_high__2000bps"] == "margin_floor"
    assert "discount_low__1000bps" not in filtered


def test_frequency_cap_blocks_all_contact_but_never_restraint() -> None:
    context = _context(contacts=(1, 3))
    outcome = RULES.apply(_candidates(context), context)
    survivor_ids = {c.id for c in outcome.survivors}
    assert survivor_ids == {"none", "wait"}


def test_soft_fatigue_penalty_is_graded() -> None:
    context = _context(contacts=(10,))
    outcome = RULES.apply(_candidates(context), context)
    assert outcome.penalties_cents["email_now"] == 15
    assert outcome.penalties_cents["none"] == 0
    assert "fatigue_penalty" in outcome.fired_rules


def test_unregistered_kind_fails_loudly() -> None:
    config = ConstraintsConfig(
        rules=[ConstraintSpec(name="x", kind="nope", mode="hard", precedence="compliance")]
    )
    with pytest.raises(KeyError, match="unregistered"):
        RuleSet.from_config(config)


# ------------------------------------------------------------------------------------------
# AC-2: >=10k randomized contexts, zero hard-constraint violations in what a policy can pick.
# ------------------------------------------------------------------------------------------


def _independent_hard_violation(candidate: Candidate, context: DecisionContext) -> bool:
    """A reimplementation of the configured hard rules straight from config params, kept
    deliberately separate from nextmove.rules so a bug there cannot hide here."""
    params = {rule.kind: rule.params for rule in CONFIG.constraints.rules if rule.mode == "hard"}
    if candidate.discount_bps > params["discount_ceiling"]["max_discount_bps"]:
        return True
    if candidate.discount_bps > 0 and (
        context.margin_rate - candidate.discount_bps / 10_000
        < params["margin_floor"]["min_margin_rate_after_discount"] - 1e-12
    ):
        return True
    stock = context.business.category_min_stock_units[context.primary_category]
    if (
        candidate.archetype in params["inventory_scarcity"]["archetypes"]
        and stock <= context.business.low_stock_threshold
    ):
        return True
    cap = params["frequency_cap"]
    recent = sum(1 for d in context.contact_days_ago if d < cap["window_days"])
    return candidate.contact and recent >= cap["max_contacts"]


context_strategy = st.builds(
    _context,
    stock=st.integers(min_value=0, max_value=300),
    contacts=st.lists(st.integers(min_value=0, max_value=60), max_size=6).map(
        lambda days: tuple(sorted(days))
    ),
    category=st.sampled_from(CATEGORIES),
    margin=st.floats(min_value=0.05, max_value=0.9),
)

extra_discount = st.integers(min_value=0, max_value=6000)


@settings(
    max_examples=10_000,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(context=context_strategy, bps=extra_discount, scores=st.randoms(use_true_random=False))
def test_ac2_no_policy_can_choose_a_hard_excluded_action(context, bps, scores) -> None:
    candidates = _candidates(context) + [
        Candidate(
            id=f"discount_low__adversarial{bps}",
            archetype="discount_low",
            params={"discount_bps": bps},
            contact=True,
            cost_cents=0,
        )
    ]
    outcome = RULES.apply(candidates, context)
    # An adversarial "learned" scorer: favours exactly the riskiest candidates.
    ranked = sorted(
        outcome.survivors,
        key=lambda c: (c.discount_bps + 1000 * c.contact + scores.random(), c.id),
        reverse=True,
    )
    chosen = ranked[0]
    assert not _independent_hard_violation(chosen, context)
    for survivor in outcome.survivors:
        assert not _independent_hard_violation(survivor, context)
    for record in outcome.filtered:
        candidate = next(c for c in candidates if c.id == record.candidate_id)
        assert _independent_hard_violation(candidate, context)
    assert {"none", "wait"} <= {c.id for c in outcome.survivors}


# ------------------------------------------------------------------------------------------
# AC-13: the in-repo example plugin adds a Constraint and an ActionProvider via registries.
# ------------------------------------------------------------------------------------------


def _load_plugin():
    path = REPO / "examples" / "plugin_example.py"
    if "nextmove_example_plugin" in sys.modules:
        return sys.modules["nextmove_example_plugin"]
    spec = importlib.util.spec_from_file_location("nextmove_example_plugin", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nextmove_example_plugin"] = module
    spec.loader.exec_module(module)
    return module


def test_ac13_plugin_registers_constraint_and_provider_without_core_edits() -> None:
    _load_plugin()
    constraints = ConstraintsConfig(
        rules=[
            *CONFIG.constraints.rules,
            ConstraintSpec(
                name="quiet_after_purchase",
                kind="quiet_after_purchase",
                mode="hard",
                precedence="preference",
                params={"quiet_days": 3},
            ),
        ]
    )
    rules = RuleSet.from_config(constraints)
    context = _context(recency=1.0)
    providers = build_providers(CONFIG.actions, ["catalog", "loyalty_points"])
    candidates = generate_candidates(context, providers, CONFIG.actions)
    assert "loyalty_points__double" in {c.id for c in candidates}
    outcome = rules.apply(candidates, context)
    filtered = {r.candidate_id: r.rule for r in outcome.filtered}
    assert filtered["loyalty_points__double"] == "quiet_after_purchase"
    assert filtered["email_now"] == "quiet_after_purchase"
    relaxed = _context(recency=10.0)
    survivors = {c.id for c in rules.apply(candidates, relaxed).survivors}
    assert "loyalty_points__double" in survivors


def test_ac13_plugin_uses_only_public_registry_api() -> None:
    tree = ast.parse((REPO / "examples" / "plugin_example.py").read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("nextmove")
    }
    assert imported <= {
        "nextmove.config.models",
        "nextmove.decisions.actions",
        "nextmove.decisions.context",
        "nextmove.rules",
    }
