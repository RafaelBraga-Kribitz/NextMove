"""D2 / AC-8, AC-9: the 3WD gateway on a fixture suite, plus Delay escalation."""

import pytest

from nextmove.config.loader import load_config
from nextmove.evaluate.gateway import Estimate, Readout, adjudicate

CONFIG = load_config("tiny").config
T = CONFIG.experiments  # mde 0.5, margin 0.25, conversion_rate max_drop 0.002, budget 28
OK_GUARDRAIL = {"conversion_rate": Estimate(0.0, -0.001, 0.001)}

FIXTURES = [
    # name, primary (point, low, high), guardrails, days, expected verdict, expected case
    ("clear_win", (1.2, 0.6, 1.8), OK_GUARDRAIL, 14, "accept", "clear_win"),
    ("clear_loss", (-1.0, -1.6, -0.4), OK_GUARDRAIL, 14, "reject", "clear_loss"),
    ("in_margin", (0.05, -0.2, 0.2), OK_GUARDRAIL, 14, "reject", "in_margin"),
    (
        "conflicting_metric",
        (1.2, 0.6, 1.8),
        {"conversion_rate": Estimate(-0.002, -0.004, 0.0)},
        14,
        "delay",
        "conflicting_metrics",
    ),
    (
        "guardrail_breach",
        (1.2, 0.6, 1.8),
        {"conversion_rate": Estimate(-0.005, -0.006, -0.003)},
        14,
        "reject",
        "guardrail_breach",
    ),
    ("inconclusive", (0.4, -0.3, 1.1), OK_GUARDRAIL, 14, "delay", "inconclusive"),
    ("small_but_positive", (0.3, 0.1, 0.5), OK_GUARDRAIL, 14, "delay", "inconclusive"),
]


@pytest.mark.parametrize(("name", "primary", "guardrails", "days", "verdict", "case"), FIXTURES)
def test_ac8_fixture_suite(name, primary, guardrails, days, verdict, case) -> None:
    readout = Readout(name, "ranking_weight_nudge", Estimate(*primary), guardrails, days)
    result = adjudicate(readout, T, CONFIG.autonomy)
    assert (result.verdict, result.case) == (verdict, case), result.reason


def test_ac9_delay_past_budget_escalates() -> None:
    readout = Readout("slow", "policy_promotion", Estimate(0.4, -0.3, 1.1), OK_GUARDRAIL, 28)
    result = adjudicate(readout, T, CONFIG.autonomy)
    assert result.verdict == "needs_human_review"
    assert "escalated" in result.reason


def test_conflicting_delay_past_budget_also_escalates() -> None:
    readout = Readout(
        "conflict",
        "policy_promotion",
        Estimate(1.2, 0.6, 1.8),
        {"conversion_rate": Estimate(-0.002, -0.004, 0.0)},
        40,
    )
    assert adjudicate(readout, T, CONFIG.autonomy).verdict == "needs_human_review"


@pytest.mark.parametrize(
    ("change_type", "action"),
    [
        ("ranking_weight_nudge", "auto_apply"),
        ("policy_promotion", "requires_human_signoff"),
        ("discount_ceiling_change", "human_only"),
    ],
)
def test_accept_respects_autonomy_tiers(change_type, action) -> None:
    readout = Readout("win", change_type, Estimate(1.2, 0.6, 1.8), OK_GUARDRAIL, 7)
    assert adjudicate(readout, T, CONFIG.autonomy).autonomy == action


def test_missing_guardrail_blocks_auto_accept() -> None:
    readout = Readout("win", "ranking_weight_nudge", Estimate(1.2, 0.6, 1.8), {}, 7)
    assert adjudicate(readout, T, CONFIG.autonomy).verdict == "delay"
