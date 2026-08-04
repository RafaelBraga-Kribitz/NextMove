# ADR 001: Modular Monolith Over Services

## Status

Accepted — 2026-07-25 (ratifies OD-1). Derives from locked decision AD-14
(`docs/ARCHITECTURAL_DIRECTION.md` §5, "Modular monolith package boundaries in one repo").

This ratification follows a per-OD review confirming no substantive contradiction between
OPEN_DECISIONS.md's OD-1 recommendation and the locked ADR set. AD-14 already encodes option A
as the system's package structure; this ADR closes the procedural gap — OD-1 was a recommendation
pending formal ratification, not a live architectural debate. It is ratified as recommended,
without re-litigation.

## Context

OD-1 asked whether NextMove should ship as a modular monolith in one container, as 2-3 services
(decision API, pipeline worker, dashboard), or as full microservices. The choice determines repo
layout, testing strategy, and — most importantly at this project's scale — how much engineering
time goes to plumbing (service discovery, network contracts, deployment topology) versus product
depth (decision quality, explanation faithfulness, evaluation rigor).

AD-14 already answers this question at the architecture level: ten package boundaries
(`ingest / features / segmentation / models / decisions / rules / policies / explain / evaluate /
api`) live inside one repository, one deployable container. That decision was made before OD-1 was
formally ratified because the architecture had to commit to a shape to be reviewable at all. This
ADR is the record that confirms OD-1's own trade-off analysis reaches the same conclusion AD-14
already encodes, so no contradiction exists and no rework is required.

The core risk this option accepts is boundary erosion: without enforcement, "one repo" tends to
decay into "one undifferentiated ball of code" over time, especially under solo development where
no code-review partner catches a shortcut import.

## Decision

Ship NextMove as a modular monolith: one Python repository, one deployable API container, with the
ten package boundaries from AD-14 enforced as real module boundaries, not just directory
conventions. Every plugin point (`ActionProvider`, `Model`, `Policy`, `Constraint`,
`ClusteringCandidate`, `MCDAMethod`, `IngestAdapter`, `Explainer`) is a typed registry designed as
if it could be extracted into a service later — but none is a network boundary now. Boundary
discipline between packages is enforced mechanically by import-linting in CI, not by convention or
code review alone, because a solo project has no second reviewer to catch drift.

## Consequences

The acknowledged risk is blurred package boundaries without discipline — a monolith's classic
failure mode is that anything can import anything, and over months of iteration the boundaries
that looked clean at day one quietly disappear. This project mitigates that risk concretely and in
the same phase this ADR ships in: the SIM-02 import-linter contract (delivered in plan 01-04)
mechanically fails CI if `models/`, `decisions/`, `policies/`, or `features/` import
`simulator` internals, and the same contract-enforcement pattern extends to the other nine package
boundaries as they gain real implementations. The mitigation is not aspirational — it is a test
that runs on every commit.

The upside is that portfolio value comes from the interfaces (typed registries, contract-first
package boundaries), not from network hops between services that would only exist to demonstrate
"I can write a service" — which the reviewer would recognize as ceremony at this scale, not
substance.

## Alternatives Considered

- **Option B — 2-3 services** (decision API, pipeline worker, dashboard) was rejected: it
  demonstrates service-oriented thinking but doubles the operational surface (deployment, service
  discovery, network contracts) for a product with a single-operator user base and no throughput
  requirement that would justify horizontal service scaling.
- **Option C — full microservices** was rejected outright: it is pure cost at this project's scale
  and actively violates the production-realism principle — a reviewer evaluating engineering
  judgment would read microservices for a solo-built decision engine as over-engineering, not
  rigor.
