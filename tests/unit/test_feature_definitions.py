"""Covers every `must_haves.truths` / behavior-block item for plan 01-10 Task 1: the
config-driven feature set, the transform registry, and `FEATURE_SET_VERSION`.
"""

from __future__ import annotations

import pytest

from nextmove.config.loader import load_config
from nextmove.config.models import FeaturesConfig, FeatureSpec
from nextmove.features.definitions import (
    FEATURE_SET_VERSION,
    FEATURE_TRANSFORMS,
    FeatureTransform,
    _compute_feature_set_version,
    register_transform,
    resolve_feature_set,
)


@pytest.fixture(scope="module")
def features_config() -> FeaturesConfig:
    return load_config("tiny").config.features


def test_at_least_twelve_transforms_registered() -> None:
    assert len(FEATURE_TRANSFORMS) >= 12


def test_every_registered_transform_declares_output_column_dtype_and_empty_default() -> None:
    for name, transform in FEATURE_TRANSFORMS.items():
        assert transform.output_column, name
        assert transform.dtype, name
        # empty_default may legitimately be None (rfm_recency), 0, 0.0, or a JSON string --
        # the pinned check is that it was *set*, not that it is truthy.
        assert "empty_default" in transform.model_fields_set or transform.empty_default is None


def test_resolve_feature_set_matches_config_declared_names_and_order(
    features_config: FeaturesConfig,
) -> None:
    resolved = resolve_feature_set(features_config)
    assert [t.name for t in resolved] == [spec.name for spec in features_config.features]


def test_resolve_feature_set_respects_reordering(features_config: FeaturesConfig) -> None:
    reordered = FeaturesConfig(
        grid_frequency=features_config.grid_frequency,
        lookback_days=features_config.lookback_days,
        features=list(reversed(features_config.features)),
    )
    resolved = resolve_feature_set(reordered)
    assert [t.name for t in resolved] == [spec.name for spec in reordered.features]
    assert [t.name for t in resolved] != [spec.name for spec in features_config.features]


def test_resolve_feature_set_raises_key_error_naming_unregistered_spec(
    features_config: FeaturesConfig,
) -> None:
    bad_config = FeaturesConfig(
        grid_frequency=features_config.grid_frequency,
        lookback_days=features_config.lookback_days,
        features=[
            *features_config.features,
            FeatureSpec(name="not_a_real_feature", kind="numeric", params={}),
        ],
    )
    with pytest.raises(KeyError, match="not_a_real_feature"):
        resolve_feature_set(bad_config)


def test_register_transform_raises_on_duplicate_name() -> None:
    def _factory() -> FeatureTransform:
        return FeatureTransform(
            name="rfm_recency",
            output_column="dup_column",
            dtype="int64",
            empty_default=0,
            window_days=None,
            sql_expression="(SELECT 1)",
        )

    with pytest.raises(ValueError, match="rfm_recency"):
        register_transform(_factory)


def test_feature_set_version_is_stable_across_two_calls(features_config: FeaturesConfig) -> None:
    resolved = resolve_feature_set(features_config)
    first = _compute_feature_set_version(resolved)
    second = _compute_feature_set_version(resolved)
    assert first == second


def test_feature_set_version_changes_when_a_sql_expression_changes(
    features_config: FeaturesConfig,
) -> None:
    resolved = resolve_feature_set(features_config)
    baseline = _compute_feature_set_version(resolved)

    mutated = list(resolved)
    original = mutated[0]
    mutated[0] = original.model_copy(update={"sql_expression": original.sql_expression + " -- x"})
    changed = _compute_feature_set_version(mutated)

    assert changed != baseline


def test_module_level_feature_set_version_matches_full_registry_recompute() -> None:
    full_set = sorted(FEATURE_TRANSFORMS.values(), key=lambda t: t.name)
    assert FEATURE_SET_VERSION == _compute_feature_set_version(full_set)


def test_no_case_folding_in_definitions_module() -> None:
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[2] / "src/nextmove/features/definitions.py"
    ).read_text()
    assert "NFC" in source
    assert source.lower().count("lower()") == 0
