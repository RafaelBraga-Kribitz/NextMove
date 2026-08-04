"""The simulated world's static structure: customers, catalog, inventory, and a campaign
calendar, all built from `SimulatorConfig` by `World.initialize`.

Every category name, SKU count, price band, population size, and campaign parameter this
module produces is read from `config` — none is a literal here (D-01, ENG-03): changing
`config/simulator.yaml` changes the generated world with no code edit.

**Purpose-scoped sub-streams.** Beyond customer traits (owned by `nextmove.simulator.traits`),
this module derives three more kinds of per-entity randomness — signup timing, SKU prices, and
campaign discounts — each of which needs its own independent stream. Reusing `entity_rng`
directly for these would collide with (or duplicate) customer-id-keyed trait streams: calling
`entity_rng(SeedDomain.world, 5, seeds)` for both customer 5's traits and, say, SKU ordinal 5's
price would hand both draws the *same* underlying stream. Instead this module uses
`stream_rng` with a small set of fixed, large tick sentinels (`_SIGNUP_TICK_SENTINEL`,
`_CATALOG_PRICE_TICK_SENTINEL`, `_CAMPAIGN_TICK_SENTINEL`) to fold a distinguishing value into
each purpose's entropy. `numpy.random.SeedSequence` entropy must be non-negative, so these
sentinels are chosen far above any realistic `horizon_days` (a multi-year daily-tick horizon
is still under a million ticks) rather than negative; a real simulated tick can therefore
never collide with a sentinel, and each purpose's sentinel is unique, so the three purposes
never collide with each other either.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nextmove.config.models import SimulatorConfig
from nextmove.simulator.clock import SimClock
from nextmove.simulator.rng import SeedDomain, stream_rng
from nextmove.simulator.traits import LatentTraits, sample_latent_traits

# Large tick sentinels for purpose-scoped, non-tick-indexed sub-streams (see module
# docstring) -- SeedSequence entropy must be non-negative, so these sit far above any
# realistic horizon_days instead of below zero. Never renumber these once execution has
# produced real data: doing so would change every draw derived through them, breaking
# ENG-04's byte-identical-rerun claim.
_SIGNUP_TICK_SENTINEL = 1_000_000_001
_CATALOG_PRICE_TICK_SENTINEL = 1_000_000_002
_CAMPAIGN_TICK_SENTINEL = 1_000_000_003


class Customer(BaseModel):
    """One simulated customer: identity, latent traits, and the tick they signed up on."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: int = Field(ge=0)
    traits: LatentTraits
    signup_tick: int = Field(ge=0)


class Sku(BaseModel):
    """One catalog item. `base_price_cents` is an integer minor-unit price (never a float) so
    no monetary value can drift in Parquet bytes between runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sku: str = Field(min_length=1)
    category: str = Field(min_length=1)
    base_price_cents: int = Field(ge=0)
    margin_rate: float = Field(ge=0.0, le=1.0)
    seasonality_class: Literal["high", "low"]


class Catalog(BaseModel):
    """The full SKU catalog plus lookups by sku and by category, both built over sorted keys
    so lookup iteration order is itself deterministic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skus: tuple[Sku, ...]
    by_sku: dict[str, Sku]
    by_category: dict[str, tuple[Sku, ...]]

    @classmethod
    def build(cls, skus: list[Sku]) -> "Catalog":
        ordered = tuple(sorted(skus, key=lambda sku: sku.sku))
        by_sku = {sku.sku: sku for sku in ordered}
        grouped: dict[str, list[Sku]] = {}
        for sku in ordered:
            grouped.setdefault(sku.category, []).append(sku)
        by_category = {name: tuple(grouped[name]) for name in sorted(grouped)}
        return cls(skus=ordered, by_sku=by_sku, by_category=by_category)


class InventoryState:
    """Mutable per-SKU stock levels. `reserve`/`release`/`restock` all clamp at zero: stock
    can never go negative regardless of call order.

    Deliberately not a frozen Pydantic model — inventory is the one piece of world state a
    running simulation mutates tick over tick (Phase 3 reuses this exact class for the daily
    tick loop), unlike the rest of `World`, which is fixed at `initialize` time.
    """

    def __init__(self, initial_stock: dict[str, int]) -> None:
        self._stock: dict[str, int] = dict(initial_stock)

    def units(self, sku: str) -> int:
        """Current stock for `sku`; 0 for a sku this inventory was never seeded with."""
        return self._stock.get(sku, 0)

    def reserve(self, sku: str, quantity: int) -> bool:
        """Attempt to reserve `quantity` units of `sku`.

        Returns `True` and decrements stock if enough units are available. Returns `False`
        and leaves stock unchanged otherwise — in particular, reserving against a sku with
        zero units always returns `False` and leaves the count at zero; it never produces a
        negative count.
        """
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        available = self._stock.get(sku, 0)
        if available < quantity:
            return False
        self._stock[sku] = available - quantity
        return True

    def release(self, sku: str, quantity: int) -> None:
        """Return `quantity` previously reserved units of `sku` to stock."""
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        self._stock[sku] = self._stock.get(sku, 0) + quantity

    def restock(self, sku: str, quantity: int) -> None:
        """Add `quantity` freshly restocked units of `sku`."""
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        self._stock[sku] = self._stock.get(sku, 0) + quantity


class Campaign(BaseModel):
    """One scheduled campaign window: a category/channel pair active over
    `[start_tick, end_tick)`, matching `SimClock`'s half-open tick convention. Whether an
    individual exposure actually fires on a given day within the window (subject to
    `frequency_cap_per_week` and `send_probability_per_eligible_day`) is organic-behavior
    logic owned by plan 01-08, not this module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str = Field(min_length=1)
    start_tick: int = Field(ge=0)
    end_tick: int = Field(gt=0)
    category: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    discount_bps: int = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def _check_tick_order(self) -> "Campaign":
        if self.start_tick >= self.end_tick:
            raise ValueError(f"start_tick ({self.start_tick}) must be < end_tick ({self.end_tick})")
        return self


class World(BaseModel):
    """The fully-populated simulated world: customers, catalog, inventory, campaign calendar,
    the clock that drives every timestamp, and the config that produced all of it."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    customers: tuple[Customer, ...]
    catalog: Catalog
    inventory: InventoryState
    campaigns: tuple[Campaign, ...]
    clock: SimClock
    config: SimulatorConfig

    @classmethod
    def initialize(cls, config: SimulatorConfig) -> "World":
        """Build a fully-populated, deterministic world from `config`.

        Two calls with the same `config` produce worlds whose customers, catalog, and
        campaign calendar compare equal; two calls with configs differing only in
        `n_customers` produce identical traits for every customer id present in both
        (RESEARCH Pattern 1 — nothing here depends on population size).
        """
        clock = SimClock(config.start_date, config.horizon_days)
        customers = tuple(
            Customer(
                customer_id=customer_id,
                traits=sample_latent_traits(customer_id, config),
                signup_tick=_draw_signup_tick(customer_id, config),
            )
            for customer_id in range(config.n_customers)
        )
        catalog = _build_catalog(config)
        inventory = _build_inventory(config, catalog)
        campaigns = _build_campaigns(config)
        return cls(
            customers=customers,
            catalog=catalog,
            inventory=inventory,
            campaigns=campaigns,
            clock=clock,
            config=config,
        )

    def seasonal_multiplier(self, tick: int) -> float:
        """The raw configured multiplier for `tick`'s calendar month — the full-amplitude
        curve `high`-class categories experience directly."""
        month = self.clock.timestamp_for_tick(tick).month
        return self.config.seasonality.monthly_multipliers[month - 1]

    def seasonal_multiplier_for_class(
        self, tick: int, seasonality_class: Literal["high", "low"]
    ) -> float:
        """The multiplier a category of `seasonality_class` experiences at `tick`.

        `high` categories read the raw configured curve unmodified. `low` categories read a
        damped version of the same curve, pulled toward 1.0 by
        `config.seasonality.low_class_amplitude_factor` — this is what makes the
        low-seasonality contrast category genuinely flatter (a smaller peak-to-trough ratio)
        rather than merely relabeled (D-01).
        """
        raw = self.seasonal_multiplier(tick)
        if seasonality_class == "high":
            return raw
        factor = self.config.seasonality.low_class_amplitude_factor
        return 1.0 + (raw - 1.0) * factor

    def is_high_season(self, tick: int) -> bool:
        """Whether `tick` falls in the configured peak month."""
        return self.clock.timestamp_for_tick(tick).month == self.config.seasonality.peak_month


def _draw_signup_tick(customer_id: int, config: SimulatorConfig) -> int:
    rng = stream_rng(SeedDomain.world, customer_id, _SIGNUP_TICK_SENTINEL, config.seeds)
    return int(rng.integers(0, config.horizon_days))


def _build_catalog(config: SimulatorConfig) -> Catalog:
    skus: list[Sku] = []
    sku_ordinal = 0
    for category in config.categories:
        for local_index in range(category.sku_count):
            rng = stream_rng(
                SeedDomain.world, sku_ordinal, _CATALOG_PRICE_TICK_SENTINEL, config.seeds
            )
            price = int(
                rng.integers(category.base_price_cents_min, category.base_price_cents_max + 1)
            )
            skus.append(
                Sku(
                    sku=f"{category.name}-{local_index:05d}",
                    category=category.name,
                    base_price_cents=price,
                    margin_rate=category.margin_rate,
                    seasonality_class=category.seasonality_class,
                )
            )
            sku_ordinal += 1
    return Catalog.build(skus)


def _build_inventory(config: SimulatorConfig, catalog: Catalog) -> InventoryState:
    initial_stock = {sku.sku: config.inventory.initial_stock_per_sku for sku in catalog.skus}
    return InventoryState(initial_stock)


def _build_campaigns(config: SimulatorConfig) -> tuple[Campaign, ...]:
    campaigns: list[Campaign] = []
    ordinal = 0
    for category in config.categories:
        for channel in config.campaigns.channels:
            rng = stream_rng(SeedDomain.campaign, ordinal, _CAMPAIGN_TICK_SENTINEL, config.seeds)
            discount_bps = int(
                rng.integers(
                    config.campaigns.discount_bps_min, config.campaigns.discount_bps_max + 1
                )
            )
            campaigns.append(
                Campaign(
                    campaign_id=f"{category.name}-{channel}-{ordinal:04d}",
                    start_tick=0,
                    end_tick=config.horizon_days,
                    category=category.name,
                    channel=channel,
                    discount_bps=discount_bps,
                )
            )
            ordinal += 1
    return tuple(campaigns)
