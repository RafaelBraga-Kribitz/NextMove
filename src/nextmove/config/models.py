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


class EngagementConfig(StrictModel):
    """Daily organic session-occurrence and browse-depth parameters the daily tick's stage-3
    organic generation reads (plan 01-08, D-07 stage 3).

    Distinct from `ResponseConfig.base_conversion_rate`, which is the *response* function's
    base conversion probability once a session already exists -- this group governs whether,
    and how deeply, a customer browses on a given day at all. Added because no existing
    config group covers it and no such number may be a bare literal in `src/nextmove/`
    (ENG-03).
    """

    base_session_probability: float = Field(ge=0.0, le=1.0)
    min_views_per_session: int = Field(gt=0)
    max_views_per_session: int = Field(gt=0)
    add_to_cart_given_view_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_view_range(self) -> "EngagementConfig":
        if self.min_views_per_session > self.max_views_per_session:
            raise ValueError(
                "min_views_per_session must be <= max_views_per_session "
                f"(got {self.min_views_per_session} > {self.max_views_per_session})"
            )
        return self


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
    engagement: EngagementConfig
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
    # Plan 01-09: the monotonic-session-timestamps gate's cross-batch carry evicts an entry
    # once its last-seen timestamp is more than this many seconds behind the current batch's
    # watermark. Config, not a code constant, because it changes a gate's verdict (a longer
    # span means fewer evictions and therefore fewer violations) and ENG-04 requires anything
    # that can change output to sit inside the hashed config surface. Default matches D-07's
    # daily tick: a session in this world cannot legitimately span more than one day.
    session_max_span_seconds: int = Field(default=86400, gt=0)


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


class ActionVariant(StrictModel):
    """One concrete parameterization of an archetype. `suffix` names the variant inside its
    candidate id (`<archetype>__<suffix>`); an archetype with a single unnamed variant uses the
    bare archetype name as its id."""

    suffix: str | None = None
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ActionArchetype(StrictModel):
    """One ADR-010 archetype: whether it contacts the customer (and so counts toward frequency
    caps and fatigue), its per-send cost, and its small parameter grid."""

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    contact: bool
    cost_cents: int = Field(ge=0)
    variants: list[ActionVariant] = Field(min_length=1)

    @model_validator(mode="after")
    def _variant_suffixes_are_unique(self) -> "ActionArchetype":
        suffixes = [variant.suffix for variant in self.variants]
        if len(self.variants) > 1 and any(suffix is None for suffix in suffixes):
            raise ValueError(f"archetype {self.name!r}: every variant needs a suffix")
        if len(set(suffixes)) != len(suffixes):
            raise ValueError(f"archetype {self.name!r}: duplicate variant suffixes")
        return self


class ActionsConfig(StrictModel):
    """The ADR-010 action catalog (A3). `none` and `wait` are mandatory: restraint is a
    first-class action, so a catalog without them fails validation."""

    horizon_days: int = Field(gt=0)
    catalog: list[ActionArchetype]

    @model_validator(mode="after")
    def _restraint_present(self) -> "ActionsConfig":
        names = [archetype.name for archetype in self.catalog]
        if len(set(names)) != len(names):
            raise ValueError("action catalog archetype names must be unique")
        for required in ("none", "wait"):
            if required not in names:
                raise ValueError(f"action catalog must contain the {required!r} archetype")
        for archetype in self.catalog:
            if archetype.name in ("none", "wait") and archetype.contact:
                raise ValueError(f"{archetype.name!r} must not contact the customer")
        return self


class ConstraintSpec(StrictModel):
    """One configured constraint instance: which registered implementation, hard or soft,
    its precedence class (`compliance > inventory > campaign > preference`), and its params."""

    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    mode: Literal["hard", "soft"]
    precedence: Literal["compliance", "inventory", "campaign", "preference"]
    params: dict[str, float | int | str | list[str]] = Field(default_factory=dict)


class ConstraintsConfig(StrictModel):
    """Declarative constraint set (A4). Hard constraints remove candidates before ranking; soft
    constraints add a penalty (in cents) during ranking. The distinction is config, not code."""

    rules: list[ConstraintSpec]

    @model_validator(mode="after")
    def _names_unique(self) -> "ConstraintsConfig":
        names = [rule.name for rule in self.rules]
        if len(set(names)) != len(names):
            raise ValueError("constraint names must be unique")
        return self


class RulesOnlyPolicyConfig(StrictModel):
    """Thresholds of the hand-written CRM playbook baseline (A5). Feature names refer to
    feature-grid output columns."""

    cart_units_min: int = Field(ge=1)
    price_sensitivity_proxy_min: float = Field(ge=0.0)
    discount_candidate: str = Field(min_length=1)
    engaged_sessions_min: int = Field(ge=1)
    engaged_candidate: str = Field(min_length=1)
    lapsed_recency_days_min: int = Field(ge=1)
    lapsed_candidate: str = Field(min_length=1)


class ExpectedValuePolicyConfig(StrictModel):
    family: Literal["auto", "logistic", "gbm"]
    risk_aversion: float = Field(ge=0.0)
    min_confidence: float = Field(ge=0.0, le=1.0)
    interval_quantiles: tuple[float, float]

    @model_validator(mode="after")
    def _quantiles(self) -> "ExpectedValuePolicyConfig":
        low, high = self.interval_quantiles
        if not 0.0 <= low < high <= 1.0:
            raise ValueError("interval_quantiles must satisfy 0 <= low < high <= 1")
        return self


class BaselinesConfig(StrictModel):
    top_seller_candidate: str = Field(min_length=1)
    rules_only: RulesOnlyPolicyConfig


class PoliciesConfig(StrictModel):
    """Policy-level settings: the baselines (A5); the expected-value policy's utility weights
    are added with the decision engine (C1)."""

    baselines: BaselinesConfig
    expected_value: ExpectedValuePolicyConfig


class EvaluationSeeds(StrictModel):
    experiment: int
    outcomes: int
    bootstrap: int
    models: int


class EvaluationConfig(StrictModel):
    """Temporal design of the simulated evaluation (ADR-012). Windows are fractions of the
    simulated horizon so every profile gets the same train / validation / test shape:
    `[warmup, train_end)` randomized experiment for training, `[train_end, validation_end)`
    randomized experiment for calibration and model selection, `[validation_end, horizon)`
    the held-out replay window every policy is compared on."""

    warmup_days: int = Field(ge=1)
    train_end_fraction: float = Field(gt=0.0, lt=1.0)
    validation_end_fraction: float = Field(gt=0.0, lt=1.0)
    experiment_every_days: int = Field(ge=1)
    replay_every_days: int = Field(ge=1)
    bootstrap_resamples: int = Field(ge=100)
    ci_level: float = Field(gt=0.5, lt=1.0)
    seeds: EvaluationSeeds

    @model_validator(mode="after")
    def _ordered(self) -> "EvaluationConfig":
        if self.train_end_fraction >= self.validation_end_fraction:
            raise ValueError("train_end_fraction must be < validation_end_fraction")
        return self

    def windows(self, horizon_days: int) -> tuple[int, int, int]:
        """(train_end_day, validation_end_day, horizon_days)."""
        train_end = max(self.warmup_days + 1, int(horizon_days * self.train_end_fraction))
        validation_end = max(train_end + 1, int(horizon_days * self.validation_end_fraction))
        return train_end, min(validation_end, horizon_days - 1), horizon_days


class LogisticConfig(StrictModel):
    C: float = Field(gt=0.0)
    max_iter: int = Field(gt=0)


class GbmConfig(StrictModel):
    n_estimators: int = Field(gt=0)
    learning_rate: float = Field(gt=0.0)
    num_leaves: int = Field(ge=2)
    min_child_samples: int = Field(ge=1)
    subsample: float = Field(gt=0.0, le=1.0)
    colsample_bytree: float = Field(gt=0.0, le=1.0)
    reg_lambda: float = Field(ge=0.0)


class CalibrationConfig(StrictModel):
    max_ece: float = Field(gt=0.0, lt=1.0)
    reliability_bins: int = Field(ge=2)


class ModelsConfig(StrictModel):
    ensemble_size: int = Field(ge=2)
    logistic: LogisticConfig
    gbm: GbmConfig
    calibration: CalibrationConfig
    attribution_top_k: int = Field(ge=1)


class McdaCriterion(StrictModel):
    weight: float = Field(gt=0.0)
    direction: Literal["benefit", "cost"]


class SegmentationConfig(StrictModel):
    features: list[str] = Field(min_length=1)
    kmeans_k: list[int] = Field(min_length=1)
    min_segment_share: float = Field(gt=0.0, lt=1.0)
    max_segments: int = Field(ge=2)
    stability_resamples: int = Field(ge=2)
    sensitivity_factor: float = Field(gt=0.0, lt=1.0)
    interpretability: dict[str, float]


class McdaConfig(StrictModel):
    """MCDA criteria and weights for segmentation method selection (AC-7)."""

    criteria: dict[str, McdaCriterion]
    segmentation: SegmentationConfig


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
    constraints: ConstraintsConfig
    actions: ActionsConfig
    mcda: McdaConfig
    experiments: ExperimentsConfig = Field(default_factory=ExperimentsConfig)
    autonomy: AutonomyConfig
    policies: PoliciesConfig
    evaluation: EvaluationConfig
    models: ModelsConfig
