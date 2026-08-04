"""Pins the chosen latent-trait distribution behaviour (RESEARCH Assumption A3, Open
Question 1) and machine-asserts SIM-01's world-structure claims: trait bounds, config-driven
generation, and the D-01 seasonality contrast. Runs entirely against the `tiny` profile so the
suite stays fast; nothing here builds a 50000-customer world.
"""

import datetime as dt
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nextmove.config.loader import load_config
from nextmove.config.models import SimulatorConfig, TraitDistribution
from nextmove.simulator.traits import draw_trait_value, sample_latent_traits, trait_support
from nextmove.simulator.world import Campaign, Catalog, Customer, InventoryState, Sku, World


@pytest.fixture(scope="module")
def tiny_sim_config() -> SimulatorConfig:
    return load_config("tiny").config.simulator


def _mutated(sim: SimulatorConfig, mutate) -> SimulatorConfig:
    """Round-trip `sim` through a dict, apply `mutate` in place, and re-validate. This is how
    the "config-drives-behaviour" tests below produce a config that differs from `sim` by
    exactly one value."""
    data = sim.model_dump(mode="python")
    mutate(data)
    return SimulatorConfig.model_validate(data)


def _config_with_degenerate_trait(
    sim: SimulatorConfig, trait_field: str, value: float
) -> SimulatorConfig:
    """A config where `trait_field` (a `latent_traits` key) is forced to a `uniform`
    distribution degenerate at exactly `value` — i.e. its configured support is `[value,
    value]`, so a draw from it is guaranteed to equal `value` exactly."""

    def mutate(data: dict) -> None:
        data["latent_traits"][trait_field] = {
            "family": "uniform",
            "params": {"low": value, "high": value},
        }

    return _mutated(sim, mutate)


# ---------------------------------------------------------------------------------------
# Task 2 behavior: latent trait sampling
# ---------------------------------------------------------------------------------------


class TestSampleLatentTraits:
    def test_deterministic_across_two_calls(self, tiny_sim_config: SimulatorConfig) -> None:
        first = sample_latent_traits(7, tiny_sim_config)
        second = sample_latent_traits(7, tiny_sim_config)
        assert first == second

    def test_category_affinity_keys_match_configured_categories(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        traits = sample_latent_traits(1, tiny_sim_config)
        expected_names = {category.name for category in tiny_sim_config.categories}
        assert set(traits.category_affinity) == expected_names

    def test_category_affinity_sums_to_one(self, tiny_sim_config: SimulatorConfig) -> None:
        traits = sample_latent_traits(1, tiny_sim_config)
        assert sum(traits.category_affinity.values()) == pytest.approx(1.0, abs=1e-4)

    def test_changing_one_distribution_parameter_changes_sampled_traits(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        baseline = sample_latent_traits(1, tiny_sim_config)

        def bump_alpha(data: dict) -> None:
            data["latent_traits"]["price_sensitivity"]["params"]["alpha"] += 10.0

        mutated_config = _mutated(tiny_sim_config, bump_alpha)
        mutated = sample_latent_traits(1, mutated_config)

        assert mutated.price_sensitivity != baseline.price_sensitivity


class TestBoundarySupport:
    """Boundary — this plan's edge predicate: a trait drawn at exactly the minimum or maximum
    of its configured support is accepted and finite; a value outside the support is
    impossible by construction (must_haves.truths, edge: boundary)."""

    def test_price_sensitivity_degenerate_at_minimum_and_maximum(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        cfg_min = _config_with_degenerate_trait(tiny_sim_config, "price_sensitivity", 0.0)
        traits_min = sample_latent_traits(1, cfg_min)
        assert traits_min.price_sensitivity == 0.0
        assert math.isfinite(traits_min.price_sensitivity)

        cfg_max = _config_with_degenerate_trait(tiny_sim_config, "price_sensitivity", 1.0)
        traits_max = sample_latent_traits(1, cfg_max)
        assert traits_max.price_sensitivity == 1.0
        assert math.isfinite(traits_max.price_sensitivity)

    def test_loyalty_degenerate_at_minimum_and_maximum(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        cfg_min = _config_with_degenerate_trait(tiny_sim_config, "loyalty", 0.0)
        traits_min = sample_latent_traits(2, cfg_min)
        assert traits_min.loyalty == 0.0
        assert math.isfinite(traits_min.loyalty)

        cfg_max = _config_with_degenerate_trait(tiny_sim_config, "loyalty", 1.0)
        traits_max = sample_latent_traits(2, cfg_max)
        assert traits_max.loyalty == 1.0
        assert math.isfinite(traits_max.loyalty)

    def test_fatigue_propensity_degenerate_at_minimum_and_maximum(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        cfg_min = _config_with_degenerate_trait(tiny_sim_config, "fatigue", 0.0)
        traits_min = sample_latent_traits(3, cfg_min)
        assert traits_min.fatigue_propensity == 0.0
        assert math.isfinite(traits_min.fatigue_propensity)

        cfg_max = _config_with_degenerate_trait(tiny_sim_config, "fatigue", 8.0)
        traits_max = sample_latent_traits(3, cfg_max)
        assert traits_max.fatigue_propensity == 8.0
        assert math.isfinite(traits_max.fatigue_propensity)

    def test_category_affinity_raw_draw_degenerate_at_support_minimum_and_maximum(self) -> None:
        """`category_affinity`'s *final* value is a softmax over all categories' raw draws
        (see `nextmove.simulator.traits` module docstring), so it has no closed-form
        per-category "configured support" of its own — the boundary guarantee applies to the
        raw per-category draw all four traits share (`draw_trait_value`/`trait_support`),
        proven here directly rather than through `sample_latent_traits`."""
        import numpy as np

        dist_min = TraitDistribution(family="uniform", params={"low": -3.0, "high": -3.0})
        lo, hi = trait_support(dist_min)
        assert lo == hi == -3.0
        value = draw_trait_value(dist_min, np.random.default_rng(0))
        assert value == -3.0
        assert math.isfinite(value)

        dist_max = TraitDistribution(family="uniform", params={"low": 4.0, "high": 4.0})
        lo2, hi2 = trait_support(dist_max)
        assert lo2 == hi2 == 4.0
        value2 = draw_trait_value(dist_max, np.random.default_rng(0))
        assert value2 == 4.0
        assert math.isfinite(value2)

    @given(customer_id=st.integers(min_value=0, max_value=200_000))
    @settings(max_examples=50, deadline=None)
    def test_every_sampled_trait_within_inclusive_support(
        self, tiny_sim_config: SimulatorConfig, customer_id: int
    ) -> None:
        """A value one step outside the configured support is unreachable by construction,
        not merely unobserved — checked over many customer ids via `hypothesis`."""
        traits = sample_latent_traits(customer_id, tiny_sim_config)

        ps_lo, ps_hi = trait_support(tiny_sim_config.latent_traits.price_sensitivity)
        assert ps_lo <= traits.price_sensitivity <= ps_hi
        assert math.isfinite(traits.price_sensitivity)

        loy_lo, loy_hi = trait_support(tiny_sim_config.latent_traits.loyalty)
        assert loy_lo <= traits.loyalty <= loy_hi
        assert math.isfinite(traits.loyalty)

        fat_lo, fat_hi = trait_support(tiny_sim_config.latent_traits.fatigue)
        assert fat_lo <= traits.fatigue_propensity <= fat_hi
        assert math.isfinite(traits.fatigue_propensity)

        for affinity in traits.category_affinity.values():
            assert 0.0 <= affinity <= 1.0
            assert math.isfinite(affinity)


# ---------------------------------------------------------------------------------------
# Task 2 behavior: World.initialize
# ---------------------------------------------------------------------------------------


class TestWorldInitialize:
    def test_builds_exactly_n_customers_with_contiguous_ids(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = World.initialize(tiny_sim_config)
        assert len(world.customers) == tiny_sim_config.n_customers
        assert [customer.customer_id for customer in world.customers] == list(
            range(tiny_sim_config.n_customers)
        )

    def test_catalog_has_high_and_exactly_one_low_seasonality_category(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = World.initialize(tiny_sim_config)
        classes = [category.seasonality_class for category in tiny_sim_config.categories]
        assert classes.count("high") >= 1
        assert classes.count("low") == 1
        low_categories = {
            sku.category for sku in world.catalog.skus if sku.seasonality_class == "low"
        }
        assert len(low_categories) == 1

    def test_total_sku_count_matches_config(self, tiny_sim_config: SimulatorConfig) -> None:
        world = World.initialize(tiny_sim_config)
        expected = sum(category.sku_count for category in tiny_sim_config.categories)
        assert len(world.catalog.skus) == expected

    def test_every_sku_price_is_integer_cents_within_category_range(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = World.initialize(tiny_sim_config)
        ranges = {
            category.name: (category.base_price_cents_min, category.base_price_cents_max)
            for category in tiny_sim_config.categories
        }
        for sku in world.catalog.skus:
            assert isinstance(sku.base_price_cents, int)
            lo, hi = ranges[sku.category]
            assert lo <= sku.base_price_cents <= hi

    def test_seasonal_multiplier_matches_configured_month(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = World.initialize(tiny_sim_config)
        # tick 0 is start_date's month (January for the shipped config).
        expected = tiny_sim_config.seasonality.monthly_multipliers[
            world.clock.timestamp_for_tick(0).month - 1
        ]
        assert world.seasonal_multiplier(0) == expected

    def test_two_initializations_of_same_config_compare_equal(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world_a = World.initialize(tiny_sim_config)
        world_b = World.initialize(tiny_sim_config)
        assert world_a.customers == world_b.customers
        assert world_a.catalog == world_b.catalog
        assert world_a.campaigns == world_b.campaigns

    def test_differing_only_in_n_customers_preserves_shared_customer_traits(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        small_config = _mutated(tiny_sim_config, lambda data: data.update(n_customers=10))
        large_config = _mutated(tiny_sim_config, lambda data: data.update(n_customers=90))

        small_world = World.initialize(small_config)
        large_world = World.initialize(large_config)

        for customer_id in range(10):
            assert small_world.customers[customer_id].traits == (
                large_world.customers[customer_id].traits
            )


# ---------------------------------------------------------------------------------------
# Task 3: config-drives-behaviour and the D-01 seasonality contrast
# ---------------------------------------------------------------------------------------


class TestConfigDrivesBehaviour:
    """The SIM-01-scoped half of ENG-03's "changing YAML changes behaviour without a code
    edit" claim; plan 01-11 adds the end-to-end version."""

    def test_mutating_seasonality_and_trait_param_changes_generated_world(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        def mutate(data: dict) -> None:
            data["seasonality"]["monthly_multipliers"][0] += 0.5
            data["latent_traits"]["price_sensitivity"]["params"]["alpha"] += 5.0

        mutated_config = _mutated(tiny_sim_config, mutate)

        baseline_world = World.initialize(tiny_sim_config)
        mutated_world = World.initialize(mutated_config)

        assert baseline_world.seasonal_multiplier(0) != mutated_world.seasonal_multiplier(0)
        assert (
            baseline_world.customers[0].traits.price_sensitivity
            != mutated_world.customers[0].traits.price_sensitivity
        )


class TestSeasonalityContrast:
    """Mechanical statement of D-01: the low-seasonality category is measurably flatter than
    the fashion category, not merely differently labeled."""

    def test_low_class_peak_to_trough_ratio_is_smaller_than_high_class(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        # World.initialize's cost is dominated by SKU/customer counts, not horizon_days (no
        # per-tick simulation happens at initialize time), so widening the horizon to reach
        # every calendar month costs nothing extra here; n_customers stays tiny.
        full_year_config = _mutated(
            tiny_sim_config, lambda data: data.update(n_customers=5, horizon_days=366)
        )
        world = World.initialize(full_year_config)

        peak_month = full_year_config.seasonality.peak_month
        multipliers = full_year_config.seasonality.monthly_multipliers
        trough_month = min(range(1, 13), key=lambda month: multipliers[month - 1])
        start = full_year_config.start_date
        peak_tick = (dt.date(start.year, peak_month, 1) - start).days
        trough_tick = (dt.date(start.year, trough_month, 1) - start).days

        high_peak = world.seasonal_multiplier_for_class(peak_tick, "high")
        high_trough = world.seasonal_multiplier_for_class(trough_tick, "high")
        low_peak = world.seasonal_multiplier_for_class(peak_tick, "low")
        low_trough = world.seasonal_multiplier_for_class(trough_tick, "low")

        high_ratio = high_peak / high_trough
        low_ratio = low_peak / low_trough

        assert low_ratio < high_ratio


# ---------------------------------------------------------------------------------------
# Supporting model behavior: InventoryState, Catalog
# ---------------------------------------------------------------------------------------


class TestInventoryState:
    def test_reserve_on_zero_units_reports_unfilled_and_stays_zero(self) -> None:
        inventory = InventoryState({"sku-1": 0})
        filled = inventory.reserve("sku-1", 1)
        assert filled is False
        assert inventory.units("sku-1") == 0

    def test_reserve_never_produces_negative_count(self) -> None:
        inventory = InventoryState({"sku-1": 3})
        assert inventory.reserve("sku-1", 5) is False
        assert inventory.units("sku-1") == 3

    def test_reserve_then_release_round_trips(self) -> None:
        inventory = InventoryState({"sku-1": 5})
        assert inventory.reserve("sku-1", 2) is True
        assert inventory.units("sku-1") == 3
        inventory.release("sku-1", 2)
        assert inventory.units("sku-1") == 5

    def test_restock_increments(self) -> None:
        inventory = InventoryState({"sku-1": 5})
        inventory.restock("sku-1", 10)
        assert inventory.units("sku-1") == 15


class TestCatalogLookups:
    def test_by_sku_and_by_category_built_over_sorted_keys(self) -> None:
        skus = [
            Sku(
                sku="z-sku",
                category="cat-a",
                base_price_cents=100,
                margin_rate=0.2,
                seasonality_class="high",
            ),
            Sku(
                sku="a-sku",
                category="cat-b",
                base_price_cents=200,
                margin_rate=0.3,
                seasonality_class="low",
            ),
        ]
        catalog = Catalog.build(skus)
        assert list(catalog.by_sku) == sorted(catalog.by_sku)
        assert list(catalog.by_category) == sorted(catalog.by_category)
        assert catalog.by_sku["a-sku"].category == "cat-b"
        assert catalog.by_sku["z-sku"].category == "cat-a"


class TestCampaignValidation:
    def test_start_tick_must_be_before_end_tick(self) -> None:
        with pytest.raises(ValueError, match="start_tick"):
            Campaign(
                campaign_id="c1",
                start_tick=5,
                end_tick=5,
                category="fashion_apparel",
                channel="email",
                discount_bps=500,
            )


class TestCustomerModel:
    def test_customer_id_and_signup_tick_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError):
            Customer(customer_id=-1, traits=None, signup_tick=0)  # type: ignore[arg-type]
