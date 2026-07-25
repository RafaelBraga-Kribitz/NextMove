# Phase 1: Reproducible World - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-25
**Phase:** 1-Reproducible World
**Areas discussed:** Simulator world shape, OD-7 + ADR ratification, Toolchain on Windows,
Simulated clock & action injection, Feature materialization, Quarantine ergonomics,
Config & profile layout

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Simulator world shape | Flavor, scale, and response functions of the generated world | ✓ |
| OD-7 + ADR ratification | The one deliberately-open decision, plus how OD-1..10 get ratified | ✓ |
| Toolchain on Windows | make vs just, dependency manager, CI shape | ✓ |

**User's choice:** All three.
**Notes:** Three gray areas were offered; the user selected every one. Four further areas were
added later in the session (see below) after the user chose "Explore more gray areas".

---

## Simulator world shape

### Q1 — World flavor

| Option | Description | Selected |
|--------|-------------|----------|
| Fashion world, UC1-native (Recommended) | Mid-market fashion retailer with real winter seasonality; UC1/UC2 occur literally | |
| Generic multi-category | Several verticals, milder seasonality; UC1 becomes hypothetical | |
| Fashion core + one contrast category | Fashion-led plus a low-seasonality category so effects show by contrast | ✓ |

**User's choice:** Fashion core + one contrast category.
**Notes:** Chose against the recommendation. The contrast category costs a little simulator surface
but gives segmentation something real to separate on — a stronger position than the recommended
option, since MCDA-selected segmentation is a Phase 4 differentiator that needs visible structure.

### Q2 — Scale

| Option | Description | Selected |
|--------|-------------|----------|
| ~50k customers / 18 months (Recommended) | Two winter peaks; MDE-reachable for segment-level 3WD; demo profile ~2k for CI | ✓ |
| ~10k customers / 12 months | Fast but thin — 3WD would sit in Delay for lack of power; one peak only | |
| ~200k customers / 24 months | Closest to the anchor paper's scale but blows the five-minute reviewer budget | |

**User's choice:** ~50k customers / 18 months.
**Notes:** The binding constraint was Phase 3 statistical power versus the published
"under 5 minutes" reviewer claim.

### Q3 — Action-response functions

| Option | Description | Selected |
|--------|-------------|----------|
| Latent traits × action → uplift (Recommended) | Documented function of traits + context; ground-truth uplift computable | |
| Fixed per-segment lift tables | Simpler but coarse, and hands the clusterer its own answer key | |
| Latent traits + explicit reward-hacking loophole | As recommended, plus a deliberately exploitable loophole | ✓ |

**User's choice:** Latent traits + explicit reward-hacking loophole.
**Notes:** Chose the more ambitious option. Claude flagged the timing nuance and the user did not
object: the loophole is a *simulator* property and therefore buildable now, but the probe that
exploits it needs the contextual bandit, which is v2. Phase 3 can demonstrate it earlier with a
naive profit-maximizing policy. QUALITY_BAR §"Failure analysis" mandates the probe, so building the
failure mode in from the start makes it genuine rather than staged.

### Q4 — Micro-conversion (PCR) depth

| Option | Description | Selected |
|--------|-------------|----------|
| Emit events, derive weights later (Recommended) | Phase 1 emits at derivable fidelity; derivation is Phase 4 | ✓ |
| Emit events and derive weights in Phase 1 | Earlier novel result, but modeling work inside a data phase | |
| Emit events only, weights stay configured | Simplest; forfeits a named research differentiator | |

**User's choice:** Emit events, derive weights later.
**Notes:** Preserves RESEARCH_SYNTHESIS gap #3 (data-driven micro-conversion weights) without
pulling modeling work into the foundation phase.

---

## OD-7 + ADR ratification

### Q1 — OD-7: artifact versioning

| Option | Description | Selected |
|--------|-------------|----------|
| DVC + MLflow (Recommended) | Reviewer-recognizable; DVC for data/artifacts, MLflow for runs/models | ✓ |
| Content-hashed store + MLflow | Lighter, fits DATA-04's hashing, but reads as "rolled my own" | |
| MLflow artifacts only | One tool, but weak data versioning undercuts the reproducibility claim | |

**User's choice:** DVC + MLflow.
**Notes:** Closes the `[Open: OD-7]` marker inside locked decision AD-18 — the only genuinely
undecided item the locked ADR deliberately left open. Deciding factor was reviewer recognizability
for a portfolio artifact rather than technical elegance.

### Q2 — How to ratify OD-1..OD-10

| Option | Description | Selected |
|--------|-------------|----------|
| Batch-ratify as recommended (Recommended) | Write all ten affirming recommendations; real content, no re-litigation | |
| Review each individually before writing | Walk all ten one at a time before any ADR is written | ✓ |
| Ratify only the live ones now | OD-7, OD-4, OD-10 now; defer the rest | |

**User's choice:** Review each individually before writing.
**Notes:** Rather than run ten interrogation rounds, Claude performed the per-OD review itself and
presented the analysis — which seven are already substantively encoded in the locked ADR set
(OD-1→AD-14, OD-2→AD-11+TD-03/04, OD-3→AD-12, OD-5→AD-09/15, OD-6→AD-08, OD-8→AD-10, OD-10→AD-06)
and which are genuinely live (OD-4, OD-9; OD-7 already closed above). The user then chose which to
reopen. This honored "review each individually" while keeping the session proportionate.

### Q3 — Which need live discussion

| Option | Description | Selected |
|--------|-------------|----------|
| OD-9 — tiered autonomy | Least-encoded of the ten; shapes Phase 3 gateway behavior | ✓ |
| OD-4 — public dataset track | Credibility-vs-scope call affecting v2 and Phase 1's adapter seam | ✓ |
| The seven procedural ones | Reopen one or more despite the locked ADR encoding them | ✓ |
| None — ratify all as analyzed | Accept the analysis; ADRs still individually written | |

**User's choice:** OD-9, OD-4, and (initially) the seven procedural ones.
**Notes:** The third selection named no specific OD, so Claude followed up rather than guessing —
see Q6.

### Q4 — OD-9: tiered autonomy

| Option | Description | Selected |
|--------|-------------|----------|
| Three tiers as recommended (Recommended) | Tier 1 auto on Accept; Tier 2 sign-off; Tier 3 human-only (price/discount) | ✓ |
| Everything queued for approval | Safest, but turns "a system that learns" into "a system that files tickets" | |
| Two tiers only | Drops the sign-off tier; contradicts TD-12's promotion discipline | |

**User's choice:** Three tiers as recommended.
**Notes:** Tier membership lives in schema-validated YAML per ENG-03, so the autonomy boundary is
reviewable config rather than code.

### Q5 — OD-4: public-clickstream track

| Option | Description | Selected |
|--------|-------------|----------|
| Commit to B; Phase 1 stays schema-only (Recommended) | Ratify the split; Phase 1 obligation is only DATA-01's inward mapping | ✓ |
| Commit to B and pick the dataset now | Sanity-checks the schema against real shape; more upfront research | |
| Simulator-only (reject B) | Cleanest scope, weakest credibility per OPEN_DECISIONS' own analysis | |

**User's choice:** Commit to B; Phase 1 stays schema-only.
**Notes:** No dataset named. Locks the credibility story ("decisions in simulation, data
engineering on real shapes") without adding Phase 1 work.

### Q6 — Which procedural ODs to actually reopen

| Option | Description | Selected |
|--------|-------------|----------|
| None — ratify as analyzed | The seven stay procedural; each still gets a real ADR | ✓ |
| OD-6 — uplift approximation | Reopen propensity-delta vs T-/X-learners | |
| OD-8 — 3WD thresholds | Reopen static vs dynamic | |
| OD-10 — action space size | Reopen which archetypes make the cut | |

**User's choice:** None — ratify as analyzed.
**Notes:** Clarifying follow-up after Q3's unnamed selection. Confirms the seven were reviewed and
accepted, not skipped.

---

## Toolchain on Windows

### Q1 — Operational interface

| Option | Description | Selected |
|--------|-------------|----------|
| justfile + thin Makefile shim (Recommended) | `just` native on Windows; 3-line Makefile keeps `make reproduce` true | ✓ |
| Makefile only | Canonical but means Git Bash/WSL friction daily on Windows 11 | |
| justfile only, update the docs | Cleanest, but edits the published success metric | |

**User's choice:** justfile + thin Makefile shim.
**Notes:** Resolves the tension between the published claim ("`make reproduce`") and the
development platform (Windows 11) without weakening either.

### Q2 — Packaging

| Option | Description | Selected |
|--------|-------------|----------|
| uv, src-layout, Python 3.12 (Recommended) | Current standard, fast, first-class on Windows; lockfile backs the reproducibility claim | ✓ |
| poetry | Recognized but slower and being outpaced | |
| pip + pip-tools | Universally understood, multi-file friction, no gain over uv | |

**User's choice:** uv, src-layout, Python 3.12.
**Notes:** Python 3.12 chosen for mature wheels across XGBoost / LightGBM / SHAP / DuckDB.

### Q3 — CI shape

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub Actions, Linux only (Recommended) | lint → tests → mini E2E on demo profile → golden-file compare | ✓ |
| Linux + Windows matrix | Verifies the dev platform too; roughly doubles CI time | |
| Linux CI + pre-commit hooks | Adds local enforcement before CI | |

**User's choice:** GitHub Actions, Linux only.
**Notes:** The deliverable ships as a Linux container; the Windows dev experience is covered by
running the same `just` recipes locally.

### Q4 — Where the ten planning docs live

| Option | Description | Selected |
|--------|-------------|----------|
| Move to docs/ in Phase 1 (Recommended) | `git mv` during scaffolding, alongside the new `docs/adr/` | ✓ |
| Keep at root until Phase 5 | Defers churn but clutters root through the whole build | |
| Claude decides during planning | Let the planner pick the moment | |

**User's choice:** Move to docs/ in Phase 1.
**Notes:** Matches QUALITY_BAR §5's stated documentation standard. Git preserves history.

---

## Simulated clock & action injection

### Q1 — Clock model

| Option | Description | Selected |
|--------|-------------|----------|
| Daily tick + replayable action queue (Recommended) | Tick drains action queue, applies responses, then generates organic behavior | ✓ |
| Event-driven continuous clock | Finer grained, handles "wait 6h" naturally, harder to make deterministic | |
| Two-pass: organic then overlay | Simplest, but the overlay cannot change downstream behavior — breaks the closed loop | |

**User's choice:** Daily tick + replayable action queue.
**Notes:** The deciding criterion was "one code path, no Phase 3 rewrite": Phase 1 runs with an
empty queue, Phase 3's replay fills it, and the code is identical. The daily grain also matches the
batch/near-line cadence the MVP commits to, with real-time an explicit non-goal.

---

## Feature materialization

### Q1 — Materialization strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Daily grid + on-demand recompute path (Recommended) | Same transforms serve batch snapshots and arbitrary-`as_of_ts` computation | ✓ |
| Grid only (batch), API reads snapshots | Fastest, but mid-day decisions use stale features | |
| On-demand only | Always fresh, but expensive training assembly and weaker reproducibility | |

**User's choice:** Daily grid + on-demand recompute path.
**Notes:** Direct expression of OD-2's "one engine, two invocation modes". Also makes FEAT-02's
leakage tests straightforward — take any snapshot, assert nothing post-dates its `as_of_ts`.

### Q2 — Physical storage and what DVC tracks

| Option | Description | Selected |
|--------|-------------|----------|
| Parquet under DVC, DuckDB reads it (Recommended) | Immutable content-addressable files — what DVC is good at | ✓ |
| DuckDB file as store, DVC tracks the .duckdb | Simpler model, but versioning a mutable multi-GB blob | |
| DuckDB store + Parquet exports for DVC | Best querying, but two representations that can diverge | |

**User's choice:** Parquet under DVC, DuckDB reads it.
**Notes:** Keeps DATA-04's per-table content hashes meaningful, which a single mutable database
file would undermine.

---

## Quarantine ergonomics

### Q1 — Inspection surface and escalation

| Option | Description | Selected |
|--------|-------------|----------|
| Rejects table + threshold gate + report line (Recommended) | Queryable rejects; configurable reject-rate fails the run; one-line summary per run | ✓ |
| Rejects table only, never fails on rate | Inspectable, but 40% rejection could still "succeed" | |
| Fail on any rejection | Strict and defensible, brittle for the v2 public-dataset track | |

**User's choice:** Rejects table + threshold gate + report line.
**Notes:** Default threshold ~0.1%, in YAML per ENG-03. Deliberately not zero-tolerance because
D-13's v2 public-dataset track will meet real data containing malformed rows.

---

## Config & profile layout

### Q1 — Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Layered: base + profile overlay, one hash (Recommended) | Per-domain files; profiles override only diffs; hash over the resolved merge | ✓ |
| One flat config tree per profile | No merge semantics, but profiles drift as settings are added | |
| Per-package config files, no profiles | Clean ownership, but CLI-flag sprawl undercuts ENG-04's hashing | |

**User's choice:** Layered: base + profile overlay, one hash.
**Notes:** Profile drift was the named concern the layering avoids. Seeds are config values rather
than CLI flags specifically so determinism is auditable by a third party.

---

## Claude's Discretion

No area was delegated wholesale — the user made an explicit choice on every question, and departed
from the recommendation twice (world flavor, response functions), both times toward the more
substantive option.

Normal planner latitude remains on: module-internal structure, exact Pydantic model shapes, test
file organization, latent trait distributions and their parameterization (subject to SIM-03's
documentation requirement), and `just` recipe names beyond `reproduce`.

## Deferred Ideas

- Reward-hacking probe exploiting the D-04 loophole — v2, with the contextual bandit
- Empirical micro-conversion weight derivation — Phase 4, with the learned layer
- Public-clickstream dataset selection and adapter demo — v2 (OD-4 recommendation B)
- Dynamic 3WD thresholds — v2 stretch (OD-8 ships static)
- Uplift learners (T-/X-learner) — v2 (OD-6 ships the propensity-delta approximation)
- `.gitignore` for the Python project — still absent, belongs to Phase 1 scaffolding
