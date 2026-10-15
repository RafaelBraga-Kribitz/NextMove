"""Customer segmentation with viability constraints and an MCDA scorecard (B1, AC-7).

Candidates are a classic rule-based RFM tiering and k-means over standardized behavioural
features for each configured `k`. Every candidate is checked against the viability constraints
(minimum segment share, maximum segment count); only viable candidates enter the TOPSIS ranking.
Criteria: silhouette (cohesion), size balance (normalized entropy of segment shares), stability
(mean adjusted Rand index of refits on customer bootstrap resamples) and interpretability (a
recorded judgement per method). The scorecard -- criteria matrix, weights, ranking, viability
verdicts and a weight-sensitivity check -- is emitted on every run.

Input is one feature-grid snapshot per customer at the end of the training window, so the
segmentation never sees the test window.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from nextmove.config.models import McdaConfig, McdaCriterion
from nextmove.segmentation.mcda import topsis

__all__ = ["SegmentationResult", "rfm_rules", "run_segmentation"]

_RFM_LABELS = {
    0: "new_or_browsing",
    1: "lapsed_buyer",
    2: "active_buyer",
    3: "loyal_high_value",
}


def rfm_rules(frame: pd.DataFrame) -> np.ndarray:
    """Readable RFM tiers: never ordered; ordered but lapsed (> 60 days); active; and active
    with above-median spend. Thresholds are the classic RFM cut points, relative to data."""
    recency = frame["rfm_recency_days"]
    monetary = frame["rfm_monetary_cents"]
    never = recency.isna()
    lapsed = ~never & (recency > 60)
    spend_cut = monetary[~never & ~lapsed].median() if (~never & ~lapsed).any() else 0
    high = ~never & ~lapsed & (monetary > spend_cut)
    labels = np.where(never, 0, np.where(lapsed, 1, np.where(high, 3, 2)))
    return labels.astype(int)


def _matrix(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    x = frame[features].astype(float).copy()
    x["rfm_recency_days"] = x["rfm_recency_days"].fillna(365.0).clip(upper=365.0)
    x = x.fillna(0.0).to_numpy()
    x = np.log1p(np.clip(x, 0, None))
    sd = x.std(axis=0)
    sd[sd == 0] = 1.0
    return (x - x.mean(axis=0)) / sd


@dataclass
class SegmentationResult:
    chosen: str
    labels: np.ndarray
    segment_names: dict[int, str]
    scorecard: dict


def _kmeans(x: np.ndarray, k: int, seed: int) -> np.ndarray:
    return KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(x)


def _size_balance(labels: np.ndarray) -> float:
    shares = np.bincount(labels) / len(labels)
    shares = shares[shares > 0]
    if len(shares) <= 1:
        return 0.0
    return float(-(shares * np.log(shares)).sum() / np.log(len(shares)))


def run_segmentation(frame: pd.DataFrame, config: McdaConfig, seed: int) -> SegmentationResult:
    seg = config.segmentation
    x = _matrix(frame, seg.features)
    rng = np.random.Generator(np.random.PCG64(seed))
    sample = rng.choice(len(x), size=min(len(x), 3000), replace=False)

    def fit(method: str, rows: np.ndarray) -> np.ndarray:
        if method == "rfm_rules":
            return rfm_rules(frame.iloc[rows])
        return _kmeans(x[rows], int(method.split("_k")[1]), seed)

    methods = ["rfm_rules", *(f"kmeans_k{k}" for k in seg.kmeans_k)]
    candidates: dict[str, dict] = {}
    for method in methods:
        labels = fit(method, np.arange(len(x)))
        shares = np.bincount(labels) / len(labels)
        n_segments = int((shares > 0).sum())
        viable = bool(
            n_segments <= seg.max_segments and shares[shares > 0].min() >= seg.min_segment_share
        )
        aris = []
        for r in range(seg.stability_resamples):
            boot = np.random.Generator(np.random.PCG64([seed, r])).choice(
                len(x), size=len(x), replace=True
            )
            refit = fit(method, boot)
            aris.append(adjusted_rand_score(labels[boot], refit))
        silhouette = (
            float(silhouette_score(x[sample], labels[sample]))
            if len(np.unique(labels[sample])) > 1
            else -1.0
        )
        family = "rfm_rules" if method == "rfm_rules" else "kmeans"
        candidates[method] = {
            "labels": labels,
            "viable": viable,
            "n_segments": n_segments,
            "min_share": float(shares[shares > 0].min()),
            "criteria": {
                "silhouette": silhouette,
                "size_balance": _size_balance(labels),
                "stability": float(np.mean(aris)),
                "interpretability": float(seg.interpretability[family]),
            },
        }
    viable = {m: c["criteria"] for m, c in candidates.items() if c["viable"]}
    if not viable:
        # Too few customers for any candidate to be viable (e.g. the tiny test profile): the
        # one segmentation that always satisfies the constraints is a single segment. The
        # scorecard records why instead of failing the run or emitting a non-viable split.
        scorecard = {
            "chosen": "all_customers",
            "reason": "no candidate satisfied the viability constraints",
            "weights": {k: v.weight for k, v in sorted(config.criteria.items())},
            "viability": {
                "min_segment_share": seg.min_segment_share,
                "max_segments": seg.max_segments,
            },
            "candidates": {
                m: {k: v for k, v in c.items() if k != "labels"} for m, c in candidates.items()
            },
            "topsis_closeness": {},
            "ranking": [],
            "sensitivity": [],
            "customers": int(len(frame)),
        }
        return SegmentationResult(
            "all_customers", np.zeros(len(frame), dtype=int), {0: "all_customers"}, scorecard
        )
    scores = topsis(viable, config.criteria)
    ranking = sorted(scores, key=lambda m: (-scores[m], m))
    chosen = ranking[0]

    sensitivity = []
    for criterion in sorted(config.criteria):
        for factor in (1 - seg.sensitivity_factor, 1 + seg.sensitivity_factor):
            perturbed = {
                k: McdaCriterion(
                    weight=v.weight * (factor if k == criterion else 1.0), direction=v.direction
                )
                for k, v in config.criteria.items()
            }
            alt = topsis(viable, perturbed)
            winner = sorted(alt, key=lambda m: (-alt[m], m))[0]
            sensitivity.append(
                {
                    "criterion": criterion,
                    "weight_factor": factor,
                    "winner": winner,
                    "winner_unchanged": winner == chosen,
                }
            )

    labels = candidates[chosen]["labels"]
    names = _segment_names(chosen, frame, labels)
    scorecard = {
        "chosen": chosen,
        "weights": {k: v.weight for k, v in sorted(config.criteria.items())},
        "viability": {"min_segment_share": seg.min_segment_share, "max_segments": seg.max_segments},
        "candidates": {
            m: {k: v for k, v in c.items() if k != "labels"} for m, c in candidates.items()
        },
        "topsis_closeness": scores,
        "ranking": ranking,
        "sensitivity": sensitivity,
        "customers": int(len(frame)),
    }
    return SegmentationResult(chosen, labels, names, scorecard)


def _segment_names(method: str, frame: pd.DataFrame, labels: np.ndarray) -> dict[int, str]:
    """Readable names for k-means clusters, from each cluster's profile: buyers first, then
    browsers ranked by visit frequency."""
    if method == "rfm_rules":
        return {k: v for k, v in _RFM_LABELS.items() if k in set(labels.tolist())}
    profiles = []
    for label in sorted(set(labels.tolist())):
        part = frame[labels == label]
        profiles.append(
            (
                label,
                float(part["rfm_recency_days"].notna().mean()),
                float(part["session_visits_count"].mean()),
            )
        )
    names: dict[int, str] = {}
    buyers = sorted((p for p in profiles if p[1] >= 0.5), key=lambda p: -p[2])
    browsers = sorted((p for p in profiles if p[1] < 0.5), key=lambda p: -p[2])
    for rank, (label, _, _) in enumerate(buyers):
        names[label] = "buyers" if rank == 0 else f"buyers_{rank + 1}"
    browser_names = ["engaged_browsers", "occasional_browsers", "light_browsers"]
    for rank, (label, _, _) in enumerate(browsers):
        names[label] = browser_names[rank] if rank < len(browser_names) else f"browsers_{rank + 1}"
    return names
