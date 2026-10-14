"""D1-D4 on the tiny pipeline: policy comparison (AC-10), gateway escalation on a real replay
readout (AC-9), uplift error table (ADR-006), and reproducible published tables (AC-11)."""

import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nextmove.config.loader import load_config
from nextmove.evaluate.gateway import adjudicate
from nextmove.evaluate.pipeline import _readout, run_evaluation

POLICIES = {
    "do_nothing",
    "always_discount",
    "top_seller",
    "rules_only",
    "expected_value_logistic",
    "expected_value_gbm",
    "oracle_upper_bound",
}


def test_policy_comparison_covers_all_policies_with_intervals(tiny_pipeline: Path) -> None:
    summary = pd.read_csv(tiny_pipeline / "reports" / "policy_comparison.csv")
    assert set(summary["policy"]) == POLICIES
    assert summary["is_ml_policy"].sum() == 1
    assert (summary["profit_ci_low_eur"] <= summary["profit_eur"] + 1e-9).all()
    assert (summary["profit_eur"] <= summary["profit_ci_high_eur"] + 1e-9).all()
    nothing = summary.set_index("policy").loc["do_nothing"]
    assert nothing["discount_rate"] == 0 and nothing["contact_rate"] == 0
    # The hindsight oracle is never beaten in expected profit.
    best = summary.set_index("policy")["expected_profit_eur"]
    assert best["oracle_upper_bound"] >= best.drop("oracle_upper_bound").max() - 1e-9
    assert summary["run_id"].nunique() == 1


def test_report_files_exist_and_carry_caveat(tiny_pipeline: Path) -> None:
    reports = tiny_pipeline / "reports"
    for name in (
        "evaluation_report.md",
        "policy_comparison.png",
        "uplift_error.csv",
        "gateway_verdicts.csv",
        "model_cards/gbm.md",
        "model_cards/logistic.md",
    ):
        assert (reports / name).is_file(), name
    text = (reports / "evaluation_report.md").read_text(encoding="utf-8")
    assert text.splitlines()[2].startswith("> **Simulated data only.**")
    summary = json.loads((reports / "summary.json").read_text())
    assert summary["run_id"] in text


def test_replay_never_chooses_a_filtered_action(tiny_pipeline: Path) -> None:
    decisions = pd.read_parquet(tiny_pipeline / "evaluation" / "replay_decisions.parquet")
    assert len(decisions)
    contact = decisions[decisions["contact"]]
    assert (contact["recent_contacts_7d"] < 2).all()
    assert (decisions["discount_bps"] <= 2000).all()


def test_ac9_inconclusive_replay_readout_escalates_past_budget(tiny_pipeline: Path) -> None:
    resolved = load_config("tiny")
    decisions = pd.read_parquet(tiny_pipeline / "evaluation" / "replay_decisions.parquet")
    a = decisions[decisions["policy"] == "expected_value_gbm"]
    b = decisions[decisions["policy"] == "always_discount"]
    customers = sorted(set(a["customer_id"]) | set(b["customer_id"]))
    weights = (
        np.random.default_rng(0)
        .multinomial(len(customers), np.full(len(customers), 1 / len(customers)), size=200)
        .astype(float)
    )
    readout = _readout("candidate vs control", a, b, customers, weights, 0.95, days_running=10)
    if readout.primary.point < 0:
        readout = _readout("candidate vs control", b, a, customers, weights, 0.95, 10)
    # Thresholds that cannot Accept (huge MDE) and cannot call a tie (tiny margin): a
    # non-negative effect is therefore a Delay, and a Delay past its budget must escalate.
    thresholds = resolved.config.experiments.model_copy(
        update={"mde": 1e9, "indifference_margin": 1e-12, "delay_budget_days": 5, "guardrails": []}
    )
    verdict = adjudicate(readout, thresholds, resolved.config.autonomy)
    assert verdict.verdict == "needs_human_review", verdict
    within = dataclasses.replace(readout, days_running=2)
    assert adjudicate(within, thresholds, resolved.config.autonomy).verdict == "delay"


def test_uplift_error_table(tiny_pipeline: Path) -> None:
    uplift = pd.read_csv(tiny_pipeline / "reports" / "uplift_error.csv")
    assert set(uplift["family"]) == {"logistic", "gbm"}
    assert (uplift["mae"] >= 0).all()


def test_published_tables_reproduce_exactly(tiny_pipeline: Path, tmp_path: Path) -> None:
    resolved = load_config("tiny")
    run_evaluation(resolved, tiny_pipeline, tmp_path / "again")
    for name in (
        "policy_comparison.csv",
        "uplift_error.csv",
        "gateway_verdicts.csv",
        "model_metrics.csv",
        "by_segment.csv",
    ):
        first = (tiny_pipeline / "reports" / name).read_text(encoding="utf-8")
        assert (tmp_path / "again" / name).read_text(encoding="utf-8") == first, name
