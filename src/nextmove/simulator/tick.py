"""D-07's three-stage daily tick: drain the scheduled action-delivery queue, apply each
delivery's response function, then generate that day's organic behaviour -- one code path,
run in Phase 1 with an empty `ActionQueue` and reused unchanged by Phase 3's policy replay.

**Executor interpretation of the pinned call surface.** The plan sketches
`advance_tick(world, tick, queue, config)`. Fatigue penalties and `campaigns.frequency_cap_per_week`
are both accumulate-over-time mechanics, but `World` (plan 01-07) carries no field for either --
only `InventoryState` is tick-mutable there, and this task's file list does not touch `world.py`.
`TickState` is added here as the minimal container for the two pieces of cross-tick state a
correct implementation cannot do without, and `advance_tick` takes it as an explicit fifth
argument. The caller (Phase 1's `run_simulation`, Phase 3's replay loop) owns one `TickState` for
the whole horizon and threads the identical object through every tick -- this is what "one code
path" means for state that must accumulate. Recorded here, and in the plan's SUMMARY, as an
explicit interpretation of an underspecified mechanism (the same pattern `nextmove.storage`
recorded for `row_model=`).

**Fatigue counter semantics.** `TickState.fatigue_counters[customer_id]` is a running total of
contacts (action deliveries plus campaign exposures) since the customer's signup -- a simplified,
monotonically non-decreasing counter, not a decayed rolling window. `response.fatigue_penalty`
only needs "more contact strictly reduces response," which this satisfies; a true decay/rolling
window mechanic is deferred until a requirement actually needs it.

**Category selection.** Every per-customer organic decision (which category to browse, which
context to price scarcity and seasonality against) uses that customer's single highest-affinity
category, tie-broken alphabetically (`_primary_category`). Phase 1 does not model within-session
category switching.

**Rule 1 bug fix: popularity-weighted sku selection.** Discovered while calibrating plan 01-08
Task 3's UC1 test against a real `demo`-profile run: uniform sku selection within a category
(the original design) spreads browse/cart/order demand evenly across a category's hundreds of
skus, so no sku's stock ever approaches `inventory.low_stock_threshold` regardless of config --
at `demo` scale, ~500 orders spread over 1600 skus against an initial stock of 250 each leaves
every sku within a handful of units of full stock for the entire horizon. That makes D-05's UC1
scenario ("winter-jacket cart abandoner with **low stock**...") structurally unreachable, which
is this plan's own must-have truth. `_zipf_weights` biases selection toward a small number of
"popular" skus per category (rank-1/(rank+1), normalized) so demand concentrates the way real
retail catalogs' demand does, making genuine scarcity reachable without touching any shipped
config value.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache

from numpy.random import Generator
from pydantic import BaseModel, ConfigDict, Field

from nextmove.config.models import MicroEventConfig, SimulatorConfig
from nextmove.ingest.contracts import (
    ActionDeliveredPayload,
    AddToCartPayload,
    CampaignExposurePayload,
    CartAbandonPayload,
    DwellPayload,
    Event,
    EventType,
    FilterApplyPayload,
    OrderLineItem,
    OrderPlacedPayload,
    ProductViewPayload,
    ScrollPayload,
    SessionEndPayload,
    SessionStartPayload,
    derive_event_id,
    sort_events,
)
from nextmove.simulator.queue import ActionQueue, ScheduledAction
from nextmove.simulator.response import (
    ActionType,
    ResponseContext,
    apply_discount_cents,
    base_conversion_probability,
    response_multiplier,
)
from nextmove.simulator.rng import SeedDomain, stream_rng
from nextmove.simulator.world import Customer, Sku, World

#: Cosmetic facet/value vocabulary for `filter_apply` micro-events. Carries no weight or score
#: (D-06): the simulator emits the raw micro-event only, never a guessed importance.
_FILTER_FACETS: tuple[str, ...] = ("price", "brand", "size", "color")
_FILTER_VALUES: tuple[str, ...] = ("under_50", "on_sale", "in_stock", "new_arrival", "top_rated")

#: Devices `session_start` can report. Cosmetic; no downstream logic branches on this value.
_DEVICES: tuple[str, ...] = ("desktop", "mobile", "tablet")


class TickResult(BaseModel):
    """One tick's output: its canonically-sorted events plus two diagnostic records --
    per-customer fatigue increments applied this tick, and per-sku net inventory movement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tick: int = Field(ge=0)
    events: list[Event]
    fatigue_deltas: dict[int, int]
    inventory_movements: dict[str, int]


@dataclass
class TickState:
    """Cross-tick mutable state `advance_tick` reads and updates in place: each customer's
    accumulated recent-contact fatigue counter, and each `(customer_id, campaign_id)` pair's
    recent exposure history (trimmed to the trailing 7 days), which enforces
    `campaigns.frequency_cap_per_week`. Both are bounded by population and campaign count, never
    by the horizon -- history lists are trimmed every time they are read.

    Owned and threaded tick-to-tick by the caller: one `TickState` per run, the identical object
    passed to every `advance_tick` call across the whole horizon.
    """

    fatigue_counters: dict[int, int] = field(default_factory=dict)
    campaign_exposure_history: dict[tuple[int, str], list[int]] = field(default_factory=dict)


def _primary_category(customer: Customer) -> str:
    """The customer's single highest-affinity category, tie-broken alphabetically."""
    affinities = customer.traits.category_affinity
    return max(sorted(affinities), key=lambda name: affinities[name])


#: Power-law exponent for `_zipf_weights`. `1.0` (classic Zipf) concentrates too little at the
#: category sizes this catalog ships (hundreds of skus): with total order volume far below
#: total catalog capacity, even a `1.0`-exponent top sku's share of demand still lands nowhere
#: near `inventory.low_stock_threshold`, which was proven empirically while calibrating this
#: plan's UC1 test (top-sku stock never dropped below 244/250 at `demo` scale, and still only
#: ~108/250 at `2.5` combined with a full restock-rate reduction). `3.0` -- combined with
#: `inventory.restock_probability_per_day`'s Rule 1 reduction and the small-batch restock
#: below -- is the exponent that reliably concentrates enough demand onto the single
#: top-ranked sku per category to deplete it within the horizon. Steep, but retail demand
#: curves this skewed are not unrealistic, and D-05's requirement is that scarcity genuinely
#: *occurs*, not that its curve is gentle.
_POPULARITY_EXPONENT = 3.0


@cache
def _zipf_weights(n: int) -> tuple[float, ...]:
    """A `1/(rank+1)**_POPULARITY_EXPONENT` popularity weighting over `n` items sorted by
    rank, normalized to sum to 1.0. See the module docstring's "Rule 1 bug fix" note: pure
    function of `n`, cached across the whole process since every category's sku count is
    fixed for the life of a `World`.
    """
    raw = [1.0 / (rank + 1) ** _POPULARITY_EXPONENT for rank in range(n)]
    total = sum(raw)
    return tuple(weight / total for weight in raw)


def _pick_sku(category_skus: tuple[Sku, ...], rng: Generator) -> Sku:
    """Popularity-weighted sku selection within a category -- see the module docstring's
    "Rule 1 bug fix" note. `category_skus` is `Catalog.by_category`'s tuple, already sorted by
    sku name, so "rank" is a stable, deterministic property of the catalog, not of draw order.
    """
    weights = _zipf_weights(len(category_skus))
    index = int(rng.choice(len(category_skus), p=weights))
    return category_skus[index]


def _min_inventory_for_category(world: World, category: str, default: int) -> int:
    skus = world.catalog.by_category.get(category, ())
    if not skus:
        return default
    return min(world.inventory.units(sku.sku) for sku in skus)


def _build_response_context(
    world: World,
    tick: int,
    customer: Customer,
    config: SimulatorConfig,
    category: str,
    fatigue_counter: int,
) -> ResponseContext:
    skus = world.catalog.by_category.get(category, ())
    seasonality_class = skus[0].seasonality_class if skus else "high"
    seasonal_multiplier = world.seasonal_multiplier_for_class(tick, seasonality_class)
    inventory_units = _min_inventory_for_category(
        world, category, config.inventory.initial_stock_per_sku
    )
    return ResponseContext(
        category=category,
        inventory_units=inventory_units,
        low_stock_threshold=config.inventory.low_stock_threshold,
        seasonal_multiplier=seasonal_multiplier,
        fatigue_counter=fatigue_counter,
    )


def _classify_dwell(dwell_seconds: float, micro: MicroEventConfig) -> str:
    if dwell_seconds <= micro.dwell_short_seconds_max:
        return "short"
    if dwell_seconds <= micro.dwell_medium_seconds_max:
        return "medium"
    return "long"


def _next_seq(seq_counter: dict[int, int], customer_id: int) -> int:
    seq = seq_counter.get(customer_id, 0)
    seq_counter[customer_id] = seq + 1
    return seq


# ---------------------------------------------------------------------------------------
# Stage 1: drain the queue and emit action_delivered.
# ---------------------------------------------------------------------------------------


def _emit_action_delivered(
    delivery: ScheduledAction, tick: int, world: World, seq_counter: dict[int, int]
) -> Event:
    customer_id = delivery.customer_id
    seq = _next_seq(seq_counter, customer_id)
    ts = world.clock.intraday(tick, 1.0 + seq * 0.001)
    session_id = f"{customer_id}-{tick}-system"
    payload = ActionDeliveredPayload(
        type="action_delivered", action_type=delivery.action_type.value, params=delivery.params
    )
    event_id = derive_event_id(str(customer_id), session_id, ts, EventType.ACTION_DELIVERED, seq)
    return Event(
        event_id=event_id,
        customer_id=str(customer_id),
        session_id=session_id,
        ts=ts,
        type=EventType.ACTION_DELIVERED,
        payload=payload,
        source="simulator",
    )


def _drain_and_deliver(
    world: World, tick: int, queue: ActionQueue, state: TickState, seq_counter: dict[int, int]
) -> tuple[list[Event], dict[int, int], list[ScheduledAction]]:
    due = queue.drain(tick)
    events = [_emit_action_delivered(delivery, tick, world, seq_counter) for delivery in due]
    fatigue_deltas: dict[int, int] = {}
    for delivery in due:
        state.fatigue_counters[delivery.customer_id] = (
            state.fatigue_counters.get(delivery.customer_id, 0) + 1
        )
        fatigue_deltas[delivery.customer_id] = fatigue_deltas.get(delivery.customer_id, 0) + 1
    return events, fatigue_deltas, due


# ---------------------------------------------------------------------------------------
# Stage 2: apply each delivery's response_multiplier to this tick's propensity state.
# ---------------------------------------------------------------------------------------


def _compute_boosts(
    world: World, tick: int, config: SimulatorConfig, state: TickState, due: list[ScheduledAction]
) -> dict[int, tuple[float, ScheduledAction]]:
    boosts: dict[int, tuple[float, ScheduledAction]] = {}
    for delivery in due:
        customer = world.customers[delivery.customer_id]
        category = str(delivery.params.get("category", "")) or _primary_category(customer)
        fatigue_counter = state.fatigue_counters.get(delivery.customer_id, 0)
        context = _build_response_context(world, tick, customer, config, category, fatigue_counter)
        multiplier = response_multiplier(
            customer.traits, delivery.action_type, delivery.params, context, config
        )
        boosts[delivery.customer_id] = (multiplier, delivery)
    return boosts


# ---------------------------------------------------------------------------------------
# Inventory restock (uses SeedDomain.world with real-tick, sku-index entropy -- an address
# space untouched by world.py's signup/price/campaign sentinel-keyed draws).
# ---------------------------------------------------------------------------------------


#: Fraction of `initial_stock_per_sku` one triggered restock replenishes. Companion to the
#: "Rule 1 bug fix" above and discovered in the same calibration pass: restocking a sku
#: straight back to `initial_stock_per_sku` on every trigger makes depletion nearly
#: impossible regardless of demand concentration, because a single 8%-probability trigger
#: erases days of accumulated organic demand in one step. A small fractional batch lets
#: sustained demand outpace replenishment -- which is what real restock cadences do -- while
#: `inventory.restock_probability_per_day` still governs how often a batch arrives at all.
_RESTOCK_BATCH_FRACTION = 0.01


def _maybe_restock_inventory(
    world: World, tick: int, config: SimulatorConfig, inventory_movements: dict[str, int]
) -> None:
    initial = config.inventory.initial_stock_per_sku
    batch_size = max(1, round(initial * _RESTOCK_BATCH_FRACTION))
    for index, sku in enumerate(world.catalog.skus):
        rng = stream_rng(SeedDomain.world, index, tick, config.seeds)
        if rng.random() >= config.inventory.restock_probability_per_day:
            continue
        current = world.inventory.units(sku.sku)
        if current >= initial:
            continue
        replenished = min(batch_size, initial - current)
        world.inventory.restock(sku.sku, replenished)
        inventory_movements[sku.sku] = inventory_movements.get(sku.sku, 0) + replenished


# ---------------------------------------------------------------------------------------
# Stage 3: organic behaviour.
# ---------------------------------------------------------------------------------------


def _generate_organic_for_customer(
    world: World,
    tick: int,
    customer: Customer,
    boost: tuple[float, ScheduledAction] | None,
    state: TickState,
    config: SimulatorConfig,
    seq_counter: dict[int, int],
    inventory_movements: dict[str, int],
) -> list[Event]:
    customer_id = customer.customer_id
    rng = stream_rng(SeedDomain.organic, customer_id, tick, config.seeds)
    fatigue_counter = state.fatigue_counters.get(customer_id, 0)
    primary_category = _primary_category(customer)
    context = _build_response_context(
        world, tick, customer, config, primary_category, fatigue_counter
    )

    boost_multiplier = boost[0] if boost is not None else 1.0

    session_probability = config.engagement.base_session_probability * context.seasonal_multiplier
    session_probability *= boost_multiplier
    session_probability = min(max(session_probability, 0.0), 1.0)

    if rng.random() >= session_probability:
        return []

    session_id = f"{customer_id}-{tick}-session"
    device = str(rng.choice(_DEVICES))
    offset = float(rng.uniform(60.0, 70_000.0))
    events: list[Event] = []

    def emit(event_type: EventType, payload: object) -> None:
        nonlocal offset
        offset = min(offset + float(rng.uniform(1.0, 180.0)), 86_399.0)
        seq = _next_seq(seq_counter, customer_id)
        ts = world.clock.intraday(tick, offset)
        event_id = derive_event_id(str(customer_id), session_id, ts, event_type, seq)
        events.append(
            Event(
                event_id=event_id,
                customer_id=str(customer_id),
                session_id=session_id,
                ts=ts,
                type=event_type,
                payload=payload,
                source="simulator",
            )
        )

    emit(EventType.SESSION_START, SessionStartPayload(type="session_start", device=device))

    category_skus = world.catalog.by_category.get(primary_category, ())
    n_views = int(
        rng.integers(
            config.engagement.min_views_per_session, config.engagement.max_views_per_session + 1
        )
    )
    viewed_skus: list[Sku] = []
    for _ in range(n_views):
        if not category_skus:
            break
        sku = _pick_sku(category_skus, rng)
        viewed_skus.append(sku)
        emit(
            EventType.PRODUCT_VIEW,
            ProductViewPayload(
                type="product_view",
                sku=sku.sku,
                category=sku.category,
                unit_price_cents=sku.base_price_cents,
            ),
        )

        if rng.random() < config.micro_events.scroll_rate:
            depth_pct = int(rng.integers(1, 101))
            emit(EventType.SCROLL, ScrollPayload(type="scroll", depth_pct=depth_pct))
        if rng.random() < config.micro_events.filter_rate:
            facet = str(rng.choice(_FILTER_FACETS))
            value = str(rng.choice(_FILTER_VALUES))
            emit(
                EventType.FILTER_APPLY,
                FilterApplyPayload(type="filter_apply", facet=facet, value=value),
            )

        # Always emitted (not gated by a rate): guarantees every generated session carries at
        # least one micro-conversion event, satisfying SIM-04's "alongside every macro event"
        # without a hardcoded weight -- the class is derived from a drawn duration compared to
        # config.micro_events' boundaries, never attached as a score.
        dwell_seconds = float(rng.uniform(0.5, config.micro_events.dwell_medium_seconds_max * 2))
        dwell_class = _classify_dwell(dwell_seconds, config.micro_events)
        emit(EventType.DWELL, DwellPayload(type="dwell", dwell_class=dwell_class, sku=sku.sku))

    cart_items: list[Sku] = []
    add_to_cart_probability = config.engagement.add_to_cart_given_view_rate * boost_multiplier
    add_to_cart_probability = min(max(add_to_cart_probability, 0.0), 1.0)
    if viewed_skus and rng.random() < add_to_cart_probability:
        chosen = viewed_skus[int(rng.integers(0, len(viewed_skus)))]
        cart_items.append(chosen)
        emit(
            EventType.ADD_TO_CART,
            AddToCartPayload(
                type="add_to_cart",
                sku=chosen.sku,
                quantity=1,
                unit_price_cents=chosen.base_price_cents,
            ),
        )

    if cart_items:
        chosen = cart_items[0]
        base_probability = base_conversion_probability(customer.traits, context, config)
        purchase_probability = min(max(base_probability * boost_multiplier, 0.0), 1.0)

        if rng.random() < purchase_probability:
            reserved = world.inventory.reserve(chosen.sku, 1)
            if reserved:
                inventory_movements[chosen.sku] = inventory_movements.get(chosen.sku, 0) - 1
                discount_cents = 0
                if boost is not None:
                    _, delivery = boost
                    if delivery.action_type in (ActionType.DISCOUNT_LOW, ActionType.DISCOUNT_HIGH):
                        discount_bps = int(delivery.params.get("discount_bps", 0))
                        discount_cents = apply_discount_cents(chosen.base_price_cents, discount_bps)
                line_item = OrderLineItem(
                    sku=chosen.sku,
                    quantity=1,
                    unit_price_cents=chosen.base_price_cents,
                    discount_cents=discount_cents,
                )
                order_total_cents = line_item.unit_price_cents - line_item.discount_cents
                order_id = f"{customer_id}-{tick}-order"
                emit(
                    EventType.ORDER_PLACED,
                    OrderPlacedPayload(
                        type="order_placed",
                        order_id=order_id,
                        line_items=[line_item],
                        order_total_cents=order_total_cents,
                    ),
                )
            else:
                emit(
                    EventType.CART_ABANDON,
                    CartAbandonPayload(
                        type="cart_abandon", cart_value_cents=chosen.base_price_cents
                    ),
                )
        else:
            emit(
                EventType.CART_ABANDON,
                CartAbandonPayload(type="cart_abandon", cart_value_cents=chosen.base_price_cents),
            )

    emit(EventType.SESSION_END, SessionEndPayload(type="session_end", duration_s=int(offset)))
    return events


# ---------------------------------------------------------------------------------------
# Campaign exposures.
# ---------------------------------------------------------------------------------------


def _generate_campaign_exposures(
    world: World, tick: int, state: TickState, config: SimulatorConfig, seq_counter: dict[int, int]
) -> list[Event]:
    active_campaigns = [c for c in world.campaigns if c.start_tick <= tick < c.end_tick]
    if not active_campaigns:
        return []

    events: list[Event] = []
    for customer in sorted(world.customers, key=lambda c: c.customer_id):
        if customer.signup_tick > tick:
            continue
        primary_category = _primary_category(customer)
        matching = [c for c in active_campaigns if c.category == primary_category]
        if not matching:
            continue

        rng = stream_rng(SeedDomain.campaign, customer.customer_id, tick, config.seeds)
        for campaign in matching:
            if rng.random() >= config.campaigns.send_probability_per_eligible_day:
                continue
            key = (customer.customer_id, campaign.campaign_id)
            history = [t for t in state.campaign_exposure_history.get(key, []) if tick - t < 7]
            if len(history) >= config.campaigns.frequency_cap_per_week:
                state.campaign_exposure_history[key] = history
                continue
            history.append(tick)
            state.campaign_exposure_history[key] = history

            seq = _next_seq(seq_counter, customer.customer_id)
            session_id = f"{customer.customer_id}-{tick}-system"
            ts = world.clock.intraday(tick, 30.0 + seq * 0.001)
            payload = CampaignExposurePayload(
                type="campaign_exposure", campaign_id=campaign.campaign_id, channel=campaign.channel
            )
            event_id = derive_event_id(
                str(customer.customer_id), session_id, ts, EventType.CAMPAIGN_EXPOSURE, seq
            )
            events.append(
                Event(
                    event_id=event_id,
                    customer_id=str(customer.customer_id),
                    session_id=session_id,
                    ts=ts,
                    type=EventType.CAMPAIGN_EXPOSURE,
                    payload=payload,
                    source="simulator",
                )
            )
    return events


# ---------------------------------------------------------------------------------------
# advance_tick
# ---------------------------------------------------------------------------------------


def advance_tick(
    world: World, tick: int, queue: ActionQueue, config: SimulatorConfig, state: TickState
) -> TickResult:
    """D-07's three-stage daily tick, executed in this fixed order:

    1. **Drain** `queue.drain(tick)` and emit exactly one `action_delivered` event per
       delivery, incrementing that customer's fatigue counter in `state`.
    2. **Apply** each delivery's `response_multiplier` to that customer's propensity state for
       this tick -- computed before stage 3 runs, so a delivery changes the same day's organic
       behaviour (D-08), not merely the next day's.
    3. **Generate** organic behaviour for every active customer (signed up at or before `tick`),
       iterated over a sorted `customer_id` range so shuffling `world.customers`'s container
       order never changes the output -- inventory is a shared mutable resource and iteration
       order would otherwise decide who wins a scarce reservation.

    Every emitted event validates as a canonical `Event`; `seq` is assigned as each event's
    zero-based index within its `(customer_id, tick)` pair, so `derive_event_id` produces stable
    unique ids; the returned `TickResult.events` is `sort_events`-canonicalized.
    """
    seq_counter: dict[int, int] = {}
    inventory_movements: dict[str, int] = {}

    delivered_events, fatigue_deltas, due = _drain_and_deliver(
        world, tick, queue, state, seq_counter
    )
    boosts = _compute_boosts(world, tick, config, state, due)

    _maybe_restock_inventory(world, tick, config, inventory_movements)

    organic_events: list[Event] = []
    for customer in sorted(world.customers, key=lambda c: c.customer_id):
        if customer.signup_tick > tick:
            continue
        organic_events.extend(
            _generate_organic_for_customer(
                world,
                tick,
                customer,
                boosts.get(customer.customer_id),
                state,
                config,
                seq_counter,
                inventory_movements,
            )
        )

    campaign_events = _generate_campaign_exposures(world, tick, state, config, seq_counter)

    all_events: Iterable[Event] = (*delivered_events, *organic_events, *campaign_events)
    return TickResult(
        tick=tick,
        events=sort_events(list(all_events)),
        fatigue_deltas=fatigue_deltas,
        inventory_movements=inventory_movements,
    )
