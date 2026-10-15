"""`python -m nextmove.mart --profile <name> [--out <root>] [--export <dir>]`: the `mart` stage."""

from __future__ import annotations

import argparse
from pathlib import Path

from nextmove.config.loader import load_config
from nextmove.mart.build import MartTestFailure, build_mart


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nextmove.mart")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--export", type=Path, default=None)
    args = parser.parse_args(argv)
    resolved = load_config(args.profile)
    try:
        manifest = build_mart(resolved, args.out, args.export)
    except MartTestFailure as error:
        print(f"profile={resolved.profile} mart=FAILED {error}")
        return 1
    print(f"profile={resolved.profile} mart tables={manifest['row_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
