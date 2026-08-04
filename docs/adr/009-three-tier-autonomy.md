# ADR 009: Three-Tier Autonomy Boundary

## Status

Accepted — 2026-07-25 (ratifies OD-9, per D-12). No single locked AD-* fully encodes this decision
at the tier-boundary level; it is grounded in AD-10 (the 3WD gateway that Tier 1 auto-application
depends on) and ENG-03 (schema-validated configuration as the mechanism for tier membership).

Like OD-4 and OD-7, OD-9 required a genuine choice at ratification time — the locked ADR set
establishes that an autonomy spectrum exists but does not fix its tier boundaries. This ADR records
that deliberation.

## Context

OD-9 asked what the system may change without human review, across a spectrum from "everything
auto-applies once the 3WD gateway accepts it" to "everything is queued for manual approval,
regardless of statistical confidence." The stakes are proportional to what is at risk in each
category of change: a ranking-weight nudge that turns out wrong costs little and is easily reversed;
a change to a discount ceiling that turns out wrong can directly cost real margin at scale, and
depending on how it is exposed, real customer trust.

Full auto-apply everywhere would maximize demonstrated automation but is reckless for
high-consequence changes — nothing in a 3WD Accept verdict certifies that an accepted variant is
safe to apply *without limit* to the category of change it touches, only that it is statistically
distinguishable from the baseline. Full manual queueing everywhere would be safe but would defeat
the product's core differentiator: a decision engine that cannot act without a human in the loop for
every micro-change is not meaningfully more autonomous than a recommendation-only tool.

## Decision

Adopt a tiered autonomy model with three tiers, defined concretely:

- **Tier 1 — auto-applies on a 3WD Accept verdict.** Covers content and ranking micro-changes:
  variant assignments and ranking-weight nudges. These are low-consequence, statistically-gated, and
  reversible, so a verified Accept is sufficient authorization to apply them automatically.
- **Tier 2 — requires human sign-off.** Covers policy and model promotions, and segment
  redefinitions. These change what the system does at a structural level and carry consequences
  beyond a single decision, so a human must review and approve even after a favorable 3WD verdict.
- **Tier 3 — human-only, never automatic.** Covers anything touching price or discount ceilings.
  Financial-boundary changes are excluded from automation entirely, regardless of statistical
  confidence — no 3WD verdict, however strong, authorizes the system to move a price or discount
  ceiling without a human decision.

Tier membership lives in schema-validated YAML per ENG-03 — specifically `config/autonomy.yaml`,
created in plan 01-03 — so the autonomy boundary is reviewable configuration, not code. A reviewer
(or an operator adjusting the boundary in production) can read exactly which change categories sit
in which tier without reading source code, and any change to the boundary is a config diff, not a
code change requiring a deploy.

## Consequences

This shapes Phase 3's 3WD gateway behavior directly: the gateway's Accept verdict is necessary but
not sufficient for automation — Tier 1 changes auto-apply on Accept, but Tier 2 and Tier 3 changes
still require the gateway's statistical signal *plus* a human step, meaning the gateway's output
feeds two different downstream paths depending on tier. It also shapes the override surface Phase 2
must build: because Tier 2 and Tier 3 changes require human sign-off, Phase 2's API and dashboard
need an explicit approve/override mechanism, not just a read-only decision feed.

Because tier membership is config rather than code, the file must contain the literal string
`Tier 3` and must reference `config/autonomy.yaml` — both are testable, auditable facts about how
this boundary is implemented, not just how it is described in prose.

## Alternatives Considered

- **Full auto-apply on any 3WD Accept** was rejected: a statistically significant effect size does
  not certify that a change is safe to apply without limit, especially for changes with direct
  financial consequence (price, discount ceilings).
- **Full manual queueing for every change** was rejected: it would defeat the product's autonomy
  differentiator by requiring human review even for the lowest-consequence, most reversible category
  of change (content and ranking micro-adjustments).
