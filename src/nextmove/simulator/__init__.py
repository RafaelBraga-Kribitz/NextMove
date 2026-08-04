"""Generative world simulator: customers, catalog, inventory, campaigns, daily-tick clock,
and latent-trait-driven action-response functions.

Import-isolated (SIM-02): must never be imported by models/, decisions/, policies/, or
features/. Populated starting Phase 1.
"""

from nextmove.simulator.clock import SimClock
from nextmove.simulator.rng import SeedDomain, entity_rng, stream_rng
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
    "Campaign",
    "Catalog",
    "Customer",
    "InventoryState",
    "LatentTraits",
    "SeedDomain",
    "SimClock",
    "Sku",
    "World",
    "entity_rng",
    "sample_latent_traits",
    "stream_rng",
]
