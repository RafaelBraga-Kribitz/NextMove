"""Covers every `must_haves.truths` / behavior-block item for D-03's action-response functions,
D-04's fatigue loophole, and the `ActionQueue` D-07 stage 1 relies on (plan 01-08 Task 1).
"""

import pytest

from nextmove.config.loader import load_config
from nextmove.config.models import SimulatorConfig
from nextmove.simulator.queue import ActionQueue, ScheduledAction
from nextmove.simulator.response import (
    ActionType,
    ResponseContext,
    apply_discount_cents,
    base_conversion_probability,
    fatigue_penalty,
    ground_truth_uplift,
    response_multiplier,
)
from nextmove.simulator.traits import LatentTraits


@pytest.fixture(scope="module")
def tiny_sim_config() -> SimulatorConfig:
    return load_config("tiny").config.simulator


def _traits(
    price_sensitivity: float = 0.3,
    loyalty: float = 0.3,
    fatigue_propensity: float = 0.5,
    category_affinity: dict[str, float] | None = None,
) -> LatentTraits:
    if category_affinity is None:
        category_affinity = {"fashion_apparel": 0.5, "home_basics": 0.5}
    return LatentTraits(
        price_sensitivity=price_sensitivity,
        loyalty=loyalty,
        fatigue_propensity=fatigue_propensity,
        category_affinity=category_affinity,
    )


def _context(
    category: str = "fashion_apparel",
    inventory_units: int = 200,
    low_stock_threshold: int = 20,
    seasonal_multiplier: float = 1.0,
    fatigue_counter: int = 0,
) -> ResponseContext:
    return ResponseContext(
        category=category,
        inventory_units=inventory_units,
        low_stock_threshold=low_stock_threshold,
        seasonal_multiplier=seasonal_multiplier,
        fatigue_counter=fatigue_counter,
    )


def _disable_loophole(config: SimulatorConfig) -> SimulatorConfig:
    data = config.model_dump(mode="python")
    data["loophole"]["fatigue_penalty_enabled"] = False
    return SimulatorConfig.model_validate(data)


# ---------------------------------------------------------------------------------------
# response_multiplier(none) / ground_truth_uplift(none)
# ---------------------------------------------------------------------------------------


class TestNoneAction:
    def test_response_multiplier_none_is_exactly_one(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        traits = _traits()
        context = _context()
        assert response_multiplier(traits, ActionType.NONE, {}, context, tiny_sim_config) == 1.0

    def test_ground_truth_uplift_none_is_exactly_zero(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        traits = _traits()
        context = _context()
        assert ground_truth_uplift(traits, ActionType.NONE, {}, context, tiny_sim_config) == 0.0


# ---------------------------------------------------------------------------------------
# Monotonicity: price sensitivity (discount) and loyalty (recommend)
# ---------------------------------------------------------------------------------------


class TestMonotonicity:
    def test_high_price_sensitivity_beats_low_on_discount_action(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        context = _context()
        params = {"discount_bps": 1500}
        low = _traits(price_sensitivity=0.05)
        high = _traits(price_sensitivity=0.95)

        low_multiplier = response_multiplier(
            low, ActionType.DISCOUNT_HIGH, params, context, tiny_sim_config
        )
        high_multiplier = response_multiplier(
            high, ActionType.DISCOUNT_HIGH, params, context, tiny_sim_config
        )
        assert high_multiplier > low_multiplier

    def test_high_loyalty_beats_low_on_recommend_action(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        context = _context()
        low = _traits(loyalty=0.05)
        high = _traits(loyalty=0.95)

        low_multiplier = response_multiplier(
            low, ActionType.RECOMMEND, {}, context, tiny_sim_config
        )
        high_multiplier = response_multiplier(
            high, ActionType.RECOMMEND, {}, context, tiny_sim_config
        )
        assert high_multiplier > low_multiplier


# ---------------------------------------------------------------------------------------
# Fatigue penalty and the D-04 loophole
# ---------------------------------------------------------------------------------------


class TestFatiguePenalty:
    def test_accumulated_fatigue_strictly_reduces_multiplier_when_enabled(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        assert tiny_sim_config.loophole.fatigue_penalty_enabled is True
        traits = _traits()
        low_fatigue_context = _context(fatigue_counter=0)
        high_fatigue_context = _context(fatigue_counter=50)

        low = response_multiplier(
            traits, ActionType.EMAIL_NOW, {}, low_fatigue_context, tiny_sim_config
        )
        high = response_multiplier(
            traits, ActionType.EMAIL_NOW, {}, high_fatigue_context, tiny_sim_config
        )
        assert high < low

    def test_fatigue_penalty_disabled_makes_response_invariant_to_fatigue_counter(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        disabled_config = _disable_loophole(tiny_sim_config)
        traits = _traits()

        multiplier_at_0 = response_multiplier(
            traits, ActionType.EMAIL_NOW, {}, _context(fatigue_counter=0), disabled_config
        )
        multiplier_at_50 = response_multiplier(
            traits, ActionType.EMAIL_NOW, {}, _context(fatigue_counter=50), disabled_config
        )
        assert multiplier_at_0 == multiplier_at_50

    def test_fatigue_penalty_disabled_returns_exactly_one(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        disabled_config = _disable_loophole(tiny_sim_config)
        traits = _traits()
        assert fatigue_penalty(traits, 0, disabled_config) == 1.0
        assert fatigue_penalty(traits, 50, disabled_config) == 1.0

    def test_fatigue_penalty_docstring_names_the_loophole(self) -> None:
        assert "loophole" in (fatigue_penalty.__doc__ or "")

    def test_response_multiplier_docstring_states_combining_formula(self) -> None:
        doc = response_multiplier.__doc__ or ""
        assert "combining formula" in doc.lower()


# ---------------------------------------------------------------------------------------
# ground_truth_uplift: determinism and shape
# ---------------------------------------------------------------------------------------


class TestGroundTruthUplift:
    def test_deterministic_for_fixed_inputs(self, tiny_sim_config: SimulatorConfig) -> None:
        traits = _traits()
        context = _context()
        params = {"discount_bps": 1000}
        first = ground_truth_uplift(
            traits, ActionType.DISCOUNT_LOW, params, context, tiny_sim_config
        )
        second = ground_truth_uplift(
            traits, ActionType.DISCOUNT_LOW, params, context, tiny_sim_config
        )
        assert first == second

    def test_matches_p_convert_with_action_minus_p_convert_with_none(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        traits = _traits()
        context = _context()
        params = {"discount_bps": 1000}
        base = base_conversion_probability(traits, context, tiny_sim_config)
        action_multiplier = response_multiplier(
            traits, ActionType.DISCOUNT_LOW, params, context, tiny_sim_config
        )
        none_multiplier = response_multiplier(traits, ActionType.NONE, {}, context, tiny_sim_config)
        expected = min(max(base * action_multiplier, 0.0), 1.0) - min(
            max(base * none_multiplier, 0.0), 1.0
        )
        actual = ground_truth_uplift(
            traits, ActionType.DISCOUNT_LOW, params, context, tiny_sim_config
        )
        assert actual == pytest.approx(expected)


# ---------------------------------------------------------------------------------------
# apply_discount_cents: half-to-even rounding
# ---------------------------------------------------------------------------------------


class TestApplyDiscountCents:
    def test_half_cent_boundary_rounds_down_to_even(self) -> None:
        # 200 cents * 125 bps / 10000 = 2.5 exactly -> rounds to 2 (nearest even).
        assert apply_discount_cents(200, 125) == 2

    def test_half_cent_boundary_rounds_up_to_even(self) -> None:
        # 600 cents * 125 bps / 10000 = 7.5 exactly -> rounds to 8 (nearest even).
        assert apply_discount_cents(600, 125) == 8

    def test_returns_int(self) -> None:
        result = apply_discount_cents(1999, 750)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------------------
# ActionQueue
# ---------------------------------------------------------------------------------------


class TestActionQueue:
    def _action(
        self, customer_id: int, deliver_tick: int, action_type: ActionType
    ) -> ScheduledAction:
        return ScheduledAction(
            customer_id=customer_id,
            deliver_tick=deliver_tick,
            action_type=action_type,
            params={},
            origin="test",
        )

    def test_drain_returns_only_actions_due_at_or_before_tick(self) -> None:
        queue = ActionQueue()
        queue.schedule(self._action(1, 3, ActionType.EMAIL_NOW))
        queue.schedule(self._action(2, 7, ActionType.RECOMMEND))

        drained = queue.drain(5)
        assert [a.customer_id for a in drained] == [1]
        assert queue.pending_count == 1

        later = queue.drain(7)
        assert [a.customer_id for a in later] == [2]
        assert queue.pending_count == 0

    def test_drain_order_is_deterministic_for_actions_sharing_a_tick(self) -> None:
        queue = ActionQueue()
        queue.schedule(self._action(3, 5, ActionType.RECOMMEND))
        queue.schedule(self._action(1, 5, ActionType.BUNDLE))
        queue.schedule(self._action(2, 5, ActionType.EMAIL_NOW))

        drained = queue.drain(5)
        assert [a.customer_id for a in drained] == [1, 2, 3]

    def test_drain_order_independent_of_schedule_order(self) -> None:
        queue_a = ActionQueue()
        queue_a.schedule(self._action(3, 5, ActionType.RECOMMEND))
        queue_a.schedule(self._action(1, 5, ActionType.BUNDLE))

        queue_b = ActionQueue()
        queue_b.schedule(self._action(1, 5, ActionType.BUNDLE))
        queue_b.schedule(self._action(3, 5, ActionType.RECOMMEND))

        assert queue_a.drain(5) == queue_b.drain(5)
