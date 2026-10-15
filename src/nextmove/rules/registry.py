"""The `Constraint` protocol, its registry, and `RuleSet`, which applies a configured
constraint set to a candidate list in declared precedence order."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from nextmove.config.models import ConstraintsConfig, ConstraintSpec
from nextmove.decisions.actions import Candidate
from nextmove.decisions.context import DecisionContext

__all__ = [
    "PRECEDENCE_ORDER",
    "Constraint",
    "FilterOutcome",
    "FilteredRecord",
    "RuleSet",
    "Verdict",
    "constraint_registry",
    "register_constraint",
]

#: Conflict precedence from DECISION_ENGINE_DESIGN §4: compliance > inventory > campaign >
#: preference. A candidate excluded by several hard rules is recorded under the highest one.
PRECEDENCE_ORDER = ("compliance", "inventory", "campaign", "preference")


@dataclass(frozen=True)
class Verdict:
    """One constraint's judgement of one candidate."""

    violated: bool
    detail: str = ""
    penalty_cents: float = 0.0


@runtime_checkable
class Constraint(Protocol):
    spec: ConstraintSpec

    def evaluate(self, candidate: Candidate, context: DecisionContext) -> Verdict: ...


ConstraintFactory = Callable[[ConstraintSpec], Constraint]

_REGISTRY: dict[str, ConstraintFactory] = {}


def register_constraint(kind: str) -> Callable[[ConstraintFactory], ConstraintFactory]:
    """Decorator registering a constraint implementation under `kind`."""

    def decorator(factory: ConstraintFactory) -> ConstraintFactory:
        if kind in _REGISTRY:
            raise ValueError(f"constraint kind {kind!r} is already registered")
        _REGISTRY[kind] = factory
        return factory

    return decorator


def constraint_registry() -> dict[str, ConstraintFactory]:
    return dict(_REGISTRY)


@dataclass(frozen=True)
class FilteredRecord:
    candidate_id: str
    rule: str
    detail: str


@dataclass
class FilterOutcome:
    """Survivors in input order, the decisive exclusion per filtered candidate, soft penalties
    per survivor, and the rules that fired (filtered something or applied a penalty)."""

    survivors: list[Candidate]
    filtered: list[FilteredRecord]
    penalties_cents: dict[str, float]
    penalty_details: dict[str, list[str]] = field(default_factory=dict)
    fired_rules: list[str] = field(default_factory=list)
    constraints_considered: list[str] = field(default_factory=list)


class RuleSet:
    """A configured constraint set, ordered by precedence (stable within a class)."""

    def __init__(self, constraints: list[Constraint]) -> None:
        rank = {name: index for index, name in enumerate(PRECEDENCE_ORDER)}
        self.constraints = sorted(constraints, key=lambda c: rank[c.spec.precedence])

    @classmethod
    def from_config(cls, config: ConstraintsConfig) -> RuleSet:
        constraints = []
        for spec in config.rules:
            factory = _REGISTRY.get(spec.kind)
            if factory is None:
                raise KeyError(
                    f"constraint {spec.name!r} names unregistered kind {spec.kind!r}; "
                    f"registered: {sorted(_REGISTRY)}"
                )
            constraints.append(factory(spec))
        return cls(constraints)

    @property
    def names(self) -> list[str]:
        return [c.spec.name for c in self.constraints]

    def apply(self, candidates: list[Candidate], context: DecisionContext) -> FilterOutcome:
        survivors: list[Candidate] = []
        filtered: list[FilteredRecord] = []
        penalties: dict[str, float] = {}
        penalty_details: dict[str, list[str]] = {}
        fired: set[str] = set()
        for candidate in candidates:
            exclusion: FilteredRecord | None = None
            penalty = 0.0
            details: list[str] = []
            for constraint in self.constraints:
                verdict = constraint.evaluate(candidate, context)
                if not verdict.violated:
                    continue
                if constraint.spec.mode == "hard":
                    if exclusion is None:
                        exclusion = FilteredRecord(
                            candidate.id, constraint.spec.name, verdict.detail
                        )
                elif verdict.penalty_cents > 0:
                    penalty += verdict.penalty_cents
                    details.append(f"{constraint.spec.name}: {verdict.detail}")
                    fired.add(constraint.spec.name)
            if exclusion is not None:
                filtered.append(exclusion)
                fired.add(exclusion.rule)
            else:
                survivors.append(candidate)
                penalties[candidate.id] = penalty
                if details:
                    penalty_details[candidate.id] = details
        return FilterOutcome(
            survivors=survivors,
            filtered=filtered,
            penalties_cents=penalties,
            penalty_details=penalty_details,
            fired_rules=[name for name in self.names if name in fired],
            constraints_considered=self.names,
        )
