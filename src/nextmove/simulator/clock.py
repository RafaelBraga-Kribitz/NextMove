"""The simulator's only time axis: a virtual clock driven by config, never the host clock.

`SimClock` derives every timestamp from `start_date` plus a tick index (D-07: the world
advances in daily ticks). Nothing in `nextmove.simulator` may read the host's wall clock
(`datetime.now`, `datetime.utcnow`, `time.time`, ...): a wall-clock reading would make two
runs of the same config differ, which breaks ENG-04's byte-identical-rerun claim, DATA-03's
monotonicity gate, and the ASOF joins plan 01-10 builds on top of this clock's output
(RESEARCH Pitfall 1 — naive/wall-clock timestamps are a documented, easy-to-miss
nondeterminism source).

Every timestamp `SimClock` returns is timezone-aware UTC. A naive timestamp anywhere
downstream would make a naive/aware comparison possible mid-pipeline, which is exactly the
failure mode `nextmove.ingest.contracts.Event` rejects at its own boundary — this clock never
produces the naive value in the first place.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

#: Seconds in one simulated day; `intraday` offsets are measured against this.
_SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class SimClock:
    """Maps a tick index in the half-open range `[0, horizon_days)` to a UTC timestamp.

    `start_date + tick days` at midnight UTC is tick `tick`'s timestamp. The range is
    half-open — `horizon_days` itself is one tick past the end of the simulated horizon — so
    `timestamp_for_tick(horizon_days)` raises rather than silently returning a timestamp one
    day past what the world actually simulated.
    """

    start_date: date
    horizon_days: int

    def __post_init__(self) -> None:
        if self.horizon_days <= 0:
            raise ValueError(f"horizon_days must be positive, got {self.horizon_days}")

    def timestamp_for_tick(self, tick: int) -> datetime:
        """Midnight UTC of `start_date + tick days`.

        Raises `IndexError` naming the offending tick when `tick` falls outside the half-open
        range `[0, horizon_days)`.
        """
        if not 0 <= tick < self.horizon_days:
            raise IndexError(
                f"tick {tick} is out of range for horizon_days={self.horizon_days}; valid "
                f"ticks are 0..{self.horizon_days - 1} inclusive"
            )
        day = self.start_date + timedelta(days=tick)
        return datetime(day.year, day.month, day.day, tzinfo=UTC)

    def intraday(self, tick: int, seconds_offset: float) -> datetime:
        """A UTC timestamp strictly inside `tick`'s day: midnight plus `seconds_offset`.

        `seconds_offset` must be strictly between 0 and 86400 (one day) so the result can
        never land exactly on `tick`'s midnight or spill into the following tick's day.
        """
        if not 0 < seconds_offset < _SECONDS_PER_DAY:
            raise ValueError(
                "seconds_offset must be strictly between 0 and 86400 (one day), got "
                f"{seconds_offset}"
            )
        return self.timestamp_for_tick(tick) + timedelta(seconds=seconds_offset)

    def ticks(self) -> Iterator[tuple[int, datetime]]:
        """Yield `(tick, timestamp)` for every tick in `[0, horizon_days)`, strictly
        increasing timestamps in ascending tick order."""
        for tick in range(self.horizon_days):
            yield tick, self.timestamp_for_tick(tick)
