"""D-07 stage 1: the scheduled action-delivery queue every daily tick drains before applying
any response function.

Phase 1 constructs an `ActionQueue` empty -- pure organic history, per D-07. Phase 3's policy
replay is its first real producer, filling it with the actions a learned or rule-based policy
decides to deliver. Nothing about this class may assume it stays empty: `drain` must behave
identically whether it is draining zero deliveries or thousands.
"""

from pydantic import BaseModel, ConfigDict, Field

from nextmove.simulator.response import ActionType


class ScheduledAction(BaseModel):
    """One action scheduled for delivery at `deliver_tick`. `origin` names what scheduled it
    (e.g. a policy id) so a delivery's provenance survives into the queue even before Phase 3
    exists to populate it with anything but test fixtures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: int = Field(ge=0)
    deliver_tick: int = Field(ge=0)
    action_type: ActionType
    params: dict[str, str | int]
    origin: str = Field(min_length=1)


class ActionQueue:
    """Mutable queue of scheduled action deliveries, drained tick by tick.

    Deliberately not a frozen Pydantic model: like `nextmove.simulator.world.InventoryState`,
    this is world state a running simulation mutates over time, not a value fixed at
    construction.
    """

    def __init__(self) -> None:
        self._pending: list[ScheduledAction] = []

    def schedule(self, action: ScheduledAction) -> None:
        """Enqueue `action` for later delivery."""
        self._pending.append(action)

    def drain(self, tick: int) -> list[ScheduledAction]:
        """Remove and return every action whose `deliver_tick` is at or before `tick`, sorted
        by `(deliver_tick, customer_id, action_type)` so ties resolve identically on every run.
        Actions scheduled for a later tick remain queued.
        """
        due = [action for action in self._pending if action.deliver_tick <= tick]
        self._pending = [action for action in self._pending if action.deliver_tick > tick]
        due.sort(
            key=lambda action: (action.deliver_tick, action.customer_id, action.action_type.value)
        )
        return due

    @property
    def pending_count(self) -> int:
        """Number of actions still queued (not yet drained)."""
        return len(self._pending)
