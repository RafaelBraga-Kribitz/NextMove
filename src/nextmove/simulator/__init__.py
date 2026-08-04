"""Generative world simulator: customers, catalog, inventory, campaigns, daily-tick clock,
and latent-trait-driven action-response functions.

Import-isolated (SIM-02): must never be imported by models/, decisions/, policies/, or
features/. Populated starting Phase 1.
"""

from nextmove.simulator.clock import SimClock
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
from nextmove.simulator.rng import SeedDomain, entity_rng, stream_rng
from nextmove.simulator.tick import TickResult, TickState, advance_tick
from nextmove.simulator.traits import LatentTraits, sample_latent_traits
from nextmove.simulator.world import (
    Campaign,
    Catalog,
    Customer,
    InventoryState,
    Sku,
    World,
)

__all__: list[str] = [
    "ActionQueue",
    "ActionType",
    "Campaign",
    "Catalog",
    "Customer",
    "InventoryState",
    "LatentTraits",
    "ResponseContext",
    "ScheduledAction",
    "SeedDomain",
    "SimClock",
    "Sku",
    "TickResult",
    "TickState",
    "World",
    "advance_tick",
    "apply_discount_cents",
    "base_conversion_probability",
    "entity_rng",
    "fatigue_penalty",
    "ground_truth_uplift",
    "response_multiplier",
    "sample_latent_traits",
    "stream_rng",
]
