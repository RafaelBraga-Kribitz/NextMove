# ADR 004: Synthetic Decisions, Public-Dataset Validation as a v2 Track

## Status

Accepted — 2026-07-25 (ratifies OD-4 as recommendation B, per D-13). No single locked AD-* fully
encodes this decision; it is grounded in DATA-01's inward-mapping adapter rule and TD-10's
simulator-primary-data honesty rules (`docs/TECHNICAL_DIRECTION.md`).

Unlike OD-1, 2, 3, 5, 6, 8, and 10, OD-4 required a genuine choice at ratification time — no locked
ADR had already committed to option B's specific split. This ADR records that deliberation.

## Context

OD-4 asked whether NextMove should be synthetic-only, or should add a public-dataset validation
track to prove the pipeline generalizes beyond the simulator's own assumptions. The stakes are
credibility: reviewers are right to discount purely synthetic results, because a simulator can be
tuned — consciously or not — to make its own generator's assumptions look validated. But public
clickstream datasets lack the one thing this project's core value proposition needs most:
counterfactuals. No public dataset records what would have happened to a customer under an action
that was not actually taken, and without counterfactuals there is no way to evaluate a decision
policy against ground-truth uplift.

Three options were on the table: (A) simulator only — cleanest scope, weakest credibility; (B)
simulator plus a public clickstream dataset run through ingestion, features, and segmentation to
prove pipeline generality, with decisions still evaluated only in simulation; (C) chase a real
partner dataset with genuine business context — appealing but not achievable on this project's
timeline as a solo effort.

## Decision

Adopt option B, per D-13. Decisions are evaluated in simulation only, and every decision-related
result is explicitly labeled "in simulation" wherever it appears — in reports, in the API response
metadata, in the dashboard. Data engineering (ingestion, feature computation, segmentation) is
additionally validated against a public e-commerce clickstream dataset to prove the pipeline
handles real-shaped, real-world data and not just the simulator's own tidy output.

The validation track itself is explicitly v2 scope. No dataset is named yet — selecting a concrete
public clickstream dataset and building its adapter is deferred, not because the idea is
speculative but because Phase 1's job is to build the seam the v2 track will plug into, not the v2
track itself.

## Consequences

Phase 1's only obligation under this ADR is what DATA-01 already requires regardless of this
decision: ingestion adapters map external event shapes inward to the canonical schema, and never
the reverse — the canonical schema never bends to accommodate a particular source's quirks. The
`IngestAdapter` registry shipping in plan 01-05 is the seam that keeps the future v2 track cheap:
because every adapter — whether it is the simulator's own event stream or a future public-dataset
adapter — must conform to the same registry interface and map into the same canonical schema, adding
the public-dataset adapter later requires zero changes to ingestion, feature computation, or
segmentation code. It is a new registry entry, not a new pipeline.

The accepted cost is that data-engineering results reported before v2 ships describe a synthetic
pipeline validated on its own synthetic input, with the "runs on real-shaped data too" claim
deferred rather than proven immediately. This is disclosed honestly rather than implied.

## Alternatives Considered

- **Option A — simulator only** was rejected: cleanest scope, but leaves the pipeline-generality
  claim entirely unproven, which a skeptical reviewer would flag immediately.
- **Option C — a real partner dataset** was rejected as unrealistic for this project's timeline and
  solo-operator constraints; sourcing and clearing a real business dataset with genuine
  counterfactual value is a multi-month undertaking on its own.
