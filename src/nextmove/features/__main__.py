"""CLI entry point: `python -m nextmove.features --profile <name> [--out <dir>]`.

Loads config, forwards `--out` as `materialize_grid`'s `out_root` (redirecting both the
canonical `events` read and the `feature_grid` write to that root), and prints one line naming
the profile, the config hash, `FEATURE_SET_VERSION`, the row count, and the resolved absolute
output path.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nextmove.config.loader import load_config
from nextmove.features.compute import materialize_grid
from nextmove.features.definitions import FEATURE_SET_VERSION
from nextmove.storage import read_lineage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m nextmove.features")
    parser.add_argument("--profile", default="default", help="Config profile name to run.")
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Output root; defaults to the storage layer's DATA_ROOT.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    resolved = load_config(args.profile)
    dest = materialize_grid(resolved, out_root=args.out)

    lineage_by_table = {record.table_name: record for record in read_lineage(root=args.out)}
    feature_grid_record = lineage_by_table.get("feature_grid")
    row_count = feature_grid_record.row_count if feature_grid_record is not None else 0

    print(
        f"profile={resolved.profile} config_hash={resolved.config_hash} "
        f"feature_set_version={FEATURE_SET_VERSION} rows={row_count} "
        f"feature_grid={dest.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
