"""CLI entry point: `python -m nextmove.simulator --profile <name> [--out <dir>]`.

Loads config via `nextmove.config.loader.load_config`, runs `run_simulation`, and prints one
summary line naming the profile, the config hash, the tick count, the event count, and every
written table's absolute resolved path -- printed so a caller that supplied `--out` can see
where the run actually landed.

This CLI declares no argument naming the random seed (D-25): the seed is a config value inside
the hashed surface, never a command-line flag, so a determinism claim is auditable from the
config hash alone.
"""

import argparse
from pathlib import Path

from nextmove.config.loader import load_config
from nextmove.simulator.run import run_simulation
from nextmove.storage import read_lineage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m nextmove.simulator")
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
    written = run_simulation(resolved, out_root=args.out)

    lineage_by_table = {record.table_name: record for record in read_lineage(root=args.out)}
    events_record = lineage_by_table.get("events_raw")
    event_count = events_record.row_count if events_record is not None else 0
    tick_count = resolved.config.simulator.horizon_days

    table_summary = ", ".join(f"{name}={path.resolve()}" for name, path in sorted(written.items()))
    print(
        f"profile={resolved.profile} config_hash={resolved.config_hash} "
        f"ticks={tick_count} events={event_count} tables: {table_summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
