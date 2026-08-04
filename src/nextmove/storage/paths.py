"""The five data zones, the sibling staging root, the producing-stage enum, and
containment-checked path resolution for both tables and part files (ENG-01, ENG-09, HIGH-5).

`DATA_ROOT` is anchored to this module's own file location, never to `Path.cwd()`. Plan
01-11 asserts two independent properties: that two runs directed at two different output
roots produce equal digests, and that two runs launched from two different working
directories produce equal digests. If the default root were derived from the working
directory, those two assertions would collapse into one experiment and the second would
prove nothing. The working directory therefore never selects a root -- the `root` parameter
on every disk-touching function does -- and `DATA_ROOT` is only what it falls back to.

Staging (`data/_staging/`) is a sibling of the five `Zone` directories and is deliberately
**not** a sixth `Zone` member. A zone is a lineage-bearing, DVC-declarable region of the data
tree; staging is transient within a single run, carries no lineage row, and is
`.dvcignore`d. Widening `Zone` to cover it would make one enum mean two incompatible things.
`resolve_staging_path` carries the identical absolute-resolve-then-assert-descendancy
discipline as `resolve_table_path`, pointed at the staging root instead of a zone directory.
"""

from enum import StrEnum
from pathlib import Path

# paths.py lives at src/nextmove/storage/paths.py, so three `.parent`s up from the resolved
# file path is the repository root.
DATA_ROOT: Path = Path(__file__).resolve().parents[3] / "data"

STAGING_DIRNAME = "_staging"


class Zone(StrEnum):
    """The five lineage-bearing, DVC-declarable data zones. Exactly five members -- staging
    is never a sixth."""

    RAW = "raw"
    CANONICAL = "canonical"
    FEATURES = "features"
    GROUND_TRUTH = "ground_truth"
    LINEAGE = "lineage"


class Stage(StrEnum):
    """The three pipeline stages -- also the three lineage fragment filenames
    (`data/lineage/{stage}.parquet`) and the three `dvc.yaml` stage names (plan 01-11). One
    enum keeps those three lists provably identical instead of coincidentally equal."""

    SIMULATE = "simulate"
    INGEST = "ingest"
    FEATURES = "features"


def resolve_table_path(name: str, zone: Zone, root: Path | None = None) -> Path:
    """Resolve a table name to its absolute Parquet path within `zone`.

    Every table read and write goes through this function so no caller can construct a path
    that escapes its zone. Raises `ValueError` naming the offending table name if the
    resolved path is not a descendant of the zone directory.
    """
    zone_dir = ((root if root is not None else DATA_ROOT) / zone.value).resolve()
    candidate = (zone_dir / f"{name}.parquet").resolve()
    if candidate != zone_dir and not candidate.is_relative_to(zone_dir):
        raise ValueError(
            f"Table name {name!r} resolves outside its zone directory ({zone_dir}); "
            "refusing to read/write it"
        )
    return candidate


def staging_root(root: Path | None = None) -> Path:
    """Absolute path to the staging root: a sibling of the five zone directories, never a
    zone itself."""
    return ((root if root is not None else DATA_ROOT) / STAGING_DIRNAME).resolve()


def resolve_staging_path(part_dir: str, part_index: int, root: Path | None = None) -> Path:
    """Resolve a part directory name and index to an absolute staging part-file path,
    creating the parent directory if it does not yet exist.

    The zero-padded fixed-width index makes lexicographic filename order equal numeric part
    order, so a merge that reads parts in sorted filename order reads them in the order they
    were written. Raises `ValueError` naming the offending `part_dir` if the resolved path
    escapes the staging root.
    """
    base = staging_root(root)
    candidate = (base / part_dir / f"part-{part_index:06d}.parquet").resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(
            f"Staging part directory {part_dir!r} resolves outside the staging root ({base}); "
            "refusing to write it"
        )
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate
