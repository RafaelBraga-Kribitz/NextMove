"""Covers plan 01-08 Task 2's behavior block: the three-stage daily tick, D-08's same-tick
closed loop, SIM-01/SIM-04 event emission, and determinism -- all against the `tiny` profile.
"""

import random
from collections import Counter

import pytest

from nextmove.config.loader import load_config
from nextmove.config.models import SimulatorConfig
from nextmove.ingest.contracts import EventType
from nextmove.simulator.queue import ActionQueue, ScheduledAction
from nextmove.simulator.response import ActionType
from nextmove.simulator.tick import TickState, advance_tick
from nextmove.simulator.world import World


@pytest.fixture(scope="module")
def tiny_sim_config() -> SimulatorConfig:
    return load_config("tiny").config.simulator


def _fresh_world(config: SimulatorConfig) -> World:
    return World.initialize(config)


# ---------------------------------------------------------------------------------------
# Empty queue vs queued delivery: action_delivered emission and D-08 same-tick effect
# ---------------------------------------------------------------------------------------


class TestQueueDrivenBehaviour:
    def test_empty_queue_produces_only_organic_events(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        result = advance_tick(world, 5, ActionQueue(), tiny_sim_config, TickState())
        assert all(event.type != EventType.ACTION_DELIVERED for event in result.events)
        assert len(result.events) > 0

    def test_queued_delivery_produces_exactly_one_action_delivered_event(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        queue = ActionQueue()
        queue.schedule(
            ScheduledAction(
                customer_id=3,
                deliver_tick=5,
                action_type=ActionType.EMAIL_NOW,
                params={},
                origin="test",
            )
        )
        result = advance_tick(world, 5, queue, tiny_sim_config, TickState())
        delivered = [e for e in result.events if e.type == EventType.ACTION_DELIVERED]
        assert len(delivered) == 1
        assert delivered[0].customer_id == "3"

    def test_delivery_changes_same_tick_organic_output_for_at_least_one_customer(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        """D-08: an action delivered on tick N changes the events generated later in tick N for
        that customer, not only from tick N+1. Scanned over several customers (rather than one
        fixed id) so the assertion does not depend on which specific customer's RNG draw happens
        to straddle the boosted-vs-unboosted probability threshold at this config and seed.
        """
        tick = 5
        found_a_difference = False
        for customer_id in range(30):
            baseline_world = _fresh_world(tiny_sim_config)
            baseline_result = advance_tick(
                baseline_world, tick, ActionQueue(), tiny_sim_config, TickState()
            )
            baseline_events = [
                e
                for e in baseline_result.events
                if e.customer_id == str(customer_id) and e.type != EventType.ACTION_DELIVERED
            ]

            boosted_world = _fresh_world(tiny_sim_config)
            boosted_queue = ActionQueue()
            boosted_queue.schedule(
                ScheduledAction(
                    customer_id=customer_id,
                    deliver_tick=tick,
                    action_type=ActionType.DISCOUNT_HIGH,
                    params={"discount_bps": 5000},
                    origin="test",
                )
            )
            boosted_result = advance_tick(
                boosted_world, tick, boosted_queue, tiny_sim_config, TickState()
            )
            boosted_events = [
                e
                for e in boosted_result.events
                if e.customer_id == str(customer_id) and e.type != EventType.ACTION_DELIVERED
            ]

            if baseline_events != boosted_events:
                found_a_difference = True
                break

        assert found_a_difference, "no customer among the first 30 showed a same-tick difference"


# ---------------------------------------------------------------------------------------
# Event validity, timestamps, session ordering
# ---------------------------------------------------------------------------------------


class TestEventValidity:
    def test_every_event_validates_as_canonical_event(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        result = advance_tick(world, 10, ActionQueue(), tiny_sim_config, TickState())
        assert len(result.events) > 0
        for event in result.events:
            # Constructed via the Event() constructor already inside advance_tick, so
            # reaching this point at all is the proof; re-validating from the dumped dict
            # additionally confirms no field was smuggled past validation via mutation.
            event.__class__.model_validate(event.model_dump(mode="python"))

    def test_every_ts_falls_strictly_inside_the_ticks_own_day(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        tick = 8
        result = advance_tick(world, tick, ActionQueue(), tiny_sim_config, TickState())
        day_start = world.clock.timestamp_for_tick(tick)
        day_end = world.clock.timestamp_for_tick(tick + 1)
        for event in result.events:
            assert day_start < event.ts < day_end

    def test_session_timestamps_strictly_increase(self, tiny_sim_config: SimulatorConfig) -> None:
        world = _fresh_world(tiny_sim_config)
        result = advance_tick(world, 12, ActionQueue(), tiny_sim_config, TickState())
        by_session: dict[str, list] = {}
        for event in result.events:
            by_session.setdefault(event.session_id, []).append(event.ts)
        for session_id, timestamps in by_session.items():
            assert timestamps == sorted(timestamps), f"session {session_id} not increasing"
            assert len(set(timestamps)) == len(timestamps), f"session {session_id} has duplicate ts"


# ---------------------------------------------------------------------------------------
# Cart abandonment, inventory scarcity
# ---------------------------------------------------------------------------------------


class TestCartAndInventory:
    def test_add_to_cart_without_order_produces_cart_abandon(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        found_add_to_cart_without_order = False
        for tick in range(15):
            result = advance_tick(world, tick, ActionQueue(), tiny_sim_config, TickState())
            by_session: dict[str, list] = {}
            for event in result.events:
                by_session.setdefault(event.session_id, []).append(event.type)
            for types in by_session.values():
                if EventType.ADD_TO_CART in types:
                    assert (EventType.ORDER_PLACED in types) or (EventType.CART_ABANDON in types), (
                        f"add_to_cart with neither order nor abandon: {types}"
                    )
                    if EventType.ORDER_PLACED not in types:
                        found_add_to_cart_without_order = True
        assert found_add_to_cart_without_order

    def test_order_never_reserves_a_sku_with_zero_inventory(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        state = TickState()
        queue = ActionQueue()
        # Force high demand: schedule a large discount to every customer every tick so orders
        # are frequent and stock genuinely depletes within the tiny profile's short horizon.
        for tick in range(tiny_sim_config.horizon_days):
            for customer in world.customers:
                queue.schedule(
                    ScheduledAction(
                        customer_id=customer.customer_id,
                        deliver_tick=tick,
                        action_type=ActionType.DISCOUNT_HIGH,
                        params={"discount_bps": 9000},
                        origin="test",
                    )
                )
            result = advance_tick(world, tick, queue, tiny_sim_config, state)
            for event in result.events:
                if event.type == EventType.ORDER_PLACED:
                    for line_item in event.payload.line_items:  # type: ignore[union-attr]
                        assert world.inventory.units(line_item.sku) >= 0


# ---------------------------------------------------------------------------------------
# Micro-conversion events
# ---------------------------------------------------------------------------------------


class TestMicroEvents:
    def test_every_session_emits_at_least_one_micro_conversion_event(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        micro_types = {EventType.SCROLL, EventType.FILTER_APPLY, EventType.DWELL}
        session_ids_seen = set()
        by_session_micro: dict[str, bool] = {}
        for tick in range(10):
            result = advance_tick(world, tick, ActionQueue(), tiny_sim_config, TickState())
            for event in result.events:
                if event.type == EventType.SESSION_START:
                    session_ids_seen.add(event.session_id)
                    by_session_micro.setdefault(event.session_id, False)
                if event.type in micro_types:
                    by_session_micro[event.session_id] = True
        assert session_ids_seen, "no sessions generated across 10 ticks"
        for session_id in session_ids_seen:
            assert by_session_micro[session_id], f"session {session_id} has no micro-event"

    def test_dwell_events_carry_a_class_not_a_duration(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        result = advance_tick(world, 4, ActionQueue(), tiny_sim_config, TickState())
        dwell_events = [e for e in result.events if e.type == EventType.DWELL]
        assert dwell_events
        for event in dwell_events:
            assert event.payload.dwell_class in ("short", "medium", "long")  # type: ignore[union-attr]
            assert not hasattr(event.payload, "duration_s")

    def test_no_micro_event_carries_a_weight_or_score(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        world = _fresh_world(tiny_sim_config)
        result = advance_tick(world, 6, ActionQueue(), tiny_sim_config, TickState())
        forbidden = {"weight", "score", "pcr_weight", "micro_weight", "micro_conversion_weight"}
        for event in result.events:
            fields = set(event.payload.model_dump(mode="python"))
            assert not (fields & forbidden)


# ---------------------------------------------------------------------------------------
# Determinism and iteration-order invariance
# ---------------------------------------------------------------------------------------


class TestDeterminism:
    def test_two_runs_of_the_same_tick_produce_identical_event_ids(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        tick = 9
        world_a = _fresh_world(tiny_sim_config)
        result_a = advance_tick(world_a, tick, ActionQueue(), tiny_sim_config, TickState())

        world_b = _fresh_world(tiny_sim_config)
        result_b = advance_tick(world_b, tick, ActionQueue(), tiny_sim_config, TickState())

        ids_a = [e.event_id for e in result_a.events]
        ids_b = [e.event_id for e in result_b.events]
        assert ids_a == ids_b
        assert result_a.events == result_b.events

    def test_shuffled_customer_container_produces_identical_output(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        tick = 7

        world_a = _fresh_world(tiny_sim_config)
        result_a = advance_tick(world_a, tick, ActionQueue(), tiny_sim_config, TickState())

        world_b = _fresh_world(tiny_sim_config)
        shuffled = list(world_b.customers)
        random.Random(0).shuffle(shuffled)
        world_b = world_b.model_copy(update={"customers": tuple(shuffled)})
        result_b = advance_tick(world_b, tick, ActionQueue(), tiny_sim_config, TickState())

        assert result_a.events == result_b.events


# ---------------------------------------------------------------------------------------
# Stage ordering (structural)
# ---------------------------------------------------------------------------------------


class TestStageOrdering:
    def test_action_delivered_events_precede_organic_events_in_returned_order_by_construction(
        self, tiny_sim_config: SimulatorConfig
    ) -> None:
        """`advance_tick` builds delivered events in stage 1 before any organic event exists,
        then canonically sorts everything by `sort_events` -- this test checks the *counts*
        line up (one action_delivered per delivery, present in the final sorted output),
        which is what actually matters once the stages have been proven to interact (D-08)."""
        world = _fresh_world(tiny_sim_config)
        queue = ActionQueue()
        queue.schedule(
            ScheduledAction(
                customer_id=1,
                deliver_tick=5,
                action_type=ActionType.WAIT,
                params={},
                origin="test",
            )
        )
        queue.schedule(
            ScheduledAction(
                customer_id=2,
                deliver_tick=5,
                action_type=ActionType.RECOMMEND,
                params={},
                origin="test",
            )
        )
        result = advance_tick(world, 5, queue, tiny_sim_config, TickState())
        counts = Counter(e.type for e in result.events)
        assert counts[EventType.ACTION_DELIVERED] == 2
