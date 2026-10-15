"""Response models: P(purchase | context, action), as calibrated bootstrap ensembles (B2).

One model per family is conditioned on the action (ADR-006, ADR-012): the action enters as an
indicator per archetype plus the discount depth, so `P(convert | a) - P(convert | none)` is a
difference of two predictions from the same model. Two families compete:

- **logistic**: standardized context features, action indicators, and action x feature
  interactions (one slope per feature per action). The uplift logit for action `a` is linear,
  so its per-feature attribution `(gamma_aj + eta_j * depth) * z_j` is exact.
- **gbm**: LightGBM on raw context features plus the archetype as a categorical feature and the
  discount depth. Attributions are exact TreeSHAP values (`pred_contrib`), differenced between
  the action row and the `none` row, so they explain the uplift logit too.

Each family is an ensemble of `ensemble_size` members fit on customer-level bootstrap resamples
of the training window, each Platt-calibrated on the validation window. The ensemble spread is
the uncertainty the decision engine turns into intervals and confidence. Training is fully
seeded and single-threaded, so a rerun reproduces every prediction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression

from nextmove.config.models import ModelsConfig

__all__ = ["Family", "ResponseModel", "fit_response_model"]

Family = Literal["logistic", "gbm"]

_EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


@dataclass
class _Member:
    estimator: object
    platt: tuple[float, float]  # calibrated logit = a * raw_logit + b


@dataclass
class ResponseModel:
    family: Family
    archetypes: list[str]
    feature_names: list[str]
    members: list[_Member]
    mean: np.ndarray
    scale: np.ndarray
    version: str
    training_rows: int

    # -- design matrices -----------------------------------------------------------------

    def _logistic_design(self, x: np.ndarray, archetypes: np.ndarray, depth: np.ndarray):
        z = (x - self.mean) / self.scale
        actions = [a for a in self.archetypes if a != "none"]
        onehot = np.stack([(archetypes == a).astype(float) for a in actions], axis=1)
        inter = (onehot[:, :, None] * z[:, None, :]).reshape(len(x), -1)
        depth = depth.reshape(-1, 1)
        return np.hstack([z, onehot, inter, depth, depth * z])

    def _gbm_design(self, x: np.ndarray, archetypes: np.ndarray, depth: np.ndarray):
        index = {a: i for i, a in enumerate(self.archetypes)}
        codes = np.array([index[a] for a in archetypes], dtype=float).reshape(-1, 1)
        return np.hstack([x, codes, depth.reshape(-1, 1)])

    def _design(self, x, archetypes, depth):
        if self.family == "logistic":
            return self._logistic_design(x, archetypes, depth)
        return self._gbm_design(x, archetypes, depth)

    def _raw_logit(self, member: _Member, design: np.ndarray) -> np.ndarray:
        if self.family == "logistic":
            return member.estimator.decision_function(design)
        return member.estimator.predict(design, raw_score=True)

    # -- prediction ----------------------------------------------------------------------

    def predict_members(
        self, x: np.ndarray, archetypes: np.ndarray | list[str], depth: np.ndarray | list[float]
    ) -> np.ndarray:
        """Calibrated probabilities, shape (n_rows, n_members)."""
        x = np.asarray(x, dtype=float)
        archetypes = np.asarray(archetypes)
        depth = np.asarray(depth, dtype=float)
        design = self._design(x, archetypes, depth)
        out = np.empty((len(x), len(self.members)))
        for j, member in enumerate(self.members):
            a, b = member.platt
            out[:, j] = _sigmoid(a * self._raw_logit(member, design) + b)
        return out

    def predict(self, x, archetypes, depth) -> np.ndarray:
        """Ensemble-mean calibrated probability per row."""
        return self.predict_members(x, archetypes, depth).mean(axis=1)

    # -- attributions --------------------------------------------------------------------

    def uplift_attributions(
        self, x_row: np.ndarray, archetype: str, depth: float
    ) -> list[tuple[str, float]]:
        """Per-feature contributions to the uplift logit `logit(a) - logit(none)`, averaged
        over ensemble members (before calibration, which is a monotone rescaling). The
        `action:<archetype>` entry is the action's own average effect."""
        x_row = np.asarray(x_row, dtype=float).reshape(1, -1)
        names = [*self.feature_names, f"action:{archetype}"]
        total = np.zeros(len(names))
        if archetype == "none":
            return [(name, 0.0) for name in names]
        for member in self.members:
            if self.family == "logistic":
                total += self._logistic_contrib(member, x_row, archetype, depth)
            else:
                total += self._gbm_contrib(member, x_row, archetype, depth)
        total /= len(self.members)
        return list(zip(names, (float(v) for v in total), strict=True))

    def _logistic_contrib(self, member, x_row, archetype, depth) -> np.ndarray:
        coef = member.estimator.coef_[0]
        p = len(self.feature_names)
        actions = [a for a in self.archetypes if a != "none"]
        k = actions.index(archetype)
        z = ((x_row - self.mean) / self.scale)[0]
        alpha = coef[p + k]
        gamma = coef[p + len(actions) + k * p : p + len(actions) + (k + 1) * p]
        delta = coef[p + len(actions) + len(actions) * p]
        eta = coef[p + len(actions) + len(actions) * p + 1 :]
        per_feature = (gamma + eta * depth) * z
        return np.append(per_feature, alpha + delta * depth)

    def _gbm_contrib(self, member, x_row, archetype, depth) -> np.ndarray:
        rows = self._gbm_design(
            np.vstack([x_row, x_row]), np.array([archetype, "none"]), np.array([depth, 0.0])
        )
        contrib = member.estimator.predict(rows, pred_contrib=True)
        diff = contrib[0] - contrib[1]
        p = len(self.feature_names)
        # columns: features..., archetype code, depth, bias
        return np.append(diff[:p], diff[p] + diff[p + 1])


def _fit_platt(raw_logit: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lr = LogisticRegression(C=1e6, max_iter=1000)
    lr.fit(raw_logit.reshape(-1, 1), y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def fit_response_model(
    family: Family,
    config: ModelsConfig,
    archetypes: list[str],
    feature_names: list[str],
    train: dict[str, np.ndarray],
    validation: dict[str, np.ndarray],
    seed: int,
) -> ResponseModel:
    """Fit a calibrated bootstrap ensemble. `train`/`validation` hold `x`, `archetype`,
    `depth`, `y` and `customer` arrays."""
    x = train["x"]
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-9] = 1.0
    model = ResponseModel(
        family=family,
        archetypes=list(archetypes),
        feature_names=list(feature_names),
        members=[],
        mean=mean,
        scale=scale,
        version="",
        training_rows=len(x),
    )
    customers = np.unique(train["customer"])
    rows_by_customer = {c: np.flatnonzero(train["customer"] == c) for c in customers}
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, len(archetypes)])))
    val_design = model._design(validation["x"], validation["archetype"], validation["depth"])
    for member_index in range(config.ensemble_size):
        sample = rng.choice(customers, size=len(customers), replace=True)
        idx = np.concatenate([rows_by_customer[c] for c in sample])
        design = model._design(x[idx], train["archetype"][idx], train["depth"][idx])
        y = train["y"][idx]
        if family == "logistic":
            estimator = LogisticRegression(
                C=config.logistic.C,
                max_iter=config.logistic.max_iter,
                solver="newton-cholesky",
                tol=1e-8,
            )
            estimator.fit(design, y)
        else:
            gbm = config.gbm
            estimator = lgb.train(
                {
                    "objective": "binary",
                    "learning_rate": gbm.learning_rate,
                    "num_leaves": gbm.num_leaves,
                    "min_data_in_leaf": gbm.min_child_samples,
                    "bagging_fraction": gbm.subsample,
                    "bagging_freq": 1,
                    "feature_fraction": gbm.colsample_bytree,
                    "lambda_l2": gbm.reg_lambda,
                    "seed": seed + member_index,
                    "deterministic": True,
                    "num_threads": 1,
                    "force_row_wise": True,
                    "verbose": -1,
                },
                lgb.Dataset(design, label=y, categorical_feature=[len(feature_names)]),
                num_boost_round=gbm.n_estimators,
            )
        member = _Member(estimator=estimator, platt=(1.0, 0.0))
        member.platt = _fit_platt(model._raw_logit(member, val_design), validation["y"])
        model.members.append(member)
    digest = hashlib.sha256()
    digest.update(json.dumps([family, config.model_dump(), archetypes, feature_names]).encode())
    digest.update(
        np.round(
            model.predict(
                validation["x"][:500], validation["archetype"][:500], validation["depth"][:500]
            ),
            12,
        ).tobytes()
    )
    model.version = f"{family}-{digest.hexdigest()[:12]}"
    return model
