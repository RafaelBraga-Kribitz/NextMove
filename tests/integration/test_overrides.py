"""D4 / UC1: a logged override is priced against the engine's choice in evaluation."""

import shutil
from pathlib import Path

import pandas as pd

from nextmove.config.loader import load_config
from nextmove.decisions.assembly import ContextStore
from nextmove.evaluate.overrides import append_override, evaluate_overrides, read_overrides
from nextmove.evaluate.pipeline import run_evaluation
from nextmove.evaluate.world import OutcomeOracle


def test_override_flows_into_evaluation(tiny_pipeline: Path, tmp_path: Path) -> None:
    root = tmp_path / "data"
    shutil.copytree(tiny_pipeline, root)
    resolved = load_config("tiny")
    decisions = pd.read_parquet(root / "evaluation" / "replay_decisions.parquet")
    row = decisions[decisions["policy"] == "expected_value_gbm"].iloc[0]
    record = append_override(
        root,
        decision_id=row["decision_id"],
        customer_id=row["customer_id"],
        day=int(row["day"]),
        original_candidate=row["candidate_id"],
        override_candidate="email_now",
        reason="Customer asked for news about the new collection",
        operator="claudia",
    )
    assert read_overrides(root) == [record]
    store = ContextStore(resolved, root, days=[int(row["day"])])
    frame = evaluate_overrides([record], store, OutcomeOracle(resolved, root))
    assert len(frame) == 1
    effect = frame.iloc[0]
    assert effect["override_effect_cents"] == (
        effect["expected_profit_override_cents"] - effect["expected_profit_original_cents"]
    )
    report_dir = tmp_path / "reports"
    run_evaluation(resolved, root, report_dir)
    published = pd.read_csv(report_dir / "override_outcomes.csv")
    assert published["override_id"].tolist() == [record.override_id]
    assert "1 logged override" in (report_dir / "evaluation_report.md").read_text()
