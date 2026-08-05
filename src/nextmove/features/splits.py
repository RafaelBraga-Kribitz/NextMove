"""Time-aware split helper with a half-open boundary and a deterministic tiebreak (FEAT-02,
locked AD-16 / proposed TD-09).

QUALITY_BAR names leakage-tolerant evaluation as prohibited anti-pattern 7: random splits on
behavioral data are the canonical corpus mistake this module exists to make structurally
impossible. `time_aware_split` is the **only** split entry point this package exposes -- there
is no shuffle parameter, no random-state parameter, and no proportion-based ("80/20") entry
point anywhere in this module, so a caller who wants a random partition over behavioural time
must add a new function and justify it in review, not flip a flag on this one.

**Boundary rule (correcting a self-contradiction in this plan's own `<action>` text).** The
plan's action text describes the boundary in two ways: "a snapshot whose `as_of_ts` is strictly
less than `boundary_ts` goes to train, and one greater than or equal to it goes to test" (which
puts an exact match in *test*), immediately followed by "a snapshot landing exactly on the
boundary therefore belongs to the earlier, training side" (which puts it in *train*). Those two
sentences cannot both be true. This module follows the plan's `must_haves.truths` and
acceptance criteria instead, which are unambiguous and mutually consistent: **`as_of_ts <=
boundary_ts` is train, `as_of_ts > boundary_ts` is test.** Documented as a deviation in this
plan's SUMMARY.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["RandomSplitRefused", "SplitResult", "time_aware_split"]


class RandomSplitRefused(Exception):
    """Raised by a future adapter that is offered a shuffle/random-state argument and refuses
    to honour it. Not raised by anything in this module today -- `time_aware_split` exposes no
    such argument to refuse -- but declared here so a future caller has a named exception to
    raise explicitly rather than quietly accepting a random split."""


@dataclass(frozen=True)
class SplitResult:
    """The outcome of `time_aware_split`: two partitions of the input snapshots plus the
    boundary they were split on and, for the two edge cases that produce no partitions at all,
    a stated `reason` rather than a silent empty result."""

    train: tuple[Mapping[str, Any], ...]
    test: tuple[Mapping[str, Any], ...]
    boundary_ts: Any
    reason: str | None


def time_aware_split(
    snapshots: Sequence[Mapping[str, Any]],
    boundary_ts: Any,
) -> SplitResult:
    """Partition `snapshots` on `as_of_ts` against `boundary_ts`, half-open: `as_of_ts <=
    boundary_ts` lands in `train`, `as_of_ts > boundary_ts` lands in `test` -- an exact match
    on the boundary belongs to the earlier, training side (see module docstring for why this
    is `<=`/`>` rather than the plan's self-contradictory `<`/`>=` prose).

    `snapshots` is sorted by `(as_of_ts, customer_id)` before partitioning, so two callers
    handing in the same snapshots in different input orders produce identical `train`/`test`
    membership and ordering -- ties on `as_of_ts` resolve by `customer_id`, deterministically,
    rather than by whatever order the caller happened to supply.

    An empty `snapshots`, or one whose members all share a single distinct `as_of_ts` (a split
    needs at least two distinct timestamps to mean anything), returns empty `train`/`test`
    tuples with a populated `reason` string -- never raises, and never silently falls back to
    any other partitioning strategy.
    """
    if not snapshots:
        return SplitResult(
            train=(), test=(), boundary_ts=boundary_ts, reason="no snapshots supplied"
        )

    ordered = tuple(
        sorted(snapshots, key=lambda snapshot: (snapshot["as_of_ts"], snapshot["customer_id"]))
    )
    distinct_timestamps = {snapshot["as_of_ts"] for snapshot in ordered}
    if len(distinct_timestamps) < 2:
        return SplitResult(
            train=(),
            test=(),
            boundary_ts=boundary_ts,
            reason=(
                "all snapshots share a single as_of_ts "
                f"({next(iter(distinct_timestamps))!r}); a time-aware split needs at least two "
                "distinct timestamps to partition on"
            ),
        )

    train = tuple(snapshot for snapshot in ordered if snapshot["as_of_ts"] <= boundary_ts)
    test = tuple(snapshot for snapshot in ordered if snapshot["as_of_ts"] > boundary_ts)
    return SplitResult(train=train, test=test, boundary_ts=boundary_ts, reason=None)
