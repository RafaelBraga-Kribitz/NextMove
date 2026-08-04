"""Merge semantics and hash-stability assertions for `nextmove.config.loader`.

Uses inline YAML written into `tmp_path` throughout — deliberately does not depend on the
repository's real `config/` tree (Task 3 in plan 01-03 owns that; see
`test_config_validates.py`).
"""

import copy

import pytest
import yaml
from pydantic import ValidationError

from nextmove.config.loader import BASE_DOMAIN_FILES, deep_merge, load_config
from nextmove.config.loader import config_hash as compute_config_hash
from nextmove.config.models import Config

# ---------------------------------------------------------------------------------------
# A minimal, fully valid config tree — every field the eight domain models require.
# ---------------------------------------------------------------------------------------

SIMULATOR_YAML = """
simulator:
  start_date: "2024-01-01"
  horizon_days: 30
  n_customers: 100
  categories:
    - name: fashion
      seasonality_class: high
      sku_count: 10
      base_price_cents_min: 1000
      base_price_cents_max: 5000
      margin_rate: 0.4
    - name: basics
      seasonality_class: low
      sku_count: 5
      base_price_cents_min: 500
      base_price_cents_max: 1500
      margin_rate: 0.3
  latent_traits:
    price_sensitivity:
      family: beta
      params: {alpha: 2.0, beta: 5.0}
    loyalty:
      family: beta
      params: {alpha: 2.0, beta: 5.0}
    fatigue:
      family: uniform
      params: {low: 0.0, high: 1.0}
    category_affinity:
      family: normal
      params: {mu: 0.0, sigma: 1.0}
  seasonality:
    monthly_multipliers: [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.0, 1.3, 2.0]
    peak_month: 12
  inventory:
    initial_stock_per_sku: 100
    low_stock_threshold: 10
    restock_probability_per_day: 0.1
  campaigns:
    channels: [email]
    frequency_cap_per_week: 2
    send_probability_per_eligible_day: 0.2
  micro_events:
    scroll_rate: 0.5
    filter_rate: 0.2
    dwell_short_seconds_max: 5.0
    dwell_medium_seconds_max: 30.0
  response:
    base_conversion_rate: 0.05
    price_sensitivity_weight: 0.3
    loyalty_weight: 0.2
    fatigue_penalty_weight: 0.1
    category_affinity_weight: 0.2
  loophole:
    fatigue_penalty_enabled: true
  seeds:
    world: 1
    organic: 2
    response: 3
    campaign: 4
"""

FEATURES_YAML = """
features:
  grid_frequency: daily
  lookback_days: 30
  features:
    - name: rfm_recency
      kind: numeric
"""

DATA_QUALITY_YAML = """
data_quality:
  max_reject_rate: 0.001
  fail_run_on_exceed: true
  semantic_gates: [non_negative_price]
"""

AUTONOMY_YAML = """
autonomy:
  tier_1_auto: [variant_assignment]
  tier_2_human_signoff: [model_promotion]
  tier_3_human_only: [discount_ceiling_change]
"""

# Constraints/actions/mcda/experiments are minimal — comment-only, populated by later
# phases. `yaml.safe_load` on a comments-only file returns None, treated as `{}`.
EMPTY_DOMAIN_YAML = "# populated by a later phase\n"


def _write_domain_files(config_dir) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "simulator.yaml").write_text(SIMULATOR_YAML)
    (config_dir / "features.yaml").write_text(FEATURES_YAML)
    (config_dir / "data_quality.yaml").write_text(DATA_QUALITY_YAML)
    (config_dir / "constraints.yaml").write_text(EMPTY_DOMAIN_YAML)
    (config_dir / "actions.yaml").write_text(EMPTY_DOMAIN_YAML)
    (config_dir / "mcda.yaml").write_text(EMPTY_DOMAIN_YAML)
    (config_dir / "experiments.yaml").write_text(EMPTY_DOMAIN_YAML)
    (config_dir / "autonomy.yaml").write_text(AUTONOMY_YAML)
    profiles_dir = config_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    (profiles_dir / "base.yaml").write_text("# base profile: no overrides\n")


@pytest.fixture
def config_tree(tmp_path):
    """A minimal, fully valid config tree under tmp_path with a no-op 'base' profile."""
    _write_domain_files(tmp_path)
    return tmp_path


# A full valid Config-shaped dict, built directly in Python (not via YAML), for the
# dict-level key-order test below.
def _valid_config_dict() -> dict:
    return yaml.safe_load(SIMULATOR_YAML + FEATURES_YAML + DATA_QUALITY_YAML + AUTONOMY_YAML) | {
        "profile": "base"
    }


# ---------------------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------------------


def test_deep_merge_overlay_wins_per_key_and_recurses() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    overlay = {"a": 2, "nested": {"y": 20, "z": 3}}
    merged = deep_merge(base, overlay)
    assert merged == {"a": 2, "nested": {"x": 1, "y": 20, "z": 3}}


def test_deep_merge_does_not_mutate_either_argument() -> None:
    base = {"a": {"x": 1}}
    overlay = {"a": {"y": 2}}
    base_before = copy.deepcopy(base)
    overlay_before = copy.deepcopy(overlay)

    deep_merge(base, overlay)

    assert base == base_before
    assert overlay == overlay_before


def test_deep_merge_identical_overlay_value_equals_base() -> None:
    base = {"a": {"b": 1, "c": 2}}
    overlay = {"a": {"b": 1}}
    merged = deep_merge(base, overlay)
    assert merged == base


def test_reversed_key_insertion_order_produces_same_hash() -> None:
    """A config dict whose keys are inserted in reverse order hashes identically to the
    forward-order dict (Pitfall 3: dict key order must never affect the hash)."""
    forward = _valid_config_dict()
    reversed_top = dict(reversed(list(forward.items())))
    reversed_top["simulator"] = dict(reversed(list(forward["simulator"].items())))

    forward_config = Config.model_validate(forward)
    reversed_config = Config.model_validate(reversed_top)

    assert compute_config_hash(forward_config) == compute_config_hash(reversed_config)


# ---------------------------------------------------------------------------------------
# load_config / config_hash, via a real (tmp_path) config tree
# ---------------------------------------------------------------------------------------


def test_empty_overlay_yields_base_unchanged_and_identical_hash(config_tree) -> None:
    """`config_tree`'s 'base' profile overlay is comment-only (empty). The result must
    equal — and hash identically to — validating the eight base domain files directly with
    no overlay merge applied at all, under the same profile name."""
    resolved = load_config("base", config_dir=config_tree)

    base_only: dict = {}
    for domain in BASE_DOMAIN_FILES:
        data = yaml.safe_load((config_tree / f"{domain}.yaml").read_text()) or {}
        base_only = deep_merge(base_only, data)
    base_only["profile"] = "base"
    base_only_config = Config.model_validate(base_only)

    assert resolved.config.model_dump(mode="json") == base_only_config.model_dump(mode="json")
    assert resolved.config_hash == compute_config_hash(base_only_config)


def test_key_order_in_yaml_does_not_change_hash(tmp_path) -> None:
    """Two on-disk config trees with logically identical content, but a simulator.yaml
    whose nested keys are declared in a different order, hash identically."""
    forward_dir = tmp_path / "forward"
    _write_domain_files(forward_dir)

    reversed_dir = tmp_path / "reversed"
    _write_domain_files(reversed_dir)
    forward_simulator = yaml.safe_load(SIMULATOR_YAML)
    reversed_simulator = {"simulator": dict(reversed(list(forward_simulator["simulator"].items())))}
    (reversed_dir / "simulator.yaml").write_text(yaml.safe_dump(reversed_simulator))

    forward_resolved = load_config("base", config_dir=forward_dir)
    reversed_resolved = load_config("base", config_dir=reversed_dir)

    assert forward_resolved.config_hash == reversed_resolved.config_hash


def test_load_config_unknown_profile_raises_naming_it(config_tree) -> None:
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        load_config("nonexistent", config_dir=config_tree)


def test_overlay_undeclared_key_raises_validation_error_naming_it(config_tree) -> None:
    (config_tree / "profiles" / "bad.yaml").write_text(
        "simulator:\n  totally_undeclared_field: 1\n"
    )
    with pytest.raises(ValidationError, match="totally_undeclared_field"):
        load_config("bad", config_dir=config_tree)


def test_config_hash_is_64_char_lowercase_hex(config_tree) -> None:
    resolved = load_config("base", config_dir=config_tree)
    assert len(resolved.config_hash) == 64
    assert resolved.config_hash == resolved.config_hash.lower()
    int(resolved.config_hash, 16)  # raises ValueError if not valid hex


def test_load_config_returns_source_files_including_profile(config_tree) -> None:
    resolved = load_config("base", config_dir=config_tree)
    assert (config_tree / "profiles" / "base.yaml") in resolved.source_files
    assert len(resolved.source_files) == 9  # eight base domain files + one profile overlay


def test_profile_path_traversal_is_rejected_not_read_outside_config_dir(config_tree) -> None:
    with pytest.raises(ValueError, match="outside the config directory"):
        load_config("../../../../../../etc/passwd", config_dir=config_tree)
