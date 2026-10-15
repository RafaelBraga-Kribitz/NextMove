"""Action generation: the `ActionProvider` registry (AD-13, ADR-010).

Providers expand the configured catalog into concrete, parameterized `Candidate`s for one
`DecisionContext`. Adding an archetype means registering a new provider, with zero edits to
ranking, constraint filtering or explanation (AC-13; see `nextmove.plugins.example`).
`generate_candidates` always returns `none` and `wait` (restraint is first-class) even if a
misconfigured provider set would omit them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from nextmove.config.models import ActionArchetype, ActionsConfig
from nextmove.decisions.context import DecisionContext
from nextmove.decisions.contract import CANDIDATE_SEPARATOR

__all__ = [
    "ActionProvider",
    "Candidate",
    "CatalogActionProvider",
    "action_provider_registry",
    "build_providers",
    "generate_candidates",
    "register_action_provider",
]


class Candidate(BaseModel):
    """One concrete action a policy can choose."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    archetype: str = Field(min_length=1)
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    contact: bool
    cost_cents: int = Field(ge=0)

    @property
    def discount_bps(self) -> int:
        return int(self.params.get("discount_bps", 0))


@runtime_checkable
class ActionProvider(Protocol):
    """Expands part of the action space into candidates for one context."""

    name: str

    def expand(self, context: DecisionContext) -> list[Candidate]: ...


ProviderFactory = Callable[[ActionsConfig], ActionProvider]

_REGISTRY: dict[str, ProviderFactory] = {}


def register_action_provider(name: str) -> Callable[[ProviderFactory], ProviderFactory]:
    """Decorator registering a provider factory under `name`. Re-registering a name raises."""

    def decorator(factory: ProviderFactory) -> ProviderFactory:
        if name in _REGISTRY:
            raise ValueError(f"action provider {name!r} is already registered")
        _REGISTRY[name] = factory
        return factory

    return decorator


def action_provider_registry() -> dict[str, ProviderFactory]:
    return dict(_REGISTRY)


def candidate_from_archetype(archetype: ActionArchetype) -> list[Candidate]:
    candidates = []
    for variant in archetype.variants:
        candidate_id = (
            archetype.name
            if variant.suffix is None
            else f"{archetype.name}{CANDIDATE_SEPARATOR}{variant.suffix}"
        )
        candidates.append(
            Candidate(
                id=candidate_id,
                archetype=archetype.name,
                params=dict(variant.params),
                contact=archetype.contact,
                cost_cents=archetype.cost_cents,
            )
        )
    return candidates


class CatalogActionProvider:
    """The built-in provider: every archetype and variant in `config/actions.yaml`."""

    name = "catalog"

    def __init__(self, config: ActionsConfig) -> None:
        self._candidates = [
            candidate
            for archetype in config.catalog
            for candidate in candidate_from_archetype(archetype)
        ]

    def expand(self, context: DecisionContext) -> list[Candidate]:
        return list(self._candidates)


register_action_provider("catalog")(CatalogActionProvider)


def build_providers(config: ActionsConfig, names: Iterable[str] | None = None) -> list:
    """Instantiate the named providers (default: every registered one, in name order)."""
    selected = sorted(_REGISTRY) if names is None else list(names)
    return [_REGISTRY[name](config) for name in selected]


def generate_candidates(
    context: DecisionContext, providers: Iterable[ActionProvider], config: ActionsConfig
) -> list[Candidate]:
    """All candidates for `context`, de-duplicated by id in first-seen order, with `none` and
    `wait` guaranteed present."""
    seen: dict[str, Candidate] = {}
    for provider in providers:
        for candidate in provider.expand(context):
            seen.setdefault(candidate.id, candidate)
    for archetype in config.catalog:
        if archetype.name in ("none", "wait"):
            for candidate in candidate_from_archetype(archetype):
                seen.setdefault(candidate.id, candidate)
    return list(seen.values())
