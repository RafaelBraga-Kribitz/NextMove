"""`python -m nextmove.evaluate <stage> --profile <name> [--out <root>]`.

Stages: `experiment` (the randomized A/B/n log) and `evaluate` (policy replay and reports).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nextmove.config.loader import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nextmove.evaluate")
    parser.add_argument("stage", choices=["experiment", "evaluate"])
    parser.add_argument("--profile", default="default")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--reports", type=Path, default=None)
    args = parser.parse_args(argv)
    resolved = load_config(args.profile)
    if args.stage == "experiment":
        from nextmove.evaluate.experiment import run_experiment

        path = run_experiment(resolved, args.out)
        print(
            f"profile={resolved.profile} config_hash={resolved.config_hash} experiment_log={path}"
        )
        return 0
    from nextmove.evaluate.pipeline import run_evaluation

    summary = run_evaluation(resolved, args.out, args.reports)
    print(f"profile={resolved.profile} run_id={summary['run_id']} reports={summary['reports_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
