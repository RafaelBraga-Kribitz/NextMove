"""D-03's explicit, documented action-response functions plus D-04's deliberate reward-hacking
loophole.

Every simulated customer's reaction to a delivered action is a function of their latent traits
(`nextmove.simulator.traits.LatentTraits`) plus a `ResponseContext` -- never a hidden or random
effect. `ground_truth_uplift` is the whole point: because `response_multiplier` is a closed-form
function of `(traits, action, params, context, config)`, the counterfactual
`P(convert|action) - P(convert|none)` is computable for any `(customer, action)` pair without
running the simulation, which is exactly the precondition `docs/adr/006-...md` names for measuring
the propensity-delta uplift approximation's error in Phase 4 (MODEL-06).

Money throughout this module is an integer count of minor units (cents), with exactly one
exception: `apply_discount_cents` is the project's single monetary rounding site, the only place
a cents value passes through a non-integer (`decimal.Decimal`) intermediate. Every other monetary
path in `nextmove.simulator` uses `apply_discount_cents` rather than dividing floats.
"""

from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from nextmove.config.models import SimulatorConfig
from nextmove.simulator.traits import LatentTraits


class ActionType(StrEnum):
    """DEC-03's eight action archetypes. `NONE` is the always-available do-nothing action;
    `response_multiplier` and `ground_truth_uplift` both return their identity value for it by
    direct construction, never by a config table lookup."""

    NONE = "none"
    WAIT = "wait"
    RECOMMEND = "recommend"
    BUNDLE = "bundle"
    DISCOUNT_LOW = "discount_low"
    DISCOUNT_HIGH = "discount_high"
    EMAIL_NOW = "email_now"
    EMAIL_DELAYED = "email_delayed"


#: Archetypes whose effect scales with the customer's price sensitivity and the discount's own
#: magnitude, and whose effectiveness is suppressed by scarce inventory (UC1: "low inventory =>
#: suppress discount").
_DISCOUNT_ACTIONS = frozenset({ActionType.DISCOUNT_LOW, ActionType.DISCOUNT_HIGH})

#: Archetypes whose effect scales with the customer's loyalty -- a retention-style nudge, not a
#: price incentive.
_LOYALTY_ACTIONS = frozenset({ActionType.RECOMMEND, ActionType.BUNDLE})


class ResponseContext(BaseModel):
    """Everything `response_multiplier` and `ground_truth_uplift` need beyond a customer's own
    latent traits: which category the action targets, that category's current inventory
    scarcity, the calendar's seasonal multiplier at the acting tick, and the customer's
    accumulated recent-contact fatigue counter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str = Field(min_length=1)
    inventory_units: int = Field(ge=0)
    low_stock_threshold: int = Field(ge=0)
    seasonal_multiplier: float = Field(gt=0.0)
    fatigue_counter: int = Field(ge=0)


def apply_discount_cents(price_cents: int, discount_bps: int) -> int:
    """The project's single monetary rounding site: the discount amount, in whole cents, that a
    `discount_bps` (basis points, 1/100 of a percent) reduction produces on `price_cents`.

    Computed with `decimal.Decimal` and quantized to whole cents with `ROUND_HALF_EVEN`. Every
    other monetary path in `nextmove.simulator` calls this rather than dividing floats: money is
    carried as integer minor units everywhere else, and a second rounding site would be a second
    place for two runs to disagree in the last digit.
    """
    price = Decimal(price_cents)
    bps = Decimal(discount_bps)
    raw_discount = price * bps / Decimal(10_000)
    quantized = raw_discount.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    return int(quantized)


def fatigue_penalty(traits: LatentTraits, fatigue_counter: int, config: SimulatorConfig) -> float:
    """Multiplicative fatigue penalty in the interval `(0, 1]`, decreasing as
    `fatigue_counter` rises, scaled by the customer's own `fatigue_propensity`.

    This is D-04's deliberate, documented reward-hacking **loophole**: when
    `config.loophole.fatigue_penalty_enabled` is `False`, this function returns exactly `1.0`
    regardless of `fatigue_counter`, and the simulated world stops penalizing repeated contact
    entirely. A policy that maximizes short-horizon profit with the penalty disabled will
    contact fatigued customers relentlessly, with no in-simulation cost for doing so -- that is
    the exploit the mandated reward-hacking probe targets, arriving with the v2 contextual
    bandit. Phase 1 ships only the loophole, documented here rather than left implicit, which is
    what makes it a deliberate artifact rather than a bug someone later finds.
    """
    if not config.loophole.fatigue_penalty_enabled:
        return 1.0
    weight = config.response.fatigue_penalty_weight
    decay = weight * traits.fatigue_propensity * fatigue_counter
    return 1.0 / (1.0 + decay)


def _scarcity_factor(context: ResponseContext) -> float:
    """`1.0` unless `context`'s category is at or below its configured low-stock threshold, in
    which case a discount's effectiveness is damped in proportion to how far stock has fallen
    below that threshold -- the mechanism behind UC1's "low inventory suppresses the discount"
    narrative."""
    if context.inventory_units > context.low_stock_threshold:
        return 1.0
    denominator = max(context.low_stock_threshold, 1)
    return min(1.0, context.inventory_units / denominator)


def response_multiplier(
    traits: LatentTraits,
    action_type: ActionType,
    params: dict[str, str | int],
    context: ResponseContext,
    config: SimulatorConfig,
) -> float:
    """D-03's documented action-response function: the multiplicative factor a delivered
    `action_type` applies to this customer's baseline conversion probability. Returns exactly
    `1.0` for `ActionType.NONE`.

    **The combining formula, in words and symbols** (plan 01-11 lifts this verbatim into
    `docs/SIMULATOR_ASSUMPTIONS.md`, SIM-03):

        response_multiplier(traits, action, params, context, config) =
            1.0                                          if action is NONE
            else
            archetype_base[action]                       (config.response.archetype_base_multiplier)
            * (1 + price_sensitivity_weight
                   * price_sensitivity
                   * discount_bps / 10000)                [DISCOUNT_LOW, DISCOUNT_HIGH only]
            * scarcity_factor(context)                    [DISCOUNT_LOW, DISCOUNT_HIGH only]
            * (1 + loyalty_weight * loyalty)               [RECOMMEND, BUNDLE only]
            * (1 + category_affinity_weight
                   * category_affinity[context.category])
            * context.seasonal_multiplier
            * fatigue_penalty(traits, context.fatigue_counter, config)

    `archetype_base` supplies a per-archetype base coefficient from config (ENG-03: no business
    number is a code literal). The price-sensitivity term applies only to the two discount
    archetypes and scales with both the customer's `price_sensitivity` and the discount's own
    magnitude (`discount_bps` read from `params`); `scarcity_factor` damps that same pair when
    the targeted category's inventory has fallen to or below its configured low-stock threshold.
    The loyalty term applies only to `recommend` and `bundle`, which are retention-style nudges
    rather than price incentives. The category-affinity, seasonality, and fatigue-penalty terms
    apply to every non-`none` archetype.
    """
    if action_type is ActionType.NONE:
        return 1.0

    multiplier = config.response.archetype_base_multiplier[action_type.value]

    if action_type in _DISCOUNT_ACTIONS:
        discount_bps = int(params.get("discount_bps", 0))
        discount_magnitude = discount_bps / 10_000
        multiplier *= 1.0 + (
            config.response.price_sensitivity_weight * traits.price_sensitivity * discount_magnitude
        )
        multiplier *= _scarcity_factor(context)

    if action_type in _LOYALTY_ACTIONS:
        multiplier *= 1.0 + config.response.loyalty_weight * traits.loyalty

    category_affinity = traits.category_affinity.get(context.category, 0.0)
    multiplier *= 1.0 + config.response.category_affinity_weight * category_affinity

    multiplier *= context.seasonal_multiplier
    multiplier *= fatigue_penalty(traits, context.fatigue_counter, config)

    return multiplier


def base_conversion_probability(
    traits: LatentTraits, context: ResponseContext, config: SimulatorConfig
) -> float:
    """Baseline conversion probability before any action-specific effect is applied: the
    configured base rate scaled by this customer's affinity for the targeted category and the
    calendar's seasonal multiplier, clamped to `[0, 1]`."""
    affinity = traits.category_affinity.get(context.category, 0.0)
    probability = config.response.base_conversion_rate * (
        1.0 + config.response.category_affinity_weight * affinity
    )
    probability *= context.seasonal_multiplier
    return min(max(probability, 0.0), 1.0)


def ground_truth_uplift(
    traits: LatentTraits,
    action_type: ActionType,
    params: dict[str, str | int],
    context: ResponseContext,
    config: SimulatorConfig,
) -> float:
    """`P(convert|action) - P(convert|none)`, computed from `base_conversion_probability` and
    `response_multiplier` -- MODEL-06's uplift definition, computable for any `(customer,
    action)` pair without running the simulation. Returns exactly `0.0` for `ActionType.NONE`
    and is deterministic for a fixed customer, action, params and context.
    """
    if action_type is ActionType.NONE:
        return 0.0

    base = base_conversion_probability(traits, context, config)
    none_multiplier = response_multiplier(traits, ActionType.NONE, {}, context, config)
    action_multiplier = response_multiplier(traits, action_type, params, context, config)
    p_none = min(max(base * none_multiplier, 0.0), 1.0)
    p_action = min(max(base * action_multiplier, 0.0), 1.0)
    return p_action - p_none
