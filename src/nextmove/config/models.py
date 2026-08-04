"""Pydantic v2 config schema for every domain Phase 1 (and later phases) steer through YAML.

Every model inherits from `StrictModel`, which sets `extra="forbid"` — the load-bearing
setting that turns a typo'd or malicious config key into a loud `ValidationError` instead of
a silently ignored one (RESEARCH Security Domain, threat T-01-07). Models are also `frozen`
so a resolved `Config` cannot be mutated after validation, and `validate_default=True` so
default values go through the same validators as YAML-sourced ones.

No business number lives as a bare literal in `src/nextmove/`; every field below is populated
from `config/*.yaml` by `nextmove.config.loader.load_config` (ENG-03).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Shared base: unknown keys fail loudly, instances are immutable once validated."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


# ---------------------------------------------------------------------------------------
# Seeds (D-25: seeds are config values inside the hashed surface, never CLI flags)
# ---------------------------------------------------------------------------------------


class SeedsConfig(StrictModel):
    """Four independent integer seeds, one per stochastic subsystem."""

    world: int
    organic: int
    response: int
    campaign: int


# ---------------------------------------------------------------------------------------
# Latent traits (D-03: action-response functions are latent-trait driven)
# ---------------------------------------------------------------------------------------

_TRAIT_REQUIRED_PARAMS: dict[str, frozenset[str]] = {
    "beta": frozenset({"alpha", "beta"}),
    "lognormal": frozenset({"mu", "sigma"}),
    "normal": frozenset({"mu", "sigma"}),
    "uniform": frozenset({"low", "high"}),
}


class TraitDistribution(StrictModel):
    """A named parametric distribution plus the params that family requires."""

    family: Literal["beta", "lognormal", "uniform", "normal"]
    params: dict[str, float]

    @model_validator(mode="after")
    def _check_required_params(self) -> "TraitDistribution":
        required = _TRAIT_REQUIRED_PARAMS[self.family]
        missing = required - self.params.keys()
        if missing:
            raise ValueError(
                f"TraitDistribution family {self.family!r} is missing required params: "
                f"{sorted(missing)}"
            )
        return self


class LatentTraitsConfig(StrictModel):
    """The four D-03 latent traits every simulated customer carries."""

    price_sensitivity: TraitDistribution
    loyalty: TraitDistribution
    fatigue: TraitDistribution
    category_affinity: TraitDistribution


# ---------------------------------------------------------------------------------------
# Categories and seasonality (D-01: fashion-core plus one low-seasonality contrast category)
# ---------------------------------------------------------------------------------------


class CategoryConfig(StrictModel):
    """One product category. Prices are integer minor units (cents) — never floats — so no
    monetary value can drift in Parquet bytes between runs. `margin_rate` is the only float.
    """

    name: str
    seasonality_class: Literal["high", "low"]
    sku_count: int = Field(gt=0)
    base_price_cents_min: int = Field(ge=0)
    base_price_cents_max: int = Field(ge=0)
    margin_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_price_range(self) -> "CategoryConfig":
        if self.base_price_cents_min > self.base_price_cents_max:
            raise ValueError(
                "base_price_cents_min must be <= base_price_cents_max "
                f"(got {self.base_price_cents_min} > {self.base_price_cents_max})"
            )
        return self


class SeasonalityConfig(StrictModel):
    """Twelve monthly multipliers plus the declared peak month.

    `low_class_amplitude_factor` is what makes the low-seasonality contrast category
    genuinely flatter (D-01) rather than merely relabeled: a `low`-class category's monthly
    multiplier is the same curve shape as `monthly_multipliers`, damped toward 1.0 by this
    factor, so its peak-to-trough ratio is provably smaller than a `high`-class category's
    (plan 01-07 `World.seasonal_multiplier_for_class`).
    """

    monthly_multipliers: list[float]
    peak_month: int = Field(ge=1, le=12)
    low_class_amplitude_factor: float = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _check_twelve_months(self) -> "SeasonalityConfig":
        if len(self.monthly_multipliers) != 12:
            raise ValueError(
                "monthly_multipliers must have exactly 12 entries, got "
                f"{len(self.monthly_multipliers)}"
            )
        return self


# ---------------------------------------------------------------------------------------
# World mechanics
# ---------------------------------------------------------------------------------------


class InventoryConfig(StrictModel):
    initial_stock_per_sku: int = Field(gt=0)
    low_stock_threshold: int = Field(ge=0)
    restock_probability_per_day: float = Field(ge=0.0, le=1.0)


class CampaignConfig(StrictModel):
    """`discount_bps_min`/`discount_bps_max` bound the discount (in basis points, 1/100 of a
    percent) a generated campaign offers — the same "min/max range in config, never a bare
    literal in code" pattern `CategoryConfig` uses for price bands (ENG-03)."""

    channels: list[str]
    frequency_cap_per_week: int = Field(ge=0)
    send_probability_per_eligible_day: float = Field(ge=0.0, le=1.0)
    discount_bps_min: int = Field(ge=0, le=10_000)
    discount_bps_max: int = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def _check_discount_range(self) -> "CampaignConfig":
        if self.discount_bps_min > self.discount_bps_max:
            raise ValueError(
                "discount_bps_min must be <= discount_bps_max "
                f"(got {self.discount_bps_min} > {self.discount_bps_max})"
            )
        return self


class MicroEventConfig(StrictModel):
    """Rates and dwell-class boundaries for the scroll / filter / dwell events SIM-04
    requires."""

    scroll_rate: float = Field(ge=0.0, le=1.0)
    filter_rate: float = Field(ge=0.0, le=1.0)
    dwell_short_seconds_max: float = Field(gt=0.0)
    dwell_medium_seconds_max: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _check_dwell_ordering(self) -> "MicroEventConfig":
        if self.dwell_short_seconds_max >= self.dwell_medium_seconds_max:
            raise ValueError(
                "dwell_short_seconds_max must be strictly less than dwell_medium_seconds_max "
                f"(got {self.dwell_short_seconds_max} >= {self.dwell_medium_seconds_max})"
            )
        return self


# The seven non-`none` DEC-03 action archetypes `response.archetype_base_multiplier` must
# cover, duplicated here as plain strings rather than imported from
# `nextmove.simulator.response.ActionType` because `nextmove.simulator` already imports
# `nextmove.config.models` (traits.py, world.py) -- importing back would close a cycle.
# `ActionType` is the canonical source; this set is a plain-string mirror kept in sync with
# it by hand.
_RESPONSE_ARCHETYPES: frozenset[str] = frozenset(
    {"wait", "recommend", "bundle", "discount_low", "discount_high", "email_now", "email_delayed"}
)


class ResponseConfig(StrictModel):
    """Coefficients of the documented action-response functions (D-03).

    `archetype_base_multiplier` gives `response_multiplier` (plan 01-08) a per-archetype base
    coefficient read from config rather than a code literal (ENG-03): `none` always returns
    the identity multiplier `1.0` by construction and is deliberately excluded from this map.
    """

    base_conversion_rate: float = Field(ge=0.0, le=1.0)
    price_sensitivity_weight: float
    loyalty_weight: float
    fatigue_penalty_weight: float
    category_affinity_weight: float
    archetype_base_multiplier: dict[str, float]

    @model_validator(mode="after")
    def _check_archetype_coverage(self) -> "ResponseConfig":
        keys = set(self.archetype_base_multiplier)
        missing = _RESPONSE_ARCHETYPES - keys
        extra = keys - _RESPONSE_ARCHETYPES
        if missing or extra:
            raise ValueError(
                "archetype_base_multiplier must declare exactly one base coefficient for "
                f"each non-none action archetype {sorted(_RESPONSE_ARCHETYPES)!r}; missing "
                f"{sorted(missing)!r}, unexpected {sorted(extra)!r}"
            )
        return self


class LoopholeConfig(StrictModel):
    """D-04's deliberate, documented reward-hacking loophole.

    When `fatigue_penalty_enabled` is False, the simulator's response function stops
    penalizing repeated contact for fatigued customers. This is not a bug: it exists so the
    mandated reward-hacking probe (arriving with the v2 contextual bandit) has a genuine
    exploit to find. Phase 1 ships the loophole; it does not ship the probe.
    """

    fatigue_penalty_enabled: bool = True


class SimulatorConfig(StrictModel):
    """Every world parameter the daily-tick simulator reads (D-07)."""

    start_date: date
    horizon_days: int = Field(gt=0)
    n_customers: int = Field(gt=0)
    categories: list[CategoryConfig]
    latent_traits: LatentTraitsConfig
    seasonality: SeasonalityConfig
    inventory: InventoryConfig
    campaigns: CampaignConfig
    micro_events: MicroEventConfig
    response: ResponseConfig
    loophole: LoopholeConfig
    seeds: SeedsConfig
    # The cadence, in ticks, at which run.py materializes a ground_truth_uplift snapshot row
    # per (customer, action_type). A schema-validated config value rather than a module
    # constant: changing it legitimately changes the shipped table's bytes, and ENG-04's
    # lineage row can only account for a change that sits inside the hashed config surface
    # (review MEDIUM-3).
    uplift_snapshot_every_ticks: int = Field(gt=0, default=30)


# ---------------------------------------------------------------------------------------
# Features (D-19: daily grid; FEAT-01's feature families)
# ---------------------------------------------------------------------------------------


class FeatureSpec(StrictModel):
    """One named feature the daily grid materializes."""

    name: str
    kind: str
    params: dict[str, float | int | str] = Field(default_factory=dict)


class FeaturesConfig(StrictModel):
    grid_frequency: Literal["daily"]
    lookback_days: int = Field(gt=0)
    features: list[FeatureSpec]


# ---------------------------------------------------------------------------------------
# Data quality (D-20/D-21: quarantine + configurable reject-rate threshold)
# ---------------------------------------------------------------------------------------


class DataQualityConfig(StrictModel):
    max_reject_rate: float = Field(default=0.001, ge=0.0, le=1.0)
    fail_run_on_exceed: bool = True
    semantic_gates: list[str]


# ---------------------------------------------------------------------------------------
# Autonomy tiers (D-12 / OD-9)
# ---------------------------------------------------------------------------------------


class AutonomyConfig(StrictModel):
    """The three D-12 autonomy tiers. Membership lists must be pairwise disjoint — a change
    type belongs to exactly one tier, never two."""

    tier_1_auto: list[str]
    tier_2_human_signoff: list[str]
    tier_3_human_only: list[str]

    @model_validator(mode="after")
    def _check_disjoint(self) -> "AutonomyConfig":
        tiers = {
            "tier_1_auto": self.tier_1_auto,
            "tier_2_human_signoff": self.tier_2_human_signoff,
            "tier_3_human_only": self.tier_3_human_only,
        }
        seen: dict[str, str] = {}
        for tier_name, members in tiers.items():
            for member in members:
                owner = seen.get(member)
                if owner is not None:
                    raise ValueError(
                        f"change type {member!r} appears in both {owner!r} and "
                        f"{tier_name!r} — autonomy tiers must be pairwise disjoint"
                    )
                seen[member] = tier_name
        return self


# ---------------------------------------------------------------------------------------
# Minimal domains later phases populate. Still `extra="forbid"` (via StrictModel) so a
# Phase 2/3/4 typo fails immediately once these grow real fields.
# ---------------------------------------------------------------------------------------


class ConstraintsConfig(StrictModel):
    """Populated by Phase 2: eligibility, frequency caps, inventory gates, discount
    ceilings, brand safety. Empty and schema-locked until then."""


class ActionsConfig(StrictModel):
    """Populated by Phase 2: the action catalog. Empty and schema-locked until then."""


class McdaConfig(StrictModel):
    """Populated by Phase 4: MCDA criteria and weights for segmentation method selection.
    Empty and schema-locked until then."""


class ExperimentsConfig(StrictModel):
    """Populated by Phase 3: 3WD thresholds (MDE, indifference margin, delay budget).
    Empty and schema-locked until then."""


# ---------------------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------------------


class Config(StrictModel):
    """The full resolved config: one field per domain, plus the resolved profile name.

    `nextmove.config.loader.load_config` is the only supported way to build one — it
    performs the layered merge (D-23) before handing the result to
    `Config.model_validate` (D-24).
    """

    profile: str
    simulator: SimulatorConfig
    features: FeaturesConfig
    data_quality: DataQualityConfig
    constraints: ConstraintsConfig = Field(default_factory=ConstraintsConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)
    mcda: McdaConfig = Field(default_factory=McdaConfig)
    experiments: ExperimentsConfig = Field(default_factory=ExperimentsConfig)
    autonomy: AutonomyConfig
