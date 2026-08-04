# ADR 008: Static 3WD Thresholds in MVP

## Status

Accepted — 2026-07-25 (ratifies OD-8). Derives from locked decision AD-10
(`docs/ARCHITECTURAL_DIRECTION.md` §"Evaluation & 3WD Experimentation Gateway").

This ratification follows a per-OD review confirming no substantive contradiction with the locked
decision set. AD-10 already commits the evaluation gateway to adjudicating experiments via
Accept/Reject/Delay with MDE, indifference margin, and max-delay escalation, without specifying
that these thresholds must be dynamic; this ADR closes the procedural gap by ratifying that they
start static. It is ratified as recommended, without re-litigation.

## Context

OD-8 asked whether the 3WD (three-way decision: Accept/Reject/Delay) gateway's statistical
thresholds — minimum detectable effect (MDE), indifference margin, maximum delay budget — should be
fixed constants in the MVP, or computed dynamically from traffic volume and seasonality from day
one. Static thresholds (a fixed MDE plus a roughly ±2%-class indifference margin) are corpus-
sanctioned and immediately shippable: they require no additional estimation machinery and their
behavior is fully predictable and auditable. Dynamic thresholds — adjusting MDE and margins based on
observed traffic and seasonal variance — are the more novel, research-flavored option, but they
multiply the tuning surface considerably: getting a dynamic threshold model wrong could make the
gateway either too trigger-happy (accepting noise as signal) or too conservative (delaying
everything indefinitely), and validating that the dynamic model itself behaves correctly is a
project in its own right.

## Decision

Adopt static thresholds for the MVP, with the threshold interface deliberately designed for
dynamism from the start — the schema and the evaluator's call signature accept a threshold source
that could later be a function of traffic and seasonality, even though the MVP always supplies a
fixed constant. Dynamic, traffic/seasonality-aware thresholds are explicitly named as the first
post-MVP experiment, because it is judged the highest-novelty, comparatively cheap win once the
static gateway is proven correct.

## Consequences

The MVP's 3WD gateway behavior is fully predictable and easy to audit: given a fixed MDE and
indifference margin, any reviewer can verify by hand whether a given experiment's observed effect
size should have produced Accept, Reject, or Delay. This predictability is valuable precisely
because the 3WD gateway is a gating mechanism for automation (per D-12's autonomy tiers) — an
unpredictable gate would undermine trust in every downstream automated action it approves.

The accepted cost is that static thresholds cannot adapt to genuinely low-traffic or highly seasonal
experiment windows within the MVP; an experiment run during a low-traffic period uses the same MDE
as one run at peak season, which may leave real effects undetected or force longer Delay periods
than a traffic-aware threshold would need. Because the interface is designed for dynamism up front,
adding traffic-aware thresholds later is an implementation change behind the existing interface, not
an interface redesign — this is what "designed for dynamism" concretely buys.

## Alternatives Considered

- **Dynamic thresholds from the start** was rejected for MVP: higher potential precision, but it
  multiplies the tuning and validation surface before the rest of the evaluation pipeline (the
  simulator, the response models, the policy ranking) is even proven correct — validating a dynamic
  threshold model on top of an unproven base system compounds risk rather than isolating it.
