"""D-03's four latent traits, sampled once per customer from `config/simulator.yaml`.

Every simulated customer carries four latent traits that later action-response functions
(plan 01-08) read as inputs:

- **price_sensitivity** — drawn `beta(alpha, beta)`, natural support `[0, 1]`. A high value
  means a larger conversion-probability response to a discount and a smaller response to a
  non-price nudge (a free-shipping or urgency message moves this customer less than a price
  cut does).
- **loyalty** — drawn `beta(alpha, beta)`, natural support `[0, 1]`. A high value means a
  smaller marginal response to any acquisition-style incentive (this customer already
  converts at a high baseline rate) and a larger response to retention-style actions
  (loyalty-tier framing, early access).
- **fatigue_propensity** — drawn `lognormal(mu, sigma)`, whose mathematical support is
  `(0, inf)`. A high value means repeated contact (campaign exposures, action deliveries)
  suppresses this customer's response probability faster — each additional touch in a rolling
  window costs more expected conversion than it does for a low-fatigue customer (subject to
  D-04's documented loophole toggle).
- **category_affinity** — one raw value per configured category, drawn `normal(mu, sigma)`
  (mathematical support `(-inf, inf)`), then transformed into a `dict[str, float]` keyed by
  category name (see "Category affinity transform" below). A high value for a category means
  a larger baseline conversion probability and a larger response to actions targeting that
  category specifically.

**Bounding unbounded families.** `beta`'s support is genuinely `[0, 1]` for any valid
`alpha, beta > 0` — no truncation is needed or applied. `normal` and `lognormal` are
mathematically unbounded, which conflicts with this plan's own "yields a finite response
input" requirement and would make a "value outside the support is impossible by construction"
test either untestable (no finite boundary exists) or vacuously true (nothing is ever outside
an infinite support). This module resolves that by truncating every `normal`/`lognormal` draw
to a symmetric `_SUPPORT_SIGMA_MULTIPLE`-sigma window (6 sigma, `P(|Z| > 6) ≈ 2e-9` for a
standard normal, so truncation almost never actually clips a real draw) via `numpy.clip`
*after* sampling. `trait_support` computes that window from the distribution's own family and
params, so "the configured support" is always a concrete, finite `(min, max)` pair regardless
of family — including for `lognormal`, whose truncated lower bound is always strictly
positive, honoring its true mathematical floor of 0.

**Category affinity transform.** The four categories in `config/simulator.yaml` are drawn
from a single shared `normal(mu=0.0, sigma=1.0)` distribution, which can and does produce
negative raw values. A literal "divide each raw value by the sum of all raw values"
normalization is unsafe here: with a mean-zero distribution and as few as two categories, the
sum of raw values is negative or near-zero with non-trivial probability, which would either
divide by (near) zero or flip the sign of every component. This module instead applies a
softmax: `exp(raw_i) / sum(exp(raw_j) for all j)`. The denominator is a sum of strictly
positive terms, so it is always well-defined and strictly positive; every component is
therefore always in `(0, 1)` and the vector always sums to 1.0 (up to float rounding) by
construction, regardless of the sign or magnitude of the underlying raw draws. This is a
deliberate design choice beyond what CONTEXT.md/RESEARCH.md specify (RESEARCH Assumption A3
explicitly leaves distribution family and transform choice to the implementer) and is recorded
here, verbatim, for `docs/SIMULATOR_ASSUMPTIONS.md` (SIM-03, plan 01-11).

Each component is rounded half-to-even to 6 decimal places after normalization, so the value
is stable in Parquet bytes across reruns (RESEARCH Pitfall 3).
"""

import math

from numpy.random import Generator
from pydantic import BaseModel, ConfigDict, field_validator

from nextmove.config.models import CategoryConfig, SimulatorConfig, TraitDistribution
from nextmove.simulator.rng import SeedDomain, entity_rng

#: How many standard deviations either side of the mean an unbounded family (`normal`,
#: `lognormal`) is truncated to. `P(|Z| > 6) ≈ 2e-9` for a standard normal, so this almost
#: never actually clips a real draw while still giving every trait a concrete, finite,
#: testable support.
_SUPPORT_SIGMA_MULTIPLE = 6.0


def trait_support(dist: TraitDistribution) -> tuple[float, float]:
    """The concrete `(min, max)` a draw from `dist` can produce, inclusive of both endpoints.

    `beta` is `[0, 1]` for any valid params — its true mathematical support. `uniform` is
    `[low, high]` — its params directly are its support. `normal`/`lognormal` are truncated to
    a `_SUPPORT_SIGMA_MULTIPLE`-sigma window around their mean (see module docstring).
    """
    if dist.family == "beta":
        return (0.0, 1.0)
    if dist.family == "uniform":
        return (dist.params["low"], dist.params["high"])
    if dist.family == "normal":
        mu, sigma = dist.params["mu"], dist.params["sigma"]
        return (mu - _SUPPORT_SIGMA_MULTIPLE * sigma, mu + _SUPPORT_SIGMA_MULTIPLE * sigma)
    if dist.family == "lognormal":
        mu, sigma = dist.params["mu"], dist.params["sigma"]
        return (
            math.exp(mu - _SUPPORT_SIGMA_MULTIPLE * sigma),
            math.exp(mu + _SUPPORT_SIGMA_MULTIPLE * sigma),
        )
    raise ValueError(f"Unknown distribution family: {dist.family!r}")


def draw_trait_value(dist: TraitDistribution, rng: Generator) -> float:
    """Draw one scalar from `dist` using `rng`, clipped into `trait_support(dist)`.

    The clip is what makes "a value outside the configured support is impossible by
    construction" true for every family, including the mathematically unbounded ones.
    """
    if dist.family == "beta":
        raw = rng.beta(dist.params["alpha"], dist.params["beta"])
    elif dist.family == "uniform":
        raw = rng.uniform(dist.params["low"], dist.params["high"])
    elif dist.family == "normal":
        raw = rng.normal(dist.params["mu"], dist.params["sigma"])
    elif dist.family == "lognormal":
        raw = rng.lognormal(dist.params["mu"], dist.params["sigma"])
    else:
        raise ValueError(f"Unknown distribution family: {dist.family!r}")
    lo, hi = trait_support(dist)
    clipped = min(max(float(raw), lo), hi)
    return clipped


def _check_finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"latent trait value must be finite, got {value!r}")
    return value


class LatentTraits(BaseModel):
    """The four D-03 latent traits a simulated customer carries. Immutable once built; an
    unknown field fails loudly rather than being silently dropped."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    price_sensitivity: float
    loyalty: float
    fatigue_propensity: float
    category_affinity: dict[str, float]

    @field_validator("price_sensitivity", "loyalty", "fatigue_propensity", mode="after")
    @classmethod
    def _validate_scalar_finite(cls, value: float) -> float:
        return _check_finite(value)

    @field_validator("category_affinity", mode="after")
    @classmethod
    def _validate_affinity_finite(cls, value: dict[str, float]) -> dict[str, float]:
        for category_name, affinity in value.items():
            if not math.isfinite(affinity):
                raise ValueError(
                    f"category_affinity[{category_name!r}] must be finite, got {affinity!r}"
                )
        return value


def _softmax_normalize(raw_by_category: dict[str, float]) -> dict[str, float]:
    """Transform per-category raw draws into shares that are always positive and always sum
    to 1.0 (up to float rounding), regardless of the sign of the raw values. See the module
    docstring's "Category affinity transform" section for why this is necessary."""
    exp_values = {name: math.exp(value) for name, value in raw_by_category.items()}
    total = sum(exp_values.values())
    return {name: round(value / total, 6) for name, value in exp_values.items()}


def _sample_category_affinity(
    dist: TraitDistribution, categories: list[CategoryConfig], rng: Generator
) -> dict[str, float]:
    # Category order is the fixed, declared order categories appear in config — never a
    # `set` or a `dict`-derived order, which Python randomizes per process (module docstring
    # in `nextmove.simulator.rng`).
    raw_by_category = {category.name: draw_trait_value(dist, rng) for category in categories}
    return _softmax_normalize(raw_by_category)


def sample_latent_traits(customer_id: int, config: SimulatorConfig) -> LatentTraits:
    """Sample `customer_id`'s latent traits from `config.latent_traits`.

    Draws from exactly one `Generator` (obtained via `entity_rng(SeedDomain.world,
    customer_id, config.seeds)`), in a fixed order: price_sensitivity, loyalty, fatigue, then
    one category-affinity draw per category in config list order. Two calls with the same
    `customer_id` and `config` always return equal `LatentTraits`, regardless of what other
    customers were sampled before or after, or in what order (RESEARCH Pattern 1).
    """
    rng = entity_rng(SeedDomain.world, customer_id, config.seeds)
    price_sensitivity = draw_trait_value(config.latent_traits.price_sensitivity, rng)
    loyalty = draw_trait_value(config.latent_traits.loyalty, rng)
    fatigue_propensity = draw_trait_value(config.latent_traits.fatigue, rng)
    category_affinity = _sample_category_affinity(
        config.latent_traits.category_affinity, config.categories, rng
    )
    return LatentTraits(
        price_sensitivity=price_sensitivity,
        loyalty=loyalty,
        fatigue_propensity=fatigue_propensity,
        category_affinity=category_affinity,
    )
