"""Declarative business rules: a registry of hard and soft `Constraint`s configured in
`config/constraints.yaml` and evaluated into a fired-rule trace.

Hard constraints remove candidates before ranking; soft constraints add a penalty during
ranking. Which is which is config, never code. Learning can never override a hard rule: the
decision engine ranks only the survivors `RuleSet.apply` returns (AC-2).
"""

from nextmove.rules.registry import (
    PRECEDENCE_ORDER,
    Constraint,
    FilteredRecord,
    FilterOutcome,
    RuleSet,
    Verdict,
    constraint_registry,
    register_constraint,
)

# Importing the built-ins registers them.
from nextmove.rules import builtin  # noqa: E402, F401  isort: skip

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
