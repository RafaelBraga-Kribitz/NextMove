"""DoD 8: every headline number on the README traces to the published, seeded run."""

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVALUATION = REPO / "reports" / "demo" / "evaluation"


def _eur(value: float) -> str:
    rounded = round(value)
    if rounded == 0:
        return "€0"
    return f"−€{abs(rounded):,}" if rounded < 0 else f"€{rounded:,}"


def _summary() -> dict[str, dict[str, str]]:
    with (EVALUATION / "policy_comparison.csv").open(encoding="utf-8") as handle:
        return {row["policy"]: row for row in csv.DictReader(handle)}


def test_readme_run_id_matches_published_run() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    run_id = json.loads((EVALUATION / "summary.json").read_text())["run_id"]
    assert f"run `{run_id}`" in readme
    assert "In simulation only" in readme or "in simulation only" in readme


def test_readme_headline_number_matches_published_table() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    rows = _summary()
    ml = next(r for r in rows.values() if r["is_ml_policy"] == "True")
    diff = -float(rows["rules_only"]["vs_do_nothing_eur"]) + float(ml["vs_do_nothing_eur"])
    assert f"+{_eur(diff)}" in readme
    low = float(ml["vs_rules_only_ci_low_eur"])
    high = float(ml["vs_rules_only_ci_high_eur"])
    assert f"95% CI {_eur(low)} to {_eur(high)}" in readme


def test_readme_result_table_matches_published_table() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for policy, row in _summary().items():
        interval = (
            f"{_eur(float(row['vs_do_nothing_eur']))} "
            f"[{_eur(float(row['vs_do_nothing_ci_low_eur']))}, "
            f"{_eur(float(row['vs_do_nothing_ci_high_eur']))}]"
        )
        if policy in ("do_nothing", "expected_value_logistic"):
            continue
        assert interval in readme, (policy, interval)
    discount = _summary()["always_discount"]
    assert f"{float(discount['wasted_discount_share']):.0%}" in readme
