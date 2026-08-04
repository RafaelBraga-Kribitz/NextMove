# ADR 003: Simulator as an Import-Isolated Package in the Same Repository

## Status

Accepted — 2026-07-25 (ratifies OD-3). Derives from locked decision AD-12
(`docs/ARCHITECTURAL_DIRECTION.md` §"Simulator", "cross-cutting component with a documented
assumption log").

This ratification follows a per-OD review confirming no substantive contradiction with the locked
decision set. AD-12 already establishes the simulator as a same-repository, cross-cutting
component; this ADR closes the procedural gap by adding the explicit import-isolation contract.
It is ratified as recommended, without re-litigation.

## Context

OD-3 asked where the simulator lives relative to the rest of the product: inside the same
repository as an isolated package, or as a separate sibling repository entirely. The stakes are
contamination risk, stated in the source's own terms: if simulator internals are importable by
`models/`, results are fake. A model that can see the simulator's latent-trait response functions
directly — rather than only the events those functions produce — is not learning to predict
behavior, it is memorizing the generator. Every downstream claim this project makes (uplift
estimates, policy comparisons, the 3WD experiment verdicts) rests on that boundary holding.

A separate repository (option B) would give hard isolation by construction — there would be no
import path to violate because there would be no shared Python environment. But it comes at a real
cost: painful versioning (which simulator commit produced which dataset?), a second install step
for any reviewer trying to reproduce results, and friction for the single-operator development
workflow this project assumes. Same-repository isolation (option A) keeps `make reproduce`
literally one command, at the cost of needing active enforcement rather than getting isolation for
free.

## Decision

Adopt option A: the simulator lives in the same repository, as its own package
(`src/nextmove/simulator/`), with import isolation enforced mechanically rather than by convention.
The exact contract, shipping in plan 01-04, is an import-linter rule forbidding four source
packages — `nextmove.models`, `nextmove.decisions`, `nextmove.policies`, and `nextmove.features` —
from importing the forbidden module `nextmove.simulator`. This is a CI-enforced contract, not a
code-review norm: any commit that adds a forbidden import fails the build before it can merge.

## Consequences

The isolation guarantee is itself a portfolio artifact — a reviewer can inspect the import-linter
configuration and verify mechanically, without reading a single line of model code, that the
project's core honesty claim (models never see the generator, only its outputs) is enforced rather
than merely asserted. This is stronger evidence than a docstring promise.

The cost accepted is that this isolation must be actively maintained: a new package added later
that legitimately needs simulator access (unlikely, but possible for a future evaluation-only tool)
requires updating the contract deliberately rather than the isolation holding automatically as it
would with a separate repository. Reproducibility stays a single `git clone` plus one environment,
which matters for a portfolio artifact a reviewer will actually try to run.

## Alternatives Considered

- **Option B — separate repository** was rejected: hard isolation by construction, but it fragments
  versioning (a dataset's provenance would need to reference a commit in a second repository) and
  turns `make reproduce` into a multi-repository setup step, which works against the project's
  stated reproducibility goal.
