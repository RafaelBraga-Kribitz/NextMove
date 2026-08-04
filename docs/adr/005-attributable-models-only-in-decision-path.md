# ADR 005: Attributable Models Only in the Decision Path

## Status

Accepted — 2026-07-25 (ratifies OD-5). Derives from locked decisions AD-09
(`docs/ARCHITECTURAL_DIRECTION.md` §"Explanation Engine", "no LLM in the explanation path") and
AD-15 (§"Explanations use relevance framing, never surveillance framing").

This ratification follows a per-OD review confirming no substantive contradiction with the locked
decision set. AD-09 and AD-15 already commit the explanation engine to SHAP-based, deterministic,
faithful attributions; this ADR closes the procedural gap by ratifying the upstream model-admission
rule those explanations depend on. It is ratified as recommended, without re-litigation.

## Context

OD-5 asked whether a non-attributable model — one whose internal reasoning cannot be faithfully
decomposed into per-feature contributions — is ever admissible in the live decision path. This
question matters because it is a direct trade-off between raw predictive accuracy and the
product's core explainability promise: every `Decision` object this system emits must carry
manager-readable reasoning plus a structured trace, per AD-15. A model that cannot produce faithful
attributions cannot honestly populate that trace — at best it would require a separate surrogate
model trained to approximate the real model's behavior, and a surrogate's explanation is, by
construction, an explanation of a different model than the one that actually made the decision.

Two options existed: (A) a hard rule — the decision path requires attributions, full stop; (B)
allow a black-box model into the decision path if it wins by a large accuracy margin, using
surrogate explanations to paper over the gap. Option B chases marginal accuracy at the cost of the
product's core promise, and surrogate explanations carry a real unfaithfulness risk — a surrogate
that looks locally accurate can still diverge from the real model's actual decision boundary in
exactly the cases that matter most (edge cases, low-confidence predictions).

## Decision

Adopt option A, matching AD-14's classical-first ML ladder (TD-11): rule-based baseline first,
then gradient-boosted trees (XGBoost/LightGBM) with mandatory calibration and SHAP attributions as
the workhorse, with an optional shallow NN or two-tower model only for the comparison narrative.
Any model whose attributions cannot faithfully feed the explanation engine is inadmissible in the
decision path — full stop, no exceptions carved out for accuracy gains. Black-box challengers may
still be trained and evaluated, but strictly within the comparison study; they never touch a live
decision.

## Consequences

This decision inherits the source's own framing directly: if a black-box model is measurably more
accurate but excluded from the decision path on explainability grounds, the finding "we declined
X% accuracy for faithful explanations" is itself reported as a strong result, not an apology. That
framing only works if the comparison study actually runs the black-box challenger fairly — so
model selection criteria (per TD-13: decision value, then calibration, then explanation quality,
then raw prediction metrics, then training cost) explicitly rank explanation quality above raw
prediction metrics, making the trade-off structural rather than a one-off judgment call.

The cost accepted is a predictive ceiling: NextMove will never deploy the single most accurate
model available if that model is a black box, even when the accuracy gap is real and measurable.
This is a deliberate, disclosed constraint that matches the product's XAI mandate, not an oversight.

## Alternatives Considered

- **Option B — allow black-box with surrogate explanations if margin is large** was rejected: it
  introduces an unfaithfulness risk (the surrogate explains a different model than the one deciding)
  precisely in the low-confidence, edge-case decisions where faithful explanation matters most, and
  it erodes the product's differentiated promise of decision-grade, trustworthy explanations.
