"""AC-12 coverage gate: >= 85% line coverage for rules/, decisions/, evaluate/; >= 75% overall.

Reads `coverage.json` (written by `pytest --cov --cov-report=json`) and exits non-zero with a
per-package table when a threshold is missed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_THRESHOLDS = {"rules": 85.0, "decisions": 85.0, "evaluate": 85.0}
OVERALL_THRESHOLD = 75.0


def main(path: str = "coverage.json") -> int:
    data = json.loads(Path(path).read_text())
    per_package: dict[str, list[int]] = {}
    for filename, info in data["files"].items():
        parts = Path(filename).parts
        if "nextmove" not in parts:
            continue
        package = parts[parts.index("nextmove") + 1]
        summary = info["summary"]
        totals = per_package.setdefault(package, [0, 0])
        totals[0] += summary["covered_lines"]
        totals[1] += summary["num_statements"]
    failed = False
    print(f"{'package':<14}{'lines':>8}{'covered':>9}{'percent':>9}  gate")
    for package, (covered, statements) in sorted(per_package.items()):
        percent = 100.0 * covered / statements if statements else 100.0
        gate = PACKAGE_THRESHOLDS.get(package)
        verdict = "" if gate is None else ("ok" if percent >= gate else f"FAIL (< {gate:.0f}%)")
        failed |= gate is not None and percent < gate
        print(f"{package:<14}{statements:>8}{covered:>9}{percent:>8.1f}%  {verdict}")
    covered = sum(c for c, _ in per_package.values())
    statements = sum(s for _, s in per_package.values())
    overall = 100.0 * covered / statements
    ok = overall >= OVERALL_THRESHOLD
    failed |= not ok
    print(
        f"{'overall':<14}{statements:>8}{covered:>9}{overall:>8.1f}%  "
        f"{'ok' if ok else f'FAIL (< {OVERALL_THRESHOLD:.0f}%)'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
