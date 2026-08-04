# ADR 006: Propensity-Delta Uplift Approximation in MVP

## Status

Accepted — 2026-07-25 (ratifies OD-6). Derives from locked decision AD-08
(`docs/ARCHITECTURAL_DIRECTION.md` §"Optimization Layer", "Expected-value ranking in MVP, bandit as
guardrailed stretch").

This ratification follows a per-OD review confirming no substantive contradiction with the locked
decision set. AD-08 already commits the MVP ranking policy to expected-value ranking built on
calibrated response predictions rather than a dedicated uplift model; this ADR closes the
procedural gap by ratifying the specific approximation method those predictions feed. It is
ratified as recommended, without re-litigation.

## Context

OD-6 asked how the whole utility function's `E[uplift]` term should be estimated in the MVP: as a
simple delta between two response-model predictions, or by training dedicated uplift learners
(T-learner, X-learner) from the start. This is not a cosmetic modeling choice — the entire ranking
policy's expected-value calculation rests on this number, so getting the approximation's error
characteristics right, or at least measured, matters more than getting the point estimate exactly
right on day one.

Option A approximates uplift as `P(convert | action) − P(convert | none)`, computed from the same
calibrated response models the decision engine already trains, with the approximation error against
simulator ground-truth uplift quantified and reported. Option B commits to true uplift learners
(T-/X-learner) immediately, which is statistically more correct but front-loads real delicacy —
these estimators are more data-hungry, harder to calibrate, and slower to validate — and would slow
the entire MVP loop before the rest of the pipeline (features, rules, evaluation) even exists to
validate against.

## Decision

Adopt option A. The MVP approximates uplift as the delta between two calibrated response-model
predictions — `P(convert | action) − P(convert | none)` — rather than training dedicated uplift
learners. Because the simulator's response functions are latent-trait driven and documented, the
true counterfactual uplift is computable per `(customer, action)` pair in simulation, which makes
it possible to measure exactly how wrong this approximation is rather than merely assume it is
close enough. That approximation-error analysis is promoted to a headline evaluation section, not
buried as a footnote — the honest measurement of a known modeling simplification's cost is itself
a result worth reporting.

## Consequences

This creates a direct Phase 1 obligation: D-03's latent-trait response functions must make
ground-truth uplift computable per `(customer, action)` pair — which is exactly what makes the
propensity-delta approximation's error measurable at all in Phase 4. Without a simulator that can
answer "what would have happened under the untaken action," there would be nothing to measure the
approximation against, and the headline result this ADR promises would collapse into an unverifiable
claim.

The accepted cost is that the MVP's ranking policy runs on a known-biased estimator rather than a
statistically unbiased one; propensity-delta uplift estimation is a documented simplification with
well-understood failure modes (it can misattribute baseline heterogeneity as treatment effect). This
project treats that simplification as measured technical debt — logged with its removal trigger per
QUALITY_BAR.md §4 — rather than a silent assumption, and uplift learners remain the explicit
post-MVP stretch (T-/X-learner in v2).

## Alternatives Considered

- **Option B — T-/X-learners in MVP** was rejected for the MVP timeline: more statistically correct,
  but the added data requirements and calibration delicacy would slow the initial pipeline loop
  before there is a working end-to-end system to validate the estimator against.
