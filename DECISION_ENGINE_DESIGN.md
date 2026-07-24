# DECISION_ENGINE_DESIGN.md

**The most important document.** Everything else exists to feed or evaluate this component.

---

## 1. The Decision Problem

The system does **not** answer *"Will this customer buy?"*
It answers *"What should the company do next — and is doing nothing the best option?"*

Formally, for customer *c* at time *t* with business state *B*:

```
a* = argmax over a ∈ A_eligible(c, t, B) of:
       E[uplift(a | c, t)] × margin(a, B) − cost(a) − risk_penalty(a, c)
subject to hard constraints C(c, t, B)
```

where `A` always includes `none` and `wait(Δt)`. `[Decision]` Restraint is a first-class action; a system that cannot recommend "do nothing" cannot be trusted with discounts.

Key properties:

- **Counterfactual, not observational:** the score is expected *incremental* value, not raw purchase probability. MVP approximates uplift via response models conditioned on action `[Assumption: simulator ground truth lets us quantify how wrong this approximation is]`; stretch replaces it with explicit uplift learners.
- **Constrained:** hard constraints remove actions before ranking; soft constraints penalize within ranking. The distinction is declarative config, never code.
- **Uncertain:** every score carries an interval; the decision confidence derives from model calibration + score gap to the runner-up.

---

## 2. Decision Inputs

### Customer context
- Identity & tenure; segment assignment (with cold-start flag)
- Behavior features: RFM, session dynamics (visits, depth, dwell), category affinity, cart state, abandonment history, micro-conversion aggregates
- History: past actions received, responses, overrides, fatigue counters
- Modeled: propensity per action, price sensitivity, churn/fatigue risk, LTV estimate

### Business context
- Inventory levels & scarcity flags per SKU/category
- Margin per product/bundle; incentive cost schedule
- Active campaigns & mandated promotions; brand-safety rules
- Seasonality calendar (e.g., pre-Christmas peak)

### Environmental context
- Time (hour/day/season), device/channel availability
- Optional exogenous signals (e.g., weather) — simulator-provided, adapter-shaped `[Decision: modeled as a generic `context_signal` event so real integrations slot in later]`

---

## 3. Decision Outputs

The typed `Decision` object — the product's public contract:

```yaml
decision_id: uuid
customer_id: c_10482
as_of: 2026-07-24T18:00:00Z
action:
  type: premium_bundle_email        # from the action catalog
  params: {bundle_id: b_88, send_delay_hours: 6, channel: email}
expected_outcome:
  metric: conversion_uplift
  estimate: 0.038
  interval: [0.011, 0.065]
  horizon_days: 7
confidence: 0.82                    # calibrated
reasoning: >
  High purchase intent without incentive (would-buy 0.64). Discount suppressed:
  inventory is low and this customer's modeled price sensitivity is low, so a
  discount would cost margin without adding conversions. For this segment,
  premium bundles have outperformed discounts in past experiments. Waiting 6
  hours matches this customer's historical engagement window.
reasoning_trace:
  candidates_considered: [discount_10, premium_bundle_email, recommend_topseller, wait_24h, none]
  filtered:
    - {action: discount_10, rule: inventory_scarcity_gate, detail: "stock < threshold for cart item"}
  scores: {...}
  runner_up: {action: wait_24h, score_gap: 0.021}
  model_attributions: [{feature: cart_active, weight: +0.31}, ...]
constraints_considered: [inventory_scarcity_gate, frequency_cap_email, discount_ceiling, campaign_calendar]
policy: {name: expected_value_v1, model_versions: {...}, config_hash: ...}
```

Contract rules: no field may be fabricated; if a value is unavailable, it is `null` with a reason; `reasoning` must be renderable to a marketing manager without edits.

---

## 4. Decision Pipeline

```
Observation ► Prediction ► Action generation ► Constraint filtering ► Ranking ► Explanation ► (Feedback)
```

1. **Observation:** assemble the point-in-time context (feature lookup + business state). Missing data is explicit, never imputed silently at this layer.
2. **Prediction:** score each (customer, action) pair with calibrated models; attach attributions.
3. **Action generation:** the `ActionProvider` registry expands the action catalog into concrete parameterized candidates (which bundle, which discount tier, which delay). Always appends `none` and `wait`.
4. **Constraint filtering:** hard rules eliminate candidates and record why. Conflicting constraints resolve by declared precedence (`compliance > inventory > campaign > preference`); unresolvable conflicts emit `action: none` + `needs_human_review`.
5. **Decision ranking:** the active `Policy` ranks survivors by expected constrained profit with uncertainty penalty; bandit policy (stretch) may explore *only within survivors*.
6. **Explanation:** compose reasoning from attributions (relevance-framed), fired constraints, and runner-up counterfactual.
7. **Feedback (closed loop):** outcomes, overrides, and experiment verdicts flow to the evaluation store; overrides are high-weight labeled events; scheduled jobs re-segment/retrain and route material policy changes through the 3WD gateway.

---

## 5. Design Rules Specific to This Engine

- **Rules bound learning, never the reverse.** No learned component may emit an action a rule has excluded (property-tested).
- **The engine is deterministic given (context, config, model versions, seed).** Exploration randomness is seeded and logged.
- **Every decision is replayable:** the trace + versions suffice to reproduce it byte-for-byte.
- **The utility function is config, not code:** margin weights, fatigue penalty, risk aversion live in reviewed YAML — changing business posture must not require a deploy.
- **Human-in-the-loop surfaces:** override endpoint; `needs_human_review` queue; 3WD Delay escalation after budget exhaustion.
- **Failure honesty:** low confidence ⇒ safe default + explicit statement; the engine must never present a guess as certainty (anti-pattern: fake precision).
