"""A3: the config-driven action catalog and the ActionProvider registry."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nextmove.config.loader import load_config
from nextmove.config.models import ActionsConfig
from nextmove.decisions.actions import (
    Candidate,
    CatalogActionProvider,
    action_provider_registry,
    build_providers,
    generate_candidates,
    register_action_provider,
)
from nextmove.decisions.context import BusinessState, DecisionContext


def _context() -> DecisionContext:
    return DecisionContext(
        customer_id="c1",
        as_of=datetime(2024, 3, 1, tzinfo=UTC),
        primary_category="fashion_apparel",
        features={},
        business=BusinessState(
            category_min_stock_units={"fashion_apparel": 100},
            low_stock_threshold=20,
            category_margin_rate={"fashion_apparel": 0.45},
            category_avg_price_cents={"fashion_apparel": 10000},
            top_seller_category="fashion_apparel",
        ),
    )


def test_repository_catalog_has_eight_archetypes_including_restraint() -> None:
    actions = load_config("tiny").config.actions
    names = [archetype.name for archetype in actions.catalog]
    assert len(names) == 8
    assert {"none", "wait"} <= set(names)


def test_catalog_provider_expands_variants_with_stable_ids() -> None:
    actions = load_config("tiny").config.actions
    candidates = CatalogActionProvider(actions).expand(_context())
    ids = [candidate.id for candidate in candidates]
    assert "none" in ids and "wait" in ids
    assert "discount_low__1000bps" in ids
    assert len(ids) == len(set(ids))
    by_id = {candidate.id: candidate for candidate in candidates}
    assert by_id["discount_low__1000bps"].discount_bps == 1000
    assert not by_id["none"].contact and not by_id["wait"].contact


@pytest.mark.parametrize("missing", ["none", "wait"])
def test_catalog_without_restraint_fails_validation(missing: str) -> None:
    raw = load_config("tiny").config.actions.model_dump()
    raw["catalog"] = [a for a in raw["catalog"] if a["name"] != missing]
    with pytest.raises(ValidationError, match=missing):
        ActionsConfig.model_validate(raw)


def test_multi_variant_archetype_requires_suffixes() -> None:
    raw = load_config("tiny").config.actions.model_dump()
    raw["catalog"][2]["variants"][0]["suffix"] = None
    with pytest.raises(ValidationError, match="suffix"):
        ActionsConfig.model_validate(raw)


def test_generate_candidates_always_adds_restraint() -> None:
    actions = load_config("tiny").config.actions

    class OnlyEmail:
        name = "only_email"

        def expand(self, context: DecisionContext) -> list[Candidate]:
            return [Candidate(id="email_now", archetype="email_now", contact=True, cost_cents=1)]

    ids = [c.id for c in generate_candidates(_context(), [OnlyEmail()], actions)]
    assert ids[0] == "email_now"
    assert {"none", "wait"} <= set(ids)


def test_registry_rejects_duplicate_names() -> None:
    assert "catalog" in action_provider_registry()
    with pytest.raises(ValueError, match="already registered"):
        register_action_provider("catalog")(CatalogActionProvider)


def test_build_providers_defaults_to_all_registered() -> None:
    actions = load_config("tiny").config.actions
    providers = build_providers(actions, ["catalog"])
    assert [p.name for p in providers] == ["catalog"]
