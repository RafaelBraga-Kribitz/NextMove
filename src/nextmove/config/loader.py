"""Layered config resolution: deep merge, profile overlay, validation, and canonical hash.

D-23: per-domain base files plus thin profile overlays, overlay wins per key. D-24: Pydantic
validates the *merged* result and the config hash is taken over that resolved merge, so a
run's hash captures exactly what it ran with. Every YAML file is parsed with `yaml.safe_load`
and never the default full loader (T-01-05): the full loader can instantiate arbitrary Python
objects from a crafted config file.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from nextmove.config.models import Config

# The eight D-23 per-domain base files, read in this fixed order and merged onto one
# accumulator. Each file wraps its own content under its own top-level key (e.g.
# `simulator.yaml` under `simulator:`), so domain files cannot collide with one another.
BASE_DOMAIN_FILES: tuple[str, ...] = (
    "simulator",
    "features",
    "data_quality",
    "constraints",
    "actions",
    "mcda",
    "experiments",
    "autonomy",
)

# Default config tree: <repo_root>/config. loader.py lives at
# src/nextmove/config/loader.py, so four `.parent`s up from the resolved file path is the
# repository root.
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge `overlay` onto `base`; overlay wins per key (D-23's "override only
    what differs"). Neither input is mutated: a new dict is returned at every level.

    Nested dicts merge recursively. Any other overlay value — including a list — replaces
    the base value outright; list concatenation would silently change list-valued config
    semantics (e.g. `categories`) in a way "override only what differs" does not intend.
    """
    merged = dict(base)
    for key, overlay_value in overlay.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(overlay_value, dict):
            merged[key] = deep_merge(base_value, overlay_value)
        else:
            merged[key] = overlay_value
    return merged


@dataclass(frozen=True)
class ResolvedConfig:
    """The outcome of `load_config`: a validated `Config` plus the provenance that produced
    it."""

    config: Config
    config_hash: str
    profile: str
    source_files: tuple[Path, ...]


def config_hash(config: Config) -> str:
    """Stable sha256 hash over the resolved, validated config.

    Canonicalized as sorted-key, separator-tight JSON of `model_dump(mode="json")` — this is
    what makes the hash immune to YAML key order and dict insertion order (Pitfall 3: float
    formatting and key order are the two documented hash-instability sources); `mode="json"`
    gives dates and enums one stable string form. No wall-clock value may ever enter the
    hashed surface: only fields declared on the `Config` model tree are dumped, and none of
    them is a timestamp.
    """
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_config(profile: str, config_dir: Path | None = None) -> ResolvedConfig:
    """Resolve, validate, and hash the layered config for `profile`.

    Reads the eight `BASE_DOMAIN_FILES` under `config_dir` in their fixed declared order,
    deep-merging each onto an accumulator, then deep-merges the profile overlay
    (`config_dir/profiles/{profile}.yaml`) over that base. A file that parses to `None`
    (empty, or comments-only) is treated as `{}`.

    `config_dir` is resolved to an absolute path and the resolved profile file path is
    asserted to be a descendant of it (T-01-06), so a profile argument built from a
    traversal sequence cannot read a file outside the config tree. A missing profile file
    raises `FileNotFoundError` whose message names the requested profile and lists the
    profiles that were actually found.
    """
    root = (config_dir if config_dir is not None else _DEFAULT_CONFIG_DIR).resolve()

    merged: dict = {}
    source_files: list[Path] = []
    for domain in BASE_DOMAIN_FILES:
        domain_path = root / f"{domain}.yaml"
        if not domain_path.is_file():
            raise FileNotFoundError(f"Missing required base config file: {domain_path}")
        data = yaml.safe_load(domain_path.read_text()) or {}
        merged = deep_merge(merged, data)
        source_files.append(domain_path)

    profiles_dir = root / "profiles"
    available_profiles = (
        sorted(p.stem for p in profiles_dir.glob("*.yaml")) if profiles_dir.is_dir() else []
    )
    profile_path = (profiles_dir / f"{profile}.yaml").resolve()
    if not profile_path.is_relative_to(root):
        raise ValueError(
            f"Profile {profile!r} resolves outside the config directory ({root}); refusing "
            "to load it"
        )
    if not profile_path.is_file():
        raise FileNotFoundError(
            f"Unknown profile {profile!r}: no such file {profile_path}. Available profiles: "
            f"{', '.join(available_profiles) if available_profiles else '(none found)'}"
        )
    overlay = yaml.safe_load(profile_path.read_text()) or {}
    merged = deep_merge(merged, overlay)
    merged["profile"] = profile
    source_files.append(profile_path)

    config = Config.model_validate(merged)
    return ResolvedConfig(
        config=config,
        config_hash=config_hash(config),
        profile=profile,
        source_files=tuple(source_files),
    )
