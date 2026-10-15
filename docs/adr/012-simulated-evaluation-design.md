# ADR 012: Simulated Evaluation Design (Experiment, Models, Replay, Published Profile)

## Status

Accepted — 2026-10-14. Elaborates ADR-004 (decisions evaluated in simulation only) and ADR-006
(propensity-delta uplift) into a concrete, testable evaluation protocol for the M-B to M-D
milestones of ADR-011.

## Context

Phase 1 simulated only organic history: the action queue is empty, so the event log contains
no decisions to learn from or to evaluate. The decision layer needs three things the world does
not provide by itself: training data in which actions vary, a way to score any policy's choice
against what the world would have done, and a temporal design that keeps evaluation honest.

Two further facts shaped the design. First, the simulator's documented response function
(`nextmove.simulator.response`) defines the purchase probability given a delivered action, and
`ground_truth_uplift` is defined on exactly that function, so it is the natural outcome model.
Second, the feature stage dominates runtime (about seven minutes for the 2,000-customer `demo`
profile on a laptop, and far longer for the 50,000-customer `default` profile), which bounds
which profile can carry published results.

## Decision

1. **Randomized A/B/n experiment as training data.** `nextmove.evaluate.experiment` assigns
   each eligible customer, every `experiment_every_days`, one action drawn uniformly from the
   candidates that survive the hard constraints. The log keeps only observable columns
   (features, action, purchase); ground truth never enters it.
2. **Outcome oracle.** `nextmove.evaluate.world.OutcomeOracle` evaluates one decision as one
   purchase response at the customer's next visit: `p(a) = clamp(base_conversion_probability x
   response_multiplier)`, with the simulator's own context (highest-affinity category, previous
   day's minimum category stock, seasonal multiplier, all-time contact counter). `none` and
   `wait` deliver nothing inside the decision window and evaluate to `p(none)`. The
   session/cart stages of the tick loop are not re-run in replay.
3. **Common random numbers.** Every policy sees the same uniform draw per (customer, day), so
   policy differences are not blurred by outcome noise, and "would have bought anyway" (draw
   below `p(none)`) is the same customer under every policy. This is what makes the
   wasted-discount measurement possible.
4. **Temporal windows.** Fractions of the horizon: `[warmup, 67%)` train,
   `[67%, 75%)` validation (Platt calibration, model-family selection), `[75%, 100%)` test.
   The test window carries both an out-of-time slice of the experiment (prediction metrics)
   and the policy replay (decision metrics). Business reference values (average order value,
   top-seller category) use only orders before the end of the training window.
5. **Response models conditioned on the action.** One model per family (logistic with action x
   feature interactions; LightGBM with the archetype as a categorical feature) predicts
   `P(purchase | context, action)`; uplift is the difference of two predictions (ADR-006).
   Each family is a customer-level bootstrap ensemble; the ensemble spread gives the decision
   engine its intervals and confidence.
6. **Published profile.** Published tables come from the seeded `demo` profile (2,000
   customers, full 548-day horizon), which `just reproduce` uses by default. The `default`
   profile remains the scale profile; `ci` and `tiny` run in CI.

## Consequences

Every policy, baseline or learned, is compared on identical customers, days and random draws,
with intervals from a customer-level bootstrap. Because the oracle is the simulator's own
response function, all decision results are statements about this simulated world only, and
every published number carries that caveat (ADR-004).

Replay is open-loop on browsing and inventory: replayed actions change contact history and
the fatigue counter, but not the features of later days or the stock level. This is a known
limitation, recorded in the failure analysis and in `DEBT.md` (DEBT-005).

Treating `wait` as no delivery means the simulator's `wait` multiplier is never exercised in
replay; the engine still considers `wait` on every decision (AC-1) and prices it like `none`.

## Alternatives Considered

- **Re-running the full tick loop per policy** (closed-loop replay) was rejected for this
  release: it multiplies runtime by the number of policies and couples evaluation to the
  simulator's internal state machine. It is the natural next step once runtime allows.
- **Learning from the historical campaign exposures** was rejected: their assignment depends on
  the campaign calendar, not on randomization, so response models trained on them would be
  confounded.
- **Publishing from the `default` profile** was rejected for laptop runtime; the `demo` profile
  keeps the full horizon and both seasonal peaks.
