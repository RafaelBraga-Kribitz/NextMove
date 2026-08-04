"""Cross-cutting configuration infrastructure: layered YAML loading (base + profile
overlay), Pydantic validation of the merged result, and stable config hashing.

Infrastructure, not one of the eleven ENG-01 packages — sits below all of them in the
import graph so nothing creates a cycle. Populated by plan 01-03.
"""

from nextmove.config.models import (
    ActionsConfig,
    AutonomyConfig,
    CampaignConfig,
    CategoryConfig,
    Config,
    ConstraintsConfig,
    DataQualityConfig,
    ExperimentsConfig,
    FeaturesConfig,
    FeatureSpec,
    InventoryConfig,
    LatentTraitsConfig,
    LoopholeConfig,
    McdaConfig,
    MicroEventConfig,
    ResponseConfig,
    SeasonalityConfig,
    SeedsConfig,
    SimulatorConfig,
    StrictModel,
    TraitDistribution,
)

__all__: list[str] = [
    "ActionsConfig",
    "AutonomyConfig",
    "CampaignConfig",
    "CategoryConfig",
    "Config",
    "ConstraintsConfig",
    "DataQualityConfig",
    "ExperimentsConfig",
    "FeatureSpec",
    "FeaturesConfig",
    "InventoryConfig",
    "LatentTraitsConfig",
    "LoopholeConfig",
    "McdaConfig",
    "MicroEventConfig",
    "ResponseConfig",
    "SeasonalityConfig",
    "SeedsConfig",
    "SimulatorConfig",
    "StrictModel",
    "TraitDistribution",
]
