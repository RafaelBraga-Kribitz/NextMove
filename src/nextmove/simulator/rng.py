"""The simulator's only source of randomness: per-entity, order-independent NumPy generators.

Every stochastic draw anywhere in `nextmove.simulator` must come from `entity_rng` or
`stream_rng`. Both build a `numpy.random.Generator` from an explicit, ordered list of
integers handed to `numpy.random.default_rng` as `SeedSequence` entropy (RESEARCH Pattern 1):
`[entity_id, seed, domain_ordinal]` (and `tick` for the per-tick variant). This is what makes
a customer's draws depend on nothing but their own id, the configured seed, and the domain —
never on how many other customers exist, what order they are visited in, or which process
draws for them. Two reruns with the same config therefore produce byte-identical simulator
output regardless of iteration order or parallelism (ENG-04).

Do not call NumPy's legacy module-level seeding function (`numpy.random.seed`) or its
module-level draw helpers (`numpy.random.rand`, `numpy.random.choice`, ...) anywhere in this
package: they share one process-global state, so the value a customer receives would depend
on how many draws happened before them — silently wrong the moment the population grows, the
iteration order changes, or a loop is parallelized (RESEARCH "Anti-Patterns to Avoid";
T-01-17). Do not use the Python standard library `random` module either — same global-state
problem, and it derives from a different stream than NumPy's, so it could never be reconciled
with `entity_rng`'s guarantees.

Any sequence derived from a `set` or from `dict` key order must be explicitly sorted before it
is allowed to influence a draw (for example, before it determines the order entities are
visited in, or before it is folded into entropy): Python randomizes string hashing per
process, so unsorted set/dict-derived order is itself a nondeterminism source independent of
the RNG substrate.
"""

from enum import IntEnum, StrEnum

import numpy as np
from numpy.random import Generator

from nextmove.config.models import SeedsConfig


class SeedDomain(StrEnum):
    """One member per `SeedsConfig` field. Each domain draws from an independent stream even
    for the same entity id, because the domain ordinal is folded into the entropy list."""

    world = "world"
    organic = "organic"
    response = "response"
    campaign = "campaign"


class _SeedDomainOrdinal(IntEnum):
    """Stable integer index for each `SeedDomain` member, used as entropy so two domains
    sharing an entity id and a seed still produce independent streams. Ordinals are fixed
    once assigned and must never be renumbered — doing so would change every draw derived
    through them, breaking ENG-04's byte-identical-rerun claim for any previously generated
    dataset."""

    world = 0
    organic = 1
    response = 2
    campaign = 3


def entity_rng(domain: SeedDomain, entity_id: int, seeds: SeedsConfig) -> Generator:
    """Return a `Generator` whose draw sequence depends only on `domain`, `entity_id`, and the
    configured seed for that domain.

    Equal `(domain, entity_id, seeds)` always yields equal draw sequences, in this process or
    any other. Two different entity ids under the same domain and seed produce independent
    sequences (they are unlikely to collide by construction — `SeedSequence` decorrelates its
    inputs). The same entity id under two different domains also produces independent
    sequences, because the domain ordinal is part of the entropy.
    """
    seed = getattr(seeds, domain.value)
    ordinal = _SeedDomainOrdinal[domain.value]
    return np.random.default_rng([entity_id, seed, int(ordinal)])


def stream_rng(
    domain: SeedDomain, entity_id: int, tick: int, seeds: SeedsConfig
) -> Generator:
    """Return a `Generator` for one entity's draws at one simulated tick.

    Folds `tick` into the same entropy list `entity_rng` uses, so each tick gets its own
    independent stream for a given entity and domain — a customer's tick-7 draws never repeat
    or correlate with their tick-3 draws, and the sequence is still immune to iteration order
    and population size.
    """
    seed = getattr(seeds, domain.value)
    ordinal = _SeedDomainOrdinal[domain.value]
    return np.random.default_rng([entity_id, seed, int(ordinal), tick])
