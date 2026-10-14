"""B2: prediction-axis metrics used by the calibration gate (AC-5)."""

import numpy as np

from nextmove.models.metrics import (
    brier,
    expected_calibration_error,
    prediction_metrics,
    reliability_table,
)


def test_perfectly_calibrated_predictions_have_tiny_ece() -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(0.01, 0.2, 200_000)
    y = (rng.random(len(p)) < p).astype(int)
    assert expected_calibration_error(p, y, 10) < 0.003


def test_miscalibration_is_detected() -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(0.01, 0.2, 50_000)
    y = (rng.random(len(p)) < p / 2).astype(int)
    assert expected_calibration_error(p, y, 10) > 0.03


def test_reliability_table_bins_cover_all_rows() -> None:
    p = np.linspace(0, 1, 101)
    y = (p > 0.5).astype(int)
    table = reliability_table(p, y, 10)
    assert sum(row["bin_count"] for row in table) == 101
    assert brier(p, y) < 0.25


def test_prediction_metrics_keys() -> None:
    metrics = prediction_metrics(np.array([0.1, 0.9]), np.array([0, 1]), 2)
    assert metrics["roc_auc"] == 1.0
    assert {"brier", "log_loss", "ece", "brier_skill_vs_base_rate"} <= set(metrics)
