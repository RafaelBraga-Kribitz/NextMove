"""`python -m nextmove.models --profile <name> [--out <root>]`: the `train` stage."""

from __future__ import annotations

import argparse
from pathlib import Path

from nextmove.config.loader import load_config
from nextmove.models.train import CalibrationGateError, run_training


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nextmove.models")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    resolved = load_config(args.profile)
    try:
        written = run_training(resolved, args.out)
    except CalibrationGateError as error:
        print(f"profile={resolved.profile} train=FAILED {error}")
        return 1
    print(
        f"profile={resolved.profile} config_hash={resolved.config_hash} "
        + " ".join(f"{name}={path}" for name, path in sorted(written.items()))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
