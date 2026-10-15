"""Prediction-axis metrics: Brier score, log loss, ROC AUC, expected calibration error and the
reliability table behind every calibration report (AC-5)."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import log_loss, roc_auc_score

__all__ = ["brier", "expected_calibration_error", "prediction_metrics", "reliability_table"]


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def reliability_table(p: np.ndarray, y: np.ndarray, bins: int) -> list[dict[str, float]]:
    """Equal-count bins of predicted probability: mean prediction vs observed rate."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    order = np.argsort(p, kind="stable")
    rows = []
    for chunk in np.array_split(order, bins):
        if len(chunk) == 0:
            continue
        rows.append(
            {
                "bin_mean_predicted": float(p[chunk].mean()),
                "bin_observed_rate": float(y[chunk].mean()),
                "bin_count": float(len(chunk)),
            }
        )
    return rows


def expected_calibration_error(p: np.ndarray, y: np.ndarray, bins: int) -> float:
    table = reliability_table(p, y, bins)
    n = sum(row["bin_count"] for row in table)
    return float(
        sum(
            row["bin_count"] / n * abs(row["bin_mean_predicted"] - row["bin_observed_rate"])
            for row in table
        )
    )


def prediction_metrics(p: np.ndarray, y: np.ndarray, bins: int) -> dict[str, float]:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    base = float(y.mean()) if len(y) else 0.0
    base_brier = brier(np.full_like(p, base), y)
    has_both = 0 < y.sum() < len(y)
    return {
        "rows": float(len(y)),
        "positive_rate": base,
        "mean_predicted": float(p.mean()) if len(p) else 0.0,
        "brier": brier(p, y),
        "brier_skill_vs_base_rate": 1.0 - brier(p, y) / base_brier if base_brier > 0 else 0.0,
        "log_loss": float(log_loss(y, np.clip(p, 1e-9, 1 - 1e-9), labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, p)) if has_both else float("nan"),
        "ece": expected_calibration_error(p, y, bins),
    }
