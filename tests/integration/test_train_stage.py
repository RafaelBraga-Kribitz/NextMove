"""B2 on the tiny pipeline: both families trained, metrics and reliability written, AC-5 gate
enforced, and the models expose attributions (ADR-005)."""

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nextmove.config.loader import load_config
from nextmove.models.features import context_feature_names
from nextmove.models.train import FAMILIES, CalibrationGateError, load_model, run_training


def test_models_metrics_and_scorecard_written(tiny_pipeline: Path) -> None:
    metrics = pd.read_parquet(tiny_pipeline / "models" / "model_metrics.parquet")
    assert set(metrics["family"]) == set(FAMILIES)
    assert {"train", "validation", "test"} <= set(metrics["split"])
    reliability = pd.read_parquet(tiny_pipeline / "models" / "reliability.parquet")
    assert len(reliability) > 0
    assert (tiny_pipeline / "models" / "segmentation_scorecard.json").is_file()
    segments = pd.read_parquet(tiny_pipeline / "models" / "segments.parquet")
    assert segments["customer_id"].is_unique


@pytest.mark.parametrize("family", FAMILIES)
def test_attributions_sum_to_uplift_logit(tiny_pipeline: Path, family: str) -> None:
    model = load_model(family, tiny_pipeline)
    names = context_feature_names(["fashion_apparel", "home_basics"])
    assert model.feature_names == names
    x = np.full(len(names), 1.0)
    pairs = model.uplift_attributions(x, "recommend", 0.0)
    assert pairs[-1][0] == "action:recommend"
    # Sum of contributions == ensemble-mean raw uplift logit (exact for both families).
    raw = []
    for member in model.members:
        design = model._design(np.vstack([x, x]), np.array(["recommend", "none"]), np.zeros(2))
        logits = model._raw_logit(member, design)
        raw.append(logits[0] - logits[1])
    assert sum(w for _, w in pairs) == pytest.approx(float(np.mean(raw)), rel=1e-6, abs=1e-6)


def test_calibration_gate_fails_on_tight_bound(tiny_pipeline: Path, tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "copy"
    shutil.copytree(tiny_pipeline, root)
    resolved = load_config("tiny")
    strict = resolved.config.model_copy(
        update={
            "models": resolved.config.models.model_copy(
                update={
                    "calibration": resolved.config.models.calibration.model_copy(
                        update={"max_ece": 1e-9}
                    )
                }
            )
        }
    )
    with pytest.raises(CalibrationGateError, match="AC-5"):
        run_training(dataclasses.replace(resolved, config=strict), root)
