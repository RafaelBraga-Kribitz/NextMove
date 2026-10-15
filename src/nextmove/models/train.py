"""The `train` pipeline stage: segmentation (B1) and response models (B2).

Reads the randomized `experiment_log` and the feature grid; writes, under `data/models/`:

- `logistic.pkl`, `gbm.pkl` -- calibrated bootstrap ensembles (`nextmove.models.response`);
- `model_metrics` -- Brier, log loss, AUC, ECE per family, split and archetype;
- `reliability` -- the reliability-curve bins behind every calibration report;
- `segments` + `segmentation_scorecard.json` -- the chosen segmentation and its MCDA scorecard.

**AC-5 gate.** A family whose out-of-time (test-window) expected calibration error exceeds
`models.calibration.max_ece` fails the stage: no miscalibrated model can reach the decision
path. Runs are also logged to a local MLflow store (`mlruns/`) when MLflow is installed.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from nextmove.config.loader import ResolvedConfig
from nextmove.models.features import context_feature_names
from nextmove.models.metrics import prediction_metrics, reliability_table
from nextmove.models.response import ResponseModel, fit_response_model
from nextmove.segmentation.segment import run_segmentation
from nextmove.storage import (
    Stage,
    Zone,
    query,
    read_frame,
    resolve_artifact_path,
    resolve_table_path,
    write_frame,
)

__all__ = ["FAMILIES", "CalibrationGateError", "load_model", "run_training"]

FAMILIES = ("logistic", "gbm")


class CalibrationGateError(RuntimeError):
    """Raised when a model breaches the configured calibration bound (AC-5)."""


def _arrays(frame: pd.DataFrame, names: list[str]) -> dict[str, np.ndarray]:
    return {
        "x": frame[names].to_numpy(dtype=float),
        "archetype": frame["archetype"].to_numpy(),
        "depth": (frame["discount_bps"] / 10_000).to_numpy(dtype=float),
        "y": frame["converted"].astype(int).to_numpy(),
        "customer": frame["customer_id"].to_numpy(),
    }


def load_model(family: str, root: Path | None = None) -> ResponseModel:
    with resolve_artifact_path(f"{family}.pkl", Zone.MODELS, root).open("rb") as handle:
        return pickle.load(handle)  # noqa: S301 - our own artifact, written by this stage


def _segment(resolved: ResolvedConfig, root: Path | None, snapshot_day: int) -> None:
    config = resolved.config
    start = config.simulator.start_date.isoformat()
    grid = query(
        "SELECT * FROM grid WHERE date_diff('day', DATE '"
        + start
        + "', CAST(as_of_ts AS DATE)) = "
        + str(int(snapshot_day))
        + " ORDER BY customer_id",
        root=root,
        grid=resolve_table_path("feature_grid", Zone.FEATURES, root),
    ).to_pandas()
    exposures = query(
        "SELECT customer_id, COUNT(*) AS contacts_total FROM events WHERE type = "
        "'campaign_exposure' AND date_diff('day', DATE '"
        + start
        + "', CAST(ts AS DATE)) < "
        + str(int(snapshot_day))
        + " GROUP BY customer_id ORDER BY customer_id",
        root=root,
        events=resolve_table_path("events", Zone.CANONICAL, root),
    ).to_pandas()
    first = query(
        "SELECT DISTINCT customer_id FROM events WHERE date_diff('day', DATE '" + start + "', "
        "CAST(ts AS DATE)) < " + str(int(snapshot_day)) + " ORDER BY customer_id",
        root=root,
        events=resolve_table_path("events", Zone.CANONICAL, root),
    ).to_pandas()
    grid = grid[grid["customer_id"].isin(first["customer_id"])]
    grid = grid.merge(exposures, on="customer_id", how="left")
    grid["contacts_total"] = grid["contacts_total"].fillna(0)
    grid = grid.reset_index(drop=True)
    result = run_segmentation(grid, config.mcda, config.evaluation.seeds.models)
    segments = pd.DataFrame(
        {
            "customer_id": grid["customer_id"].astype(str),
            "segment_id": result.labels.astype("int64"),
            "segment_name": [result.segment_names[int(label)] for label in result.labels],
            "method": result.chosen,
            "snapshot_day": np.full(len(grid), snapshot_day, dtype="int64"),
        }
    )
    write_frame(
        segments,
        "segments",
        Zone.MODELS,
        ("customer_id",),
        resolved,
        Stage.TRAIN,
        input_paths=(resolve_table_path("feature_grid", Zone.FEATURES, root),),
        root=root,
    )
    path = resolve_artifact_path("segmentation_scorecard.json", Zone.MODELS, root)
    path.write_text(json.dumps(result.scorecard, indent=2, sort_keys=True) + "\n", "utf-8")


def run_training(resolved: ResolvedConfig, root: Path | None = None) -> dict[str, Path]:
    config = resolved.config
    train_end, _, _ = config.evaluation.windows(config.simulator.horizon_days)
    _segment(resolved, root, train_end)

    log = read_frame("experiment_log", Zone.EXPERIMENT, root)
    categories = [c.name for c in config.simulator.categories]
    names = context_feature_names(categories)
    archetypes = [a.name for a in config.actions.catalog]
    splits = {s: _arrays(log[log["split"] == s], names) for s in ("train", "validation", "test")}
    bins = config.models.calibration.reliability_bins

    metric_rows: list[dict] = []
    reliability_rows: list[dict] = []
    written: dict[str, Path] = {}
    failures: list[str] = []
    for family in FAMILIES:
        model = fit_response_model(
            family,
            config.models,
            archetypes,
            names,
            splits["train"],
            splits["validation"],
            config.evaluation.seeds.models,
        )
        path = resolve_artifact_path(f"{family}.pkl", Zone.MODELS, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(model, handle)
        written[family] = path
        for split, data in splits.items():
            p = model.predict(data["x"], data["archetype"], data["depth"])
            groups = [("all", np.ones(len(p), dtype=bool))]
            groups += [(a, data["archetype"] == a) for a in archetypes]
            for group, mask in groups:
                if mask.sum() == 0:
                    continue
                metrics = prediction_metrics(p[mask], data["y"][mask], bins)
                metric_rows.append(
                    {
                        "family": family,
                        "model_version": model.version,
                        "split": split,
                        "archetype": group,
                        **metrics,
                    }
                )
            for index, row in enumerate(reliability_table(p, data["y"], bins)):
                reliability_rows.append({"family": family, "split": split, "bin": index, **row})
        test_ece = next(
            r["ece"]
            for r in metric_rows
            if r["family"] == family and r["split"] == "test" and r["archetype"] == "all"
        )
        if test_ece > config.models.calibration.max_ece:
            failures.append(
                f"{family}: test ECE {test_ece:.4f} > {config.models.calibration.max_ece}"
            )

    inputs = (resolve_table_path("experiment_log", Zone.EXPERIMENT, root),)
    metrics_frame = pd.DataFrame(metric_rows)
    metrics_frame["rows"] = metrics_frame["rows"].astype("int64")
    written["model_metrics"] = write_frame(
        metrics_frame,
        "model_metrics",
        Zone.MODELS,
        ("family", "split", "archetype"),
        resolved,
        Stage.TRAIN,
        input_paths=inputs,
        root=root,
    )
    reliability = pd.DataFrame(reliability_rows)
    reliability["bin"] = reliability["bin"].astype("int64")
    written["reliability"] = write_frame(
        reliability,
        "reliability",
        Zone.MODELS,
        ("family", "split", "bin"),
        resolved,
        Stage.TRAIN,
        input_paths=inputs,
        root=root,
    )
    _log_mlflow(resolved, metrics_frame, root)
    if failures:
        raise CalibrationGateError("calibration gate (AC-5) failed: " + "; ".join(failures))
    return written


def _log_mlflow(resolved: ResolvedConfig, metrics: pd.DataFrame, root: Path | None) -> None:
    """Best-effort local experiment tracking (ADR-007); never part of the published bytes."""
    try:
        import mlflow
    except ImportError:  # pragma: no cover - mlflow is a dev dependency
        return
    base = (root if root is not None else Path(__file__).resolve().parents[3]) / "mlruns"
    mlflow.set_tracking_uri(f"sqlite:///{base}.db")
    mlflow.set_experiment(f"nextmove-{resolved.profile}")
    for family, group in metrics[metrics["archetype"] == "all"].groupby("family"):
        with mlflow.start_run(run_name=f"{family}-{resolved.config_hash[:10]}"):
            mlflow.log_params(
                {
                    "family": family,
                    "profile": resolved.profile,
                    "config_hash": resolved.config_hash,
                    "model_version": group["model_version"].iloc[0],
                }
            )
            for _, row in group.iterrows():
                for key in ("brier", "log_loss", "roc_auc", "ece"):
                    value = float(row[key])
                    if np.isfinite(value):
                        mlflow.log_metric(f"{row['split']}_{key}", value)
