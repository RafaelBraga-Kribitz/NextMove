# ADR 010: Fixed Action Archetype Catalog

## Status

Accepted — 2026-07-25 (ratifies OD-10). Derives from locked decision AD-06
(`docs/ARCHITECTURAL_DIRECTION.md` §"Decision Engine", "Decision engine emits the typed Decision
object").

This ratification follows a per-OD review confirming no substantive contradiction with the locked
decision set. AD-06 already commits the decision engine to generating candidate actions from an
action catalog and ranking them by expected constrained profit; this ADR closes the procedural gap
by ratifying the catalog's fixed shape for MVP. It is ratified as recommended, without
re-litigation.

## Context

OD-10 asked how large the MVP's action space should be. A huge, richly parameterized action space
makes ranking and evaluation intractable — every additional dimension multiplies the candidate set
the policy must score and the 3WD gateway must eventually validate, and a combinatorially large
space makes it much harder to reason about whether the policy's rankings are sound. A tiny,
rigid action space, on the other hand, makes the demo trivial and undersells the product's central
claim of covering a meaningful range of real interventions.

The resolution adopted elsewhere in this project's decision set narrows the scope further: per
DEC-04 and the resolution recorded in `.planning/INGEST-CONFLICTS.md`, timing and channel are fixed
*parameters* of action archetypes in v1, not dimensions the policy optimizes over — the policy ranks
over archetypes and does not search a delay/channel grid. That resolved conflict directly informs
how OD-10's action catalog is structured: the catalog needs to be large enough to express real
timing/channel variation as archetype parameters, without needing to become large enough to
*optimize* over that variation, which is deferred to v2 (POL-02).

## Decision

Fix the MVP action catalog to approximately eight archetypes: `none`, `wait`, `recommend`, `bundle`,
two discount tiers, `email-now`, and `email-delayed`. Each archetype expands into concrete,
parameterized candidates via the `ActionProvider` registry (AD-13) using small parameter grids —
enough variation within each archetype to be meaningful (e.g., which category to recommend, which
discount tier to apply) without the catalog itself growing unbounded. The registry is the explicit
escape hatch: adding a new archetype later is a new `ActionProvider` implementation, requiring zero
changes to the ranking, constraint-filtering, or explanation code that already exists.

Per DEC-04, timing (`send_delay_hours`) and channel are carried as fixed parameters on the relevant
archetypes (`email-now` vs. `email-delayed` are themselves the timing choice; channel is a bundle
parameter) rather than as separate dimensions the policy searches over — this is what lets UC1
render `timing: +6h` in the `Decision` contract's `action.params` without requiring a delay-grid
search in the ranking policy.

## Consequences

This keeps the ranking and evaluation surface tractable for the MVP: roughly eight archetypes times
small per-archetype parameter grids is a candidate set the policy can score exhaustively, and the
3WD gateway can validate experiments over without needing approximate or sampled evaluation. It also
keeps the explanation engine's job tractable — a bounded candidate set means the "chosen vs.
runner-up" comparison AD-15 requires is always over a comprehensible set of alternatives, not an
effectively infinite one.

The accepted limitation is that the MVP genuinely cannot optimize timing or channel as independent
decision dimensions — a customer who would respond best to a discount delivered at hour 3 rather
than hour 6 is not distinguishable from one who prefers hour 6, because the policy never searches
that axis in v1. This is the explicit, disclosed scope boundary that POL-02 (timing/channel as
optimized dimensions) exists to remove in v2, revisited only after policy evaluation on the fixed
catalog works and is trusted.

## Alternatives Considered

- **A larger or fully parameterized action space** (searching timing and channel as continuous or
  fine-grained dimensions) was rejected for MVP: it would multiply the candidate set the ranking
  policy and 3WD gateway must handle before either is proven correct on the simpler fixed-archetype
  case, and it was explicitly deferred to v2 per the resolved timing/channel conflict.
