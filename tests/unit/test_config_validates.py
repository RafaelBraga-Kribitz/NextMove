"""Validates the real repository config/ tree: all four profiles load and validate, hash
distinctly and stably, autonomy tiers stay disjoint, and profile overlays stay thin (D-23).

Unlike test_config_merge_hash.py, this file deliberately depends on the repository's real
config/ tree -- that is what it exists to guard.
"""

from pathlib import Path

import pytest

from nextmove.config.loader import load_config

PROFILE_NAMES = ["default", "demo", "ci", "tiny"]


@pytest.fixture
def config_dir(repo_root: Path) -> Path:
    return repo_root / "config"


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_each_profile_loads_and_validates(profile: str, config_dir: Path) -> None:
    resolved = load_config(profile, config_dir=config_dir)
    assert resolved.profile == profile
    assert resolved.config.profile == profile


def test_all_four_profiles_produce_distinct_hashes(config_dir: Path) -> None:
    hashes = {p: load_config(p, config_dir=config_dir).config_hash for p in PROFILE_NAMES}
    assert len(set(hashes.values())) == len(PROFILE_NAMES), hashes


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_loading_the_same_profile_twice_yields_the_same_hash(
    profile: str, config_dir: Path
) -> None:
    first = load_config(profile, config_dir=config_dir)
    second = load_config(profile, config_dir=config_dir)
    assert first.config_hash == second.config_hash


@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_autonomy_tiers_are_pairwise_disjoint_as_loaded(profile: str, config_dir: Path) -> None:
    autonomy = load_config(profile, config_dir=config_dir).config.autonomy
    tier_1 = set(autonomy.tier_1_auto)
    tier_2 = set(autonomy.tier_2_human_signoff)
    tier_3 = set(autonomy.tier_3_human_only)
    assert not (tier_1 & tier_2)
    assert not (tier_1 & tier_3)
    assert not (tier_2 & tier_3)


def test_each_profile_overlay_file_is_a_thin_diff(config_dir: Path) -> None:
    """Mechanical expression of "thin overlay, not a duplicated tree" (D-23): each profile
    overlay has fewer than 15 non-blank lines."""
    for profile in PROFILE_NAMES:
        overlay_path = config_dir / "profiles" / f"{profile}.yaml"
        non_blank_lines = [line for line in overlay_path.read_text().splitlines() if line.strip()]
        assert len(non_blank_lines) < 15, (
            f"{overlay_path} has {len(non_blank_lines)} non-blank lines, expected < 15"
        )


def test_tiny_profile_name_fixture_matches_repo_config(
    tiny_profile_name: str, config_dir: Path
) -> None:
    """The tiny_profile_name fixture in tests/conftest.py names a profile this plan adds."""
    resolved = load_config(tiny_profile_name, config_dir=config_dir)
    assert resolved.config.simulator.n_customers < 500
