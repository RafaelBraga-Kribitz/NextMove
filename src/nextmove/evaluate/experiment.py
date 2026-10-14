"""The randomized A/B/n experiment that produces the response models' training data.

Over the whole post-warmup horizon (ADR-012), every eligible customer is assigned, once
per `experiment_every_days`, one action drawn uniformly at random from the candidates that
survived the hard constraints. Because assignment is random given the observed context, the
log supports unconfounded response models; because it respects the constraints, it is an
experiment a real retailer could actually run.

Rows are labelled `train`, `validation` or `test` by the temporal windows: models train on
`train`, calibrate and are selected on `validation`, and report out-of-time prediction metrics
on `test`. The policy replay over the test window is a separate rollout.

The written `experiment_log` holds only what a business would observe: the context features,
the assigned action and whether the customer bought. Ground-truth probabilities never enter it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from nextmove.config.loader import ResolvedConfig
from nextmove.decisions.actions import build_providers
from nextmove.decisions.assembly import ContextStore
from nextmove.evaluate.rollout import Choice, RolloutSpec, rollout
from nextmove.evaluate.world import OutcomeOracle
from nextmove.models.features import context_feature_names, context_row
from nextmove.rules import RuleSet
from nextmove.storage import Stage, Zone, resolve_table_path, write_frame

__all__ = ["EXPERIMENT_COLUMNS", "run_experiment"]

#: Observable columns kept in the log, besides the model features.
EXPERIMENT_COLUMNS = (
    "customer_id",
    "day",
    "split",
    "primary_category",
    "candidate_id",
    "archetype",
    "discount_bps",
    "contact",
    "n_survivors",
    "prior_contacts",
    "converted",
)


def _random_chooser(seed: int):
    def choose(day, contexts, outcomes):
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, day])))
        picks = rng.random(len(contexts))
        return [
            Choice(outcome.survivors[int(pick * len(outcome.survivors))])
            for pick, outcome in zip(picks, outcomes, strict=True)
        ]

    return choose


def run_experiment(resolved: ResolvedConfig, root: Path | None = None) -> Path:
    config = resolved.config
    evaluation = config.evaluation
    train_end, validation_end, horizon = evaluation.windows(config.simulator.horizon_days)
    days = list(range(evaluation.warmup_days, horizon, evaluation.experiment_every_days))
    store = ContextStore(resolved, root, days=days, business_reference_cutoff=train_end)
    oracle = OutcomeOracle(resolved, root)
    categories = store.categories
    names = context_feature_names(categories)
    frame = rollout(
        store,
        oracle,
        RuleSet.from_config(config.constraints),
        build_providers(config.actions, ["catalog"]),
        config.actions,
        _random_chooser(evaluation.seeds.experiment),
        RolloutSpec(
            days=days,
            outcome_seed=evaluation.seeds.outcomes,
            record_features=lambda context: context_row(context, categories),
            feature_names=names,
        ),
    )
    frame["split"] = np.select(
        [frame["day"] < train_end, frame["day"] < validation_end],
        ["train", "validation"],
        default="test",
    )
    frame = frame[[*EXPERIMENT_COLUMNS, *names]]
    frame["discount_bps"] = frame["discount_bps"].astype("int64")
    frame["day"] = frame["day"].astype("int64")
    frame["n_survivors"] = frame["n_survivors"].astype("int64")
    frame["prior_contacts"] = frame["prior_contacts"].astype("int64")
    return write_frame(
        frame,
        "experiment_log",
        Zone.EXPERIMENT,
        ("day", "customer_id"),
        resolved,
        Stage.EXPERIMENT,
        input_paths=(
            resolve_table_path("feature_grid", Zone.FEATURES, root),
            resolve_table_path("events", Zone.CANONICAL, root),
        ),
        root=root,
    )
