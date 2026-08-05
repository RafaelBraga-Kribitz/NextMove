"""CLI entry point: `python -m nextmove.storage <table_name> [--root <dir>]`.

Prints a table's full lineage chain via `print_lineage_chain`, forwarding `--root` so a chain
can be inspected in an alternate output tree -- exactly where the golden reproducibility
suite's second run lands (plan 01-11). This turns DATA-04's "the full lineage chain is
printable from the command line" into a command a reviewer can actually run, rather than a
property of an internal function only a test exercises.
"""

import argparse
from pathlib import Path

from nextmove.storage.lineage import print_lineage_chain


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m nextmove.storage")
    parser.add_argument("table_name", help="Name of the table whose lineage chain to print.")
    parser.add_argument(
        "--root",
        default=None,
        type=Path,
        help="Output root to read lineage fragments from; defaults to the storage layer's "
        "DATA_ROOT.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        print_lineage_chain(args.table_name, root=args.root)
    except (KeyError, ValueError) as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
