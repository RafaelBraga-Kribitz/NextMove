"""B1 / AC-7: viability constraints, TOPSIS ranking and the per-run MCDA scorecard."""

import numpy as np
import pandas as pd

from nextmove.config.loader import load_config
from nextmove.config.models import McdaCriterion
from nextmove.segmentation.mcda import topsis
from nextmove.segmentation.segment import rfm_rules, run_segmentation

MCDA = load_config("demo").config.mcda


def test_topsis_prefers_dominant_alternative() -> None:
    criteria = {
        "a": McdaCriterion(weight=1.0, direction="benefit"),
        "b": McdaCriterion(weight=1.0, direction="cost"),
    }
    scores = topsis(
        {"good": {"a": 9, "b": 1}, "bad": {"a": 1, "b": 9}, "mid": {"a": 5, "b": 5}}, criteria
    )
    assert scores["good"] > scores["mid"] > scores["bad"]
    assert scores["good"] == 1.0 and scores["bad"] == 0.0


def _customers(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    buyer = rng.random(n) < 0.4
    return pd.DataFrame(
        {
            "customer_id": [str(i) for i in range(n)],
            "rfm_recency_days": np.where(buyer, rng.integers(1, 120, n), np.nan),
            "rfm_frequency_count": np.where(buyer, rng.integers(1, 4, n), 0),
            "rfm_monetary_cents": np.where(buyer, rng.integers(2000, 20000, n), 0),
            "session_visits_count": rng.poisson(np.where(buyer, 6, 2)),
            "price_sensitivity_proxy": rng.random(n),
            "contacts_total": rng.poisson(30, n),
        }
    )


def test_rfm_rules_assigns_readable_tiers() -> None:
    labels = rfm_rules(_customers(400))
    assert set(labels) <= {0, 1, 2, 3}


def test_segmentation_scorecard_and_viability() -> None:
    frame = _customers(800)
    result = run_segmentation(frame, MCDA, seed=1)
    card = result.scorecard
    assert card["chosen"] == result.chosen
    assert card["ranking"][0] == result.chosen
    assert set(card["weights"]) == set(MCDA.criteria)
    chosen = card["candidates"][result.chosen]
    assert chosen["viable"]
    shares = np.bincount(result.labels) / len(result.labels)
    assert shares[shares > 0].min() >= MCDA.segmentation.min_segment_share
    assert (shares > 0).sum() <= MCDA.segmentation.max_segments
    for name, candidate in card["candidates"].items():
        if not candidate["viable"]:
            assert name not in card["topsis_closeness"]
    assert len(card["sensitivity"]) == 2 * len(MCDA.criteria)
    assert set(result.segment_names) == set(result.labels.tolist())


def test_too_small_population_falls_back_to_single_viable_segment() -> None:
    result = run_segmentation(_customers(12), MCDA, seed=1)
    if result.chosen == "all_customers":
        assert set(result.labels.tolist()) == {0}
        assert "reason" in result.scorecard
