"""The three-way-decision (3WD) experimentation gateway with static thresholds (D2, ADR-008).

A readout of a candidate change against its control (point estimate and confidence interval of
the primary metric, plus guardrail metrics) is adjudicated as **Accept**, **Reject** or
**Delay**; a Delay that has run past its budget escalates to **needs_human_review** (AC-9).
Thresholds come from `config/experiments.yaml`. The verdict then meets the autonomy tiers of
`config/autonomy.yaml` (ADR-009): only a Tier 1 change auto-applies on Accept.

Rules, in order:

1. a guardrail whose whole CI lies below `-max_drop` -> **Reject** (guardrail breach);
2. primary CI entirely below zero -> **Reject** (clear loss);
3. primary CI entirely inside `[-margin, +margin]` -> **Reject** (practically equivalent);
4. primary CI above zero and point >= MDE, with no guardrail CI reaching below `-max_drop`
   -> **Accept** (clear win);
5. a primary win with a guardrail CI that reaches below `-max_drop` -> **Delay** (conflicting
   metrics);
6. anything else -> **Delay** (inconclusive);
7. a Delay with `days_running >= delay_budget_days` -> **needs_human_review**.

The thresholds are passed in, not read from module state, so a future traffic- or
season-aware threshold source can replace the static config without changing this interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from nextmove.config.models import AutonomyConfig, ExperimentsConfig

__all__ = ["Estimate", "GatewayVerdict", "Readout", "adjudicate", "autonomy_action"]

Verdict = Literal["accept", "reject", "delay", "needs_human_review"]


@dataclass(frozen=True)
class Estimate:
    point: float
    ci_low: float
    ci_high: float

    def __post_init__(self) -> None:
        if self.ci_low > self.ci_high:
            raise ValueError("ci_low must not exceed ci_high")


@dataclass(frozen=True)
class Readout:
    name: str
    change_type: str
    primary: Estimate
    guardrails: dict[str, Estimate] = field(default_factory=dict)
    days_running: int = 0


@dataclass(frozen=True)
class GatewayVerdict:
    verdict: Verdict
    reason: str
    case: str
    autonomy: str


def autonomy_action(verdict: Verdict, change_type: str, autonomy: AutonomyConfig) -> str:
    if verdict != "accept":
        return "no_change" if verdict == "reject" else "keep_collecting"
    if change_type in autonomy.tier_1_auto:
        return "auto_apply"
    if change_type in autonomy.tier_2_human_signoff:
        return "requires_human_signoff"
    if change_type in autonomy.tier_3_human_only:
        return "human_only"
    return "requires_human_signoff"


def adjudicate(
    readout: Readout, thresholds: ExperimentsConfig, autonomy: AutonomyConfig
) -> GatewayVerdict:
    primary = readout.primary
    margin = thresholds.indifference_margin
    breached: list[str] = []
    at_risk: list[str] = []
    for guardrail in thresholds.guardrails:
        estimate = readout.guardrails.get(guardrail.metric)
        if estimate is None:
            at_risk.append(f"{guardrail.metric} (not measured)")
            continue
        if estimate.ci_high < -guardrail.max_drop:
            breached.append(guardrail.metric)
        elif estimate.ci_low < -guardrail.max_drop:
            at_risk.append(guardrail.metric)

    def result(verdict: Verdict, case: str, reason: str) -> GatewayVerdict:
        if verdict == "delay" and readout.days_running >= thresholds.delay_budget_days:
            return GatewayVerdict(
                "needs_human_review",
                f"{reason}; still inconclusive after {readout.days_running} days "
                f"(budget {thresholds.delay_budget_days}), escalated for human review",
                f"{case}_past_budget",
                "human_review",
            )
        return GatewayVerdict(
            verdict, reason, case, autonomy_action(verdict, readout.change_type, autonomy)
        )

    if breached:
        return result("reject", "guardrail_breach", f"guardrail breached: {', '.join(breached)}")
    if primary.ci_high < 0:
        return result("reject", "clear_loss", "the whole confidence interval is below zero")
    if -margin <= primary.ci_low and primary.ci_high <= margin:
        return result(
            "reject",
            "in_margin",
            f"the confidence interval lies inside the +/-{margin:g} indifference margin",
        )
    if primary.ci_low > 0 and primary.point >= thresholds.mde:
        if at_risk:
            return result(
                "delay",
                "conflicting_metrics",
                f"primary metric wins but guardrail(s) at risk: {', '.join(at_risk)}",
            )
        return result("accept", "clear_win", f"CI above zero and effect >= MDE {thresholds.mde:g}")
    return result("delay", "inconclusive", "the confidence interval is too wide to decide")
