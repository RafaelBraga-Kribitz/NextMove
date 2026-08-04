"""Proves the simulator's reproducibility claim mechanically rather than by inspection:
per-entity draws are equal across processes, visit orders, and population sizes, and the
virtual clock never touches the host clock (SIM-01, ENG-04, RESEARCH Pattern 1 / Pitfall 1).
"""

import datetime as dt
import random

import numpy as np
import pytest

from nextmove.config.models import SeedsConfig
from nextmove.simulator.clock import SimClock
from nextmove.simulator.rng import SeedDomain, entity_rng, stream_rng

SEEDS = SeedsConfig(world=1, organic=2, response=3, campaign=4)


def _draw_traits_like_sequence(entity_id: int, seeds: SeedsConfig) -> tuple[float, ...]:
    """Draw a fixed-shape sequence of values the way trait sampling will: one `Generator`
    per entity, several draws in a fixed order."""
    rng = entity_rng(SeedDomain.world, entity_id, seeds)
    return (
        float(rng.beta(2.0, 5.0)),
        float(rng.beta(2.5, 4.0)),
        float(rng.lognormal(-1.2, 0.6)),
        float(rng.normal(0.0, 1.0)),
    )


class TestEntityRngDeterminism:
    def test_same_domain_entity_seed_reproduces_identical_draws(self) -> None:
        rng1 = entity_rng(SeedDomain.world, 42, SEEDS)
        rng2 = entity_rng(SeedDomain.world, 42, SEEDS)
        assert rng1.random(10).tolist() == rng2.random(10).tolist()

    def test_different_entity_ids_diverge(self) -> None:
        rng_a = entity_rng(SeedDomain.world, 1, SEEDS)
        rng_b = entity_rng(SeedDomain.world, 2, SEEDS)
        assert rng_a.random(10).tolist() != rng_b.random(10).tolist()

    def test_same_entity_different_domain_diverges(self) -> None:
        rng_world = entity_rng(SeedDomain.world, 7, SEEDS)
        rng_organic = entity_rng(SeedDomain.organic, 7, SEEDS)
        assert rng_world.random(10).tolist() != rng_organic.random(10).tolist()

    def test_order_independence_ascending_descending_shuffled(self) -> None:
        """A fixed customer's draws are identical no matter what order the population is
        visited in — the mechanical statement of RESEARCH Pattern 1's anti-pattern warning."""
        target_id = 500
        population = list(range(1000))

        ascending = list(population)
        descending = list(reversed(population))
        shuffled = list(population)
        random.Random(12345).shuffle(shuffled)

        def draws_for_target(visit_order: list[int]) -> tuple[float, ...]:
            result: tuple[float, ...] | None = None
            for entity_id in visit_order:
                draws = _draw_traits_like_sequence(entity_id, SEEDS)
                if entity_id == target_id:
                    result = draws
            assert result is not None
            return result

        draws_ascending = draws_for_target(ascending)
        draws_descending = draws_for_target(descending)
        draws_shuffled = draws_for_target(shuffled)

        assert draws_ascending == draws_descending == draws_shuffled

    def test_population_independence_small_and_large_world(self) -> None:
        """A fixed customer's draws are identical whether the population around them has 100
        members or 50000 — nothing about a customer's stream depends on population size.

        Draw customer 500's sequence in isolation, then again after generating every other
        customer in a 100-member world and, separately, every other customer in a
        50000-member world. If population size leaked into the entropy (e.g. via a shared
        global generator, or via `n_customers` folded into the seed), one of these would
        diverge from the isolated draw.
        """
        target_id = 500

        isolated_draws = _draw_traits_like_sequence(target_id, SEEDS)

        for entity_id in range(100):
            if entity_id != target_id:
                _draw_traits_like_sequence(entity_id, SEEDS)
        draws_in_small_world = _draw_traits_like_sequence(target_id, SEEDS)

        for entity_id in range(50_000):
            if entity_id != target_id:
                _draw_traits_like_sequence(entity_id, SEEDS)
        draws_in_large_world = _draw_traits_like_sequence(target_id, SEEDS)

        assert isolated_draws == draws_in_small_world == draws_in_large_world

    def test_no_legacy_numpy_global_rng_usage(self) -> None:
        """Mechanical proxy for the acceptance criterion `grep`: `entity_rng`/`stream_rng`
        never touch `np.random.seed` or the module-level legacy draw functions."""
        import inspect

        import nextmove.simulator.rng as rng_module

        source = inspect.getsource(rng_module)
        assert "np.random.seed" not in source
        assert "np.random.rand(" not in source
        assert "np.random.choice(" not in source
        assert "default_rng" in source

    def test_no_stdlib_random_import_in_rng_module(self) -> None:
        import inspect

        import nextmove.simulator.rng as rng_module

        source = inspect.getsource(rng_module)
        assert "import random" not in source


class TestStreamRng:
    def test_stream_rng_reproducible(self) -> None:
        rng1 = stream_rng(SeedDomain.response, 10, 3, SEEDS)
        rng2 = stream_rng(SeedDomain.response, 10, 3, SEEDS)
        assert rng1.random(5).tolist() == rng2.random(5).tolist()

    def test_stream_rng_diverges_across_ticks(self) -> None:
        rng_tick3 = stream_rng(SeedDomain.response, 10, 3, SEEDS)
        rng_tick4 = stream_rng(SeedDomain.response, 10, 4, SEEDS)
        assert rng_tick3.random(5).tolist() != rng_tick4.random(5).tolist()


class TestGeneratorType:
    def test_entity_rng_returns_numpy_generator(self) -> None:
        assert isinstance(entity_rng(SeedDomain.world, 1, SEEDS), np.random.Generator)


class TestSimClock:
    def test_tick_zero_is_start_date_midnight_utc(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        ts = clock.timestamp_for_tick(0)
        assert ts.tzinfo is not None
        assert ts.utcoffset() == dt.timedelta(0)
        assert (ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second) == (
            2024,
            1,
            1,
            0,
            0,
            0,
        )

    def test_horizon_days_tick_raises_indexerror(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        with pytest.raises(IndexError):
            clock.timestamp_for_tick(10)

    def test_horizon_days_minus_one_succeeds(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        ts = clock.timestamp_for_tick(9)
        assert ts == dt.datetime(2024, 1, 10, tzinfo=dt.UTC)

    def test_negative_tick_raises_indexerror(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        with pytest.raises(IndexError):
            clock.timestamp_for_tick(-1)

    def test_intraday_strictly_inside_tick_day(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        ts = clock.intraday(0, seconds_offset=3600)
        day_start = clock.timestamp_for_tick(0)
        day_end = day_start + dt.timedelta(days=1)
        assert day_start < ts < day_end
        assert ts.tzinfo is not None
        assert ts.utcoffset() == dt.timedelta(0)

    def test_intraday_rejects_offset_outside_day(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        with pytest.raises(ValueError, match="seconds_offset"):
            clock.intraday(0, seconds_offset=86_400)
        with pytest.raises(ValueError, match="seconds_offset"):
            clock.intraday(0, seconds_offset=0)
        with pytest.raises(ValueError, match="seconds_offset"):
            clock.intraday(0, seconds_offset=-1)

    def test_ticks_yields_exactly_horizon_days_strictly_increasing(self) -> None:
        clock = SimClock(dt.date(2024, 1, 1), 10)
        pairs = list(clock.ticks())
        assert len(pairs) == 10
        timestamps = [ts for _tick, ts in pairs]
        assert timestamps == sorted(timestamps)
        assert len(set(timestamps)) == len(timestamps)
        assert [tick for tick, _ts in pairs] == list(range(10))

    def test_horizon_days_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="horizon_days"):
            SimClock(dt.date(2024, 1, 1), 0)
