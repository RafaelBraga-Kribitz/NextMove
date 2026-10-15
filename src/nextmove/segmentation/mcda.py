"""TOPSIS multi-criteria ranking (AC-7): the alternative closest to the ideal and farthest
from the anti-ideal wins. Weights and directions come from `config/mcda.yaml`."""

from __future__ import annotations

import numpy as np

from nextmove.config.models import McdaCriterion

__all__ = ["topsis"]


def topsis(
    matrix: dict[str, dict[str, float]], criteria: dict[str, McdaCriterion]
) -> dict[str, float]:
    """`matrix[alternative][criterion]` -> closeness score in [0, 1] per alternative."""
    names = sorted(matrix)
    keys = sorted(criteria)
    values = np.array([[matrix[n][k] for k in keys] for n in names], dtype=float)
    norms = np.sqrt((values**2).sum(axis=0))
    norms[norms == 0] = 1.0
    weights = np.array([criteria[k].weight for k in keys])
    weighted = values / norms * (weights / weights.sum())
    benefit = np.array([criteria[k].direction == "benefit" for k in keys])
    ideal = np.where(benefit, weighted.max(axis=0), weighted.min(axis=0))
    anti = np.where(benefit, weighted.min(axis=0), weighted.max(axis=0))
    d_plus = np.sqrt(((weighted - ideal) ** 2).sum(axis=1))
    d_minus = np.sqrt(((weighted - anti) ** 2).sum(axis=1))
    total = d_plus + d_minus
    closeness = np.where(total > 0, d_minus / np.where(total > 0, total, 1.0), 0.0)
    return {n: float(c) for n, c in zip(names, closeness, strict=True)}
