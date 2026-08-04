# ADR 002: Hybrid Batch-and-On-Demand Decisioning

## Status

Accepted — 2026-07-25 (ratifies OD-2). Derives from locked decision AD-11
(`docs/ARCHITECTURAL_DIRECTION.md` §"Headless API & Demo Surface") and proposed decisions TD-03 /
TD-04 (`docs/TECHNICAL_DIRECTION.md`).

This ratification follows a per-OD review confirming no substantive contradiction with the locked
and proposed decision set. AD-11 and TD-03/TD-04 already encode option C as the invocation model;
this ADR closes the procedural gap. It is ratified as recommended, without re-litigation.

## Context

OD-2 asked where intelligence lives: does the system decide-on-request (compute per API call), or
decide-in-batch (materialize decisions nightly, serve reads)? The choice sets the API contract, the
latency budget, and the feedback cadence a reviewer or demo user experiences.

The pure-batch option (A) matches the offline-heavy consensus of the research corpus and the
marketing-cadence reality of the target buyer — a CRM daily export is genuinely how this kind of
decision gets consumed operationally. But pure batch makes an interactive demo feel static: a
reviewer clicking through UC1/UC2 in the dashboard would only ever see yesterday's materialized
grid, with no way to probe an arbitrary customer state. The pure-on-demand option (B) is
demo-friendly and simpler to reason about per request, but recomputing every feature and decision
from scratch on every call wastes the batch grid's determinism and reproducibility story.

AD-11 already commits to a REST decision API (`POST /decisions`) as the product boundary, and
TD-03 commits to "a batch DAG plus a thin synchronous read path where the API serves precomputed or
on-demand single decisions" with no streaming infrastructure. TD-04 adds that the decision engine
owns the `Decision` contract regardless of invocation path — no component reaches around another's
contract whether the call is batch-triggered or synchronous.

## Decision

Adopt option C: batch is the operational truth. The daily materialized grid (D-19's daily feature
snapshot per active customer) feeds the CRM-style export that is the product's real operating mode.
The same decision engine — the identical transform functions, the identical `Decision` contract
construction — is also invoked synchronously to serve a single customer's decision at an arbitrary
`as_of_ts`, powering both the interactive API path and the demo dashboard's live query. One engine,
two invocation modes; no second implementation to keep in sync.

## Consequences

This is the decision D-19's dual feature path implements concretely in Phase 1: a daily
materialized grid for batch and training, plus the same transform functions exposed for on-demand
computation at an arbitrary `as_of_ts`. The cost accepted is a small amount of duplication in
invocation plumbing — a batch trigger and a synchronous request handler both have to call into the
same core, which is marginally more code than either mode alone would require. In exchange, the
demo stays credible (a reviewer can query any customer state and see a live decision, not a frozen
snapshot) and the batch export remains the honest, reproducible operational surface. Because both
paths share the same transform functions, there is exactly one place where feature-computation bugs
can hide, not two.

## Alternatives Considered

- **Option A — pure batch** was rejected as the sole mode: it is operationally honest but makes
  the demo experience static, undermining the interactive walkthroughs UC1/UC2 depend on.
- **Option B — pure on-demand** was rejected as the sole mode: simpler per-request reasoning, but
  it discards the batch grid's reproducibility guarantees and recomputes constantly rather than
  ever materializing a stable, auditable daily snapshot.
