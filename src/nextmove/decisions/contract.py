"""The typed `Decision` object: the product's public contract (`docs/DECISION_ENGINE_DESIGN.md`
§3).

Every field mirrors the design document's YAML example. The contract rules from that section are
enforced here as validators rather than left to convention:

- **No fabricated field.** `expected_outcome.estimate`, `expected_outcome.interval` and
  `confidence` may be `null`, but only when `unavailable` names a reason for that exact field.
- **Restraint is first-class.** `reasoning_trace.candidates_considered` must contain `none` and at
  least one `wait` candidate (AC-1).
- **Explainable by default.** `reasoning` is non-empty and `reasoning_trace` carries the fired
  rules and the runner-up, or a stated reason why there is no runner-up (AC-4).
- **Rules bound learning.** The chosen action can never be one the trace lists as filtered by a
  hard rule.

Models are frozen and `extra="forbid"`, so a typo'd field fails loudly and a decision cannot be
mutated after it is built. `decision_json_schema()` is the JSON-schema export checked in under
`docs/api/decision.schema.json`; a contract test fails if the two drift.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "CONTRACT_VERSION",
    "ActionChoice",
    "Attribution",
    "CandidateScore",
    "Decision",
    "ExpectedOutcome",
    "FilteredCandidate",
    "PolicyInfo",
    "ReasoningTrace",
    "RunnerUp",
    "archetype_of",
    "decision_json_schema",
]

#: Bumped on any contract-breaking change (QUALITY_BAR §4: no contract-breaking API change
#: without a version bump).
CONTRACT_VERSION = "1.0.0"

#: Candidate ids are `<archetype>` or `<archetype>__<variant>` (e.g. `discount_low__1000bps`).
CANDIDATE_SEPARATOR = "__"

ParamValue = str | int | float | bool


def archetype_of(candidate_id: str) -> str:
    """The archetype a candidate id belongs to: everything before the first `__`."""
    return candidate_id.split(CANDIDATE_SEPARATOR, 1)[0]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActionChoice(_Contract):
    """The chosen action: its catalog archetype, the concrete candidate id, and its params."""

    type: str = Field(min_length=1, description="Action archetype from the action catalog.")
    candidate_id: str = Field(min_length=1, description="Concrete parameterized candidate.")
    params: dict[str, ParamValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _candidate_matches_type(self) -> ActionChoice:
        if archetype_of(self.candidate_id) != self.type:
            raise ValueError(
                f"candidate_id {self.candidate_id!r} does not belong to archetype {self.type!r}"
            )
        return self


class ExpectedOutcome(_Contract):
    """Expected incremental effect of the chosen action versus doing nothing."""

    metric: Literal["conversion_uplift"] = "conversion_uplift"
    estimate: float | None = Field(description="Point estimate; null only with a stated reason.")
    interval: tuple[float, float] | None = Field(
        description="Uncertainty interval [low, high]; null only with a stated reason."
    )
    horizon_days: int = Field(gt=0)
    expected_profit_cents: float | None = Field(
        default=None, description="Expected incremental profit in cents versus `none`."
    )

    @model_validator(mode="after")
    def _interval_brackets_estimate(self) -> ExpectedOutcome:
        if self.interval is not None:
            low, high = self.interval
            if low > high:
                raise ValueError(f"interval lower bound {low} exceeds upper bound {high}")
            if self.estimate is not None and not (low - 1e-12 <= self.estimate <= high + 1e-12):
                raise ValueError(f"estimate {self.estimate} lies outside interval {self.interval}")
        return self


class FilteredCandidate(_Contract):
    """A candidate removed by a hard constraint, and why."""

    action: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class CandidateScore(_Contract):
    """The score breakdown for one surviving candidate."""

    score: float
    uplift: float
    value_cents: float
    cost_cents: float
    risk_penalty_cents: float


class RunnerUp(_Contract):
    action: str = Field(min_length=1)
    score_gap: float = Field(ge=0.0)


class Attribution(_Contract):
    """One feature's signed contribution to the chosen action's predicted response."""

    feature: str = Field(min_length=1)
    weight: float


class ReasoningTrace(_Contract):
    """Structured, replayable trace behind `reasoning` (AC-4)."""

    candidates_considered: list[str] = Field(min_length=2)
    filtered: list[FilteredCandidate] = Field(default_factory=list)
    fired_rules: list[str] = Field(default_factory=list)
    scores: dict[str, CandidateScore]
    runner_up: RunnerUp | None
    runner_up_unavailable_reason: str | None = None
    model_attributions: list[Attribution] = Field(default_factory=list)

    @field_validator("candidates_considered")
    @classmethod
    def _restraint_is_always_considered(cls, value: list[str]) -> list[str]:
        archetypes = {archetype_of(candidate) for candidate in value}
        if "none" not in archetypes:
            raise ValueError("candidates_considered must include the `none` action")
        if "wait" not in archetypes:
            raise ValueError("candidates_considered must include a `wait` action")
        if len(set(value)) != len(value):
            raise ValueError("candidates_considered must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _trace_is_internally_consistent(self) -> ReasoningTrace:
        considered = set(self.candidates_considered)
        filtered = {item.action for item in self.filtered}
        unknown = (filtered | set(self.scores)) - considered
        if unknown:
            raise ValueError(f"trace references candidates never considered: {sorted(unknown)}")
        overlap = filtered & set(self.scores)
        if overlap:
            raise ValueError(f"filtered candidates must not be scored: {sorted(overlap)}")
        fired = {item.rule for item in self.filtered}
        if not fired <= set(self.fired_rules):
            raise ValueError("every rule that filtered a candidate must appear in fired_rules")
        if self.runner_up is None and not self.runner_up_unavailable_reason:
            raise ValueError("runner_up is null without runner_up_unavailable_reason")
        if self.runner_up is not None and self.runner_up.action not in self.scores:
            raise ValueError("runner_up must be a scored (surviving) candidate")
        return self


class PolicyInfo(_Contract):
    name: str = Field(min_length=1)
    model_versions: dict[str, str] = Field(default_factory=dict)
    config_hash: str = Field(min_length=1)


_NULLABLE_FIELDS = ("expected_outcome.estimate", "expected_outcome.interval", "confidence")


class Decision(_Contract):
    """One next-best-action decision for one customer at one point in time."""

    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    decision_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: datetime
    action: ActionChoice
    expected_outcome: ExpectedOutcome
    confidence: float | None = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
    reasoning_trace: ReasoningTrace
    constraints_considered: list[str]
    policy: PolicyInfo
    needs_human_review: bool = False
    review_reason: str | None = None
    unavailable: dict[str, str] = Field(
        default_factory=dict,
        description="Field path -> reason, for every nullable field that is null.",
    )

    @field_validator("reasoning")
    @classmethod
    def _reasoning_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning must be non-blank")
        return value

    @field_validator("as_of")
    @classmethod
    def _as_of_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _contract_rules(self) -> Decision:
        values = {
            "expected_outcome.estimate": self.expected_outcome.estimate,
            "expected_outcome.interval": self.expected_outcome.interval,
            "confidence": self.confidence,
        }
        for path in _NULLABLE_FIELDS:
            if values[path] is None and not self.unavailable.get(path, "").strip():
                raise ValueError(f"{path} is null without a reason in `unavailable`")
        stray = set(self.unavailable) - set(_NULLABLE_FIELDS)
        if stray:
            raise ValueError(f"`unavailable` names unknown fields: {sorted(stray)}")

        trace = self.reasoning_trace
        if self.action.candidate_id not in trace.candidates_considered:
            raise ValueError("chosen candidate was never considered")
        excluded = self.action.candidate_id in {item.action for item in trace.filtered}
        if excluded and not self.needs_human_review:
            # The single exception is the design's unresolvable-conflict path: every candidate,
            # restraint included, was excluded, so the engine emits `none` for a human to review.
            raise ValueError("chosen candidate was excluded by a hard constraint")
        if self.action.candidate_id not in trace.scores and not self.needs_human_review:
            raise ValueError("chosen candidate must be a scored survivor")
        if self.needs_human_review and not self.review_reason:
            raise ValueError("needs_human_review requires review_reason")
        if trace.runner_up is not None and trace.runner_up.action == self.action.candidate_id:
            raise ValueError("runner_up must differ from the chosen action")
        return self


def decision_json_schema() -> str:
    """The `Decision` JSON schema, serialized deterministically (sorted keys, 2-space indent)."""
    schema = Decision.model_json_schema()
    schema["$id"] = f"https://nextmove.local/schemas/decision/{CONTRACT_VERSION}"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"
