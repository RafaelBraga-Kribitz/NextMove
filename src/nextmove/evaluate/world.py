"""The simulated world's answer to "what would this customer have done under action `a`?".

`OutcomeOracle` is the only bridge from the decision layer's evaluation to simulator ground
truth. It lives in `nextmove.evaluate`, which import-linter allows to read the simulator; the
packages that make decisions (`features`, `models`, `decisions`, `policies`) never may (ADR-003).

**Outcome definition (ADR-012).** One decision is evaluated as one purchase response at the
customer's next visit, drawn from the simulator's documented action-response function
(`nextmove.simulator.response`, reproduced in `docs/SIMULATOR_ASSUMPTIONS.md`):

    p(a) = clamp(base_conversion_probability(traits, ctx) * response_multiplier(traits, a, ctx))

with `ctx` built exactly as the simulator builds it: the customer's highest-affinity category,
that category's minimum sku stock at the end of the previous day, the seasonal multiplier of
the category's class, and the all-time contact counter (campaign exposures plus delivered
actions). `none` and `wait` deliver nothing inside the decision window, so both evaluate to
`p(none)`; a delivered action raises the contact counter by one before its response is drawn,
mirroring the simulator's tick loop. This makes `p(a) - p(none)` the same quantity as the
simulator's `ground_truth_uplift`, evaluated at the actual action parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nextmove.config.loader import ResolvedConfig
from nextmove.simulator.clock import SimClock
from nextmove.simulator.response import (
    ActionType,
    ResponseContext,
    base_conversion_probability,
    response_multiplier,
)
from nextmove.simulator.traits import LatentTraits
from nextmove.simulator.world import World
from nextmove.storage import Zone, query, resolve_table_path

__all__ = ["NO_DELIVERY", "OutcomeOracle", "common_random_numbers"]

#: Archetypes that deliver nothing within the decision window.
NO_DELIVERY = frozenset({"none", "wait"})


def common_random_numbers(seed: int, day: int, n: int) -> np.ndarray:
    """The uniform draws shared by every policy on `day`, indexed by integer customer id.

    Using one draw per (customer, day) for every policy is the common-random-numbers design:
    policy differences are not blurred by independent outcome noise, and a customer who
    "would buy anyway" (draw below p(none)) is the same customer under every policy.
    """
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, day]))).random(n)


@dataclass(frozen=True)
class _Customer:
    traits: LatentTraits
    category: str


class OutcomeOracle:
    """Ground-truth purchase probabilities for any (customer, day, action)."""

    def __init__(self, resolved: ResolvedConfig, root: Path | None = None) -> None:
        self.config = resolved.config.simulator
        clock = SimClock(self.config.start_date, self.config.horizon_days)
        # Only the clock and config are needed for the seasonal curve; skipping validation
        # avoids sampling the whole population a second time.
        self._world = World.model_construct(clock=clock, config=self.config)
        self._class = {c.name: c.seasonality_class for c in self.config.categories}
        traits = query(
            "SELECT customer_id, price_sensitivity, loyalty, fatigue_propensity, "
            "category_affinity FROM traits ORDER BY customer_id",
            root=root,
            traits=resolve_table_path("customer_traits", Zone.GROUND_TRUTH, root),
        ).to_pylist()
        self._customers: dict[str, _Customer] = {}
        for row in traits:
            affinity = dict(row["category_affinity"])
            lt = LatentTraits(
                price_sensitivity=row["price_sensitivity"],
                loyalty=row["loyalty"],
                fatigue_propensity=row["fatigue_propensity"],
                category_affinity=affinity,
            )
            category = max(sorted(affinity), key=lambda name: affinity[name])
            self._customers[str(row["customer_id"])] = _Customer(lt, category)
        stock = query(
            "SELECT s.tick, c.category, MIN(s.units) AS units FROM snapshots s "
            "JOIN catalog c ON c.sku = s.sku GROUP BY 1, 2 ORDER BY 1, 2",
            root=root,
            snapshots=resolve_table_path("inventory_snapshots", Zone.RAW, root),
            catalog=resolve_table_path("catalog", Zone.RAW, root),
        ).to_pylist()
        self._stock: dict[tuple[int, str], int] = {
            (int(r["tick"]), str(r["category"])): int(r["units"]) for r in stock
        }
        self._seasonal_cache: dict[tuple[int, str], float] = {}

    def primary_category(self, customer_id: str) -> str:
        return self._customers[customer_id].category

    @property
    def n_customers(self) -> int:
        return self.config.n_customers

    def _seasonal(self, day: int, category: str) -> float:
        key = (day, category)
        if key not in self._seasonal_cache:
            self._seasonal_cache[key] = self._world.seasonal_multiplier_for_class(
                day, self._class.get(category, "high")
            )
        return self._seasonal_cache[key]

    def _context(self, customer_id: str, day: int, fatigue_counter: int) -> ResponseContext:
        category = self._customers[customer_id].category
        units = self._stock.get(
            (max(day - 1, 0), category), self.config.inventory.initial_stock_per_sku
        )
        return ResponseContext(
            category=category,
            inventory_units=units,
            low_stock_threshold=self.config.inventory.low_stock_threshold,
            seasonal_multiplier=self._seasonal(day, category),
            fatigue_counter=fatigue_counter,
        )

    def p_convert(
        self,
        customer_id: str,
        day: int,
        archetype: str,
        params: dict[str, str | int | float | bool],
        prior_contacts: int,
    ) -> float:
        """Purchase probability at the next visit if `archetype` is delivered on `day`."""
        customer = self._customers[customer_id]
        if archetype in NO_DELIVERY:
            context = self._context(customer_id, day, prior_contacts)
            return base_conversion_probability(customer.traits, context, self.config)
        action = ActionType(archetype)
        context = self._context(customer_id, day, prior_contacts + 1)
        sim_params = {k: v for k, v in params.items() if isinstance(v, int | str)}
        multiplier = response_multiplier(customer.traits, action, sim_params, context, self.config)
        base = base_conversion_probability(customer.traits, context, self.config)
        return min(max(base * multiplier, 0.0), 1.0)

    def uplift(
        self,
        customer_id: str,
        day: int,
        archetype: str,
        params: dict[str, str | int | float | bool],
        prior_contacts: int,
    ) -> float:
        """Ground-truth `p(a) - p(none)` at the actual action parameters."""
        return self.p_convert(customer_id, day, archetype, params, prior_contacts) - self.p_convert(
            customer_id, day, "none", {}, prior_contacts
        )
