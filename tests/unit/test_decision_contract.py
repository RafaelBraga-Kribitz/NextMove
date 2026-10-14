"""Contract tests for the typed `Decision` object (AC-1 schema half, AC-4)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nextmove.decisions.contract import Decision, archetype_of, decision_json_schema

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "decision.schema.json"


def _example() -> dict:
    """The design document's §3 example, completed with the fields the contract adds."""
    return {
        "decision_id": "d-0001",
        "customer_id": "c_10482",
        "as_of": "2026-07-24T18:00:00Z",
        "action": {
            "type": "bundle",
            "candidate_id": "bundle__email",
            "params": {"channel": "email", "send_delay_hours": 6},
        },
        "expected_outcome": {
            "metric": "conversion_uplift",
            "estimate": 0.038,
            "interval": [0.011, 0.065],
            "horizon_days": 7,
            "expected_profit_cents": 120.5,
        },
        "confidence": 0.82,
        "reasoning": "High purchase intent without incentive; discount suppressed by low stock.",
        "reasoning_trace": {
            "candidates_considered": [
                "discount_low__1000bps",
                "bundle__email",
                "recommend__top_seller",
                "wait",
                "none",
            ],
            "filtered": [
                {
                    "action": "discount_low__1000bps",
                    "rule": "inventory_scarcity_gate",
                    "detail": "stock < threshold for cart item",
                }
            ],
            "fired_rules": ["inventory_scarcity_gate"],
            "scores": {
                name: {
                    "score": score,
                    "uplift": 0.01,
                    "value_cents": 1.0,
                    "cost_cents": 0.0,
                    "risk_penalty_cents": 0.0,
                }
                for name, score in [
                    ("bundle__email", 3.0),
                    ("recommend__top_seller", 2.0),
                    ("wait", 0.5),
                    ("none", 0.0),
                ]
            },
            "runner_up": {"action": "recommend__top_seller", "score_gap": 1.0},
            "model_attributions": [{"feature": "cart_active", "weight": 0.31}],
        },
        "constraints_considered": [
            "inventory_scarcity_gate",
            "frequency_cap",
            "discount_ceiling",
        ],
        "policy": {
            "name": "expected_value_v1",
            "model_versions": {"response": "abc"},
            "config_hash": "deadbeef",
        },
    }


def test_design_document_example_validates() -> None:
    decision = Decision.model_validate(_example())
    assert decision.action.type == "bundle"
    assert decision.reasoning_trace.runner_up is not None


@pytest.mark.parametrize("dropped", ["none", "wait"])
def test_restraint_actions_must_be_considered(dropped: str) -> None:
    payload = _example()
    trace = payload["reasoning_trace"]
    trace["candidates_considered"].remove(dropped)
    trace["scores"].pop(dropped)
    with pytest.raises(ValidationError, match=f"`{dropped}`"):
        Decision.model_validate(payload)


def test_reasoning_must_be_non_blank() -> None:
    payload = _example()
    payload["reasoning"] = "   "
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)


def test_null_estimate_requires_reason() -> None:
    payload = _example()
    payload["expected_outcome"]["estimate"] = None
    with pytest.raises(ValidationError, match="without a reason"):
        Decision.model_validate(payload)
    payload["unavailable"] = {"expected_outcome.estimate": "model not trained for this action"}
    assert Decision.model_validate(payload).expected_outcome.estimate is None


def test_null_confidence_requires_reason() -> None:
    payload = _example()
    payload["confidence"] = None
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)


def test_runner_up_required_or_explained() -> None:
    payload = _example()
    payload["reasoning_trace"]["runner_up"] = None
    with pytest.raises(ValidationError, match="runner_up"):
        Decision.model_validate(payload)
    payload["reasoning_trace"]["runner_up_unavailable_reason"] = "only one survivor"
    Decision.model_validate(payload)


def test_chosen_action_cannot_be_filtered() -> None:
    payload = _example()
    payload["action"] = {"type": "discount_low", "candidate_id": "discount_low__1000bps"}
    with pytest.raises(ValidationError, match="hard constraint"):
        Decision.model_validate(payload)


def test_filtering_rule_must_be_listed_as_fired() -> None:
    payload = _example()
    payload["reasoning_trace"]["fired_rules"] = []
    with pytest.raises(ValidationError, match="fired_rules"):
        Decision.model_validate(payload)


def test_interval_must_bracket_estimate() -> None:
    payload = _example()
    payload["expected_outcome"]["interval"] = [0.05, 0.06]
    with pytest.raises(ValidationError, match="outside interval"):
        Decision.model_validate(payload)


def test_unknown_fields_are_rejected() -> None:
    payload = _example()
    payload["surprise"] = 1
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)


def test_naive_timestamp_rejected() -> None:
    payload = _example()
    payload["as_of"] = "2026-07-24T18:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        Decision.model_validate(payload)


def test_human_review_requires_reason() -> None:
    payload = copy.deepcopy(_example())
    payload["needs_human_review"] = True
    with pytest.raises(ValidationError, match="review_reason"):
        Decision.model_validate(payload)


def test_archetype_of() -> None:
    assert archetype_of("discount_low__1000bps") == "discount_low"
    assert archetype_of("none") == "none"


def test_roundtrip_json_is_lossless() -> None:
    decision = Decision.model_validate(_example())
    again = Decision.model_validate_json(decision.model_dump_json())
    assert again == decision


def test_checked_in_json_schema_matches_contract() -> None:
    """The exported schema under docs/api/ must equal the live contract (regenerate with
    `just schema`)."""
    assert SCHEMA_PATH.read_text(encoding="utf-8") == decision_json_schema()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "reasoning_trace" in schema["required"]
