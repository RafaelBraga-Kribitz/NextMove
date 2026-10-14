"""The `Policy` protocol: a policy scores the candidates that survived hard constraints.

Every policy, baselines included, sees only survivors, so no policy can choose an action a hard
rule excluded (AC-2). Scores are in cents of expected incremental profit for model-based
policies; baselines use a 1/0 preference score and say so through `uplift=None`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from nextmove.decisions.actions import Candidate
from nextmove.decisions.context import DecisionContext

__all__ = ["Policy", "ScoredCandidate", "pick", "preference_scores"]


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
    uplift: float | None = None
    uplift_interval: tuple[float, float] | None = None
    value_cents: float = 0.0
    cost_cents: float = 0.0
    risk_penalty_cents: float = 0.0
    attributions: tuple[tuple[str, float], ...] = ()
    #: Fraction of the policy's uncertainty draws in which this candidate ranked first.
    win_rate: float | None = None
    note: str | None = None
    extra: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class Policy(Protocol):
    name: str

    @property
    def model_versions(self) -> dict[str, str]: ...

    def score(
        self,
        context: DecisionContext,
        survivors: list[Candidate],
        penalties_cents: dict[str, float],
    ) -> list[ScoredCandidate]: ...


def _rank_key(item: ScoredCandidate, order: dict[str, int]) -> tuple:
    # Highest score first; ties go to restraint (no contact), then to catalog order, so
    # ranking is deterministic and never breaks a tie towards contacting the customer.
    return (-item.score, item.candidate.contact, order[item.candidate.id])


def pick(scored: list[ScoredCandidate], survivors: list[Candidate]) -> list[ScoredCandidate]:
    """Deterministically rank scored candidates, best first."""
    order = {candidate.id: index for index, candidate in enumerate(survivors)}
    return sorted(scored, key=lambda item: _rank_key(item, order))


def preference_scores(
    survivors: list[Candidate], preferred: str | None, note: str
) -> list[ScoredCandidate]:
    """1/0 scores for a baseline that prefers one candidate id (falling back to `none`)."""
    ids = {candidate.id for candidate in survivors}
    target = preferred if preferred in ids else "none"
    reason = note if target == preferred else f"{note}; not allowed now, so doing nothing"
    return [
        ScoredCandidate(
            candidate=candidate,
            score=1.0 if candidate.id == target else 0.0,
            note=reason if candidate.id == target else None,
        )
        for candidate in survivors
    ]
