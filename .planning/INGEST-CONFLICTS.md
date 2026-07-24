## Conflict Detection Report

Mode: new · Docs synthesized: 10 (2 ADR, 2 SPEC, 1 PRD, 5 DOC)
Precedence applied: ADR > SPEC > PRD > DOC · No per-doc precedence overrides present
Locked ADRs: 1 (`ARCHITECTURAL_DIRECTION.md`)

### BLOCKERS (0)

None.

Checks that ran and passed:
  - LOCKED-vs-LOCKED ADR contradiction: not applicable — only one ADR is locked (`ARCHITECTURAL_DIRECTION.md`). `TECHNICAL_DIRECTION.md` is classified `locked: false` (no document-level Accepted status).
  - Merge-mode locked-CONTEXT.md contradiction: not applicable — MODE is `new`, no pre-existing `.planning/` context.
  - UNKNOWN / low-confidence classification: none — all 10 classifications are `high` confidence with `manifest_override: true`.
  - Cross-ref cycle detection: no cycles found (see INFO below).

### WARNINGS (1 — resolved by user 2026-07-24, see RESOLUTION below)

[WARNING] Competing acceptance variants for REQ-timing-channel
  Found: PRODUCT_CHARTER.md §5 lists "Timing/channel as decision dimensions (beyond act/don't-act)" as stretch goal #2 — i.e. out of MVP; corroborated by ARCHITECTURAL_DIRECTION.md §4 (locked ADR), which lists "timing/channel decision dimensions" under Optional Capabilities ("useful but not required")
  Found: PRODUCT_CHARTER.md §4 UC1 — a *primary* MVP use case — specifies output "action: premium_bundle_email, timing: +6h"; DECISION_ENGINE_DESIGN.md §3 (SPEC) bakes timing and channel into the Decision public contract as action.params {bundle_id, send_delay_hours: 6, channel: email}; OPEN_DECISIONS.md OD-10 fixes MVP action archetypes including "email-now" and "email-delayed"; PROJECT_IDENTITY.md states the core pitch as "which intervention, for whom, when, through which channel"
  Impact: Synthesis cannot pick without losing intent. Precedence does not resolve this: the locked ADR defers timing/channel while the same PRD's flagship MVP scenario and the SPEC's public Decision contract require them. A plausible reconciliation exists (timing/channel are fixed action-archetype parameters in MVP but are not *optimized* decision dimensions until stretch) but that reading is inference, not stated in any source. Routing MVP work on either reading silently changes the size of the action space, the ranking surface, and the Decision contract.
  → Choose one variant, or split into two requirements (e.g. "timing/channel as fixed archetype parameters — MVP" vs "timing/channel as optimized decision dimensions — stretch") before routing. Both variants are preserved verbatim in .planning/intel/requirements.md as REQ-timing-channel-v1 and REQ-timing-channel-v2.

  RESOLUTION (user, 2026-07-24): SPLIT — the suggested reconciliation was adopted.
    Timing and channel are FIXED PARAMETERS of the ~8 MVP action archetypes (OD-10: email-now,
    email-delayed) and are carried in the Decision contract per DECISION_ENGINE_DESIGN.md §3, so
    UC1 renders "timing: +6h" from the selected archetype. They do NOT become optimized decision
    dimensions — the policy ranks over archetypes and does not search a delay/channel grid — until
    the stretch phase. This satisfies PRODUCT_CHARTER.md UC1 and the SPEC Decision contract without
    contradicting ARCHITECTURAL_DIRECTION.md §4 (locked ADR), which defers timing/channel
    *decision dimensions* to Optional Capabilities. The operative distinction is
    present-as-parameter (MVP) vs. optimized-as-dimension (stretch).
    REQ-timing-channel-v1/-v2 in .planning/intel/requirements.md are superseded by
    REQ-timing-channel-mvp and REQ-timing-channel-optimized.
    Gate status: WARNING cleared; safe to route.

### INFO (8)

[INFO] Cycle detection clean — both previously reported cycles are broken
  Note: Re-ran three-color DFS over the cross_refs graph (10 nodes, 5 external dangling refs excluded). Result: zero cycles, max traversal depth 3 (cap 50). The two cycles reported in the prior run — OPEN_DECISIONS → ARCHITECTURAL_DIRECTION → QUALITY_BAR → OPEN_DECISIONS, and OPEN_DECISIONS → RESEARCH_SYNTHESIS → QUALITY_BAR → OPEN_DECISIONS — are both broken. Verified directly against QUALITY_BAR.md: its re-classified cross_refs are [DEBT.md, README.md, docs/adr/NNN-*.md, EXPERIMENTS.md, SIMULATOR_ASSUMPTIONS.md, DECISION_ENGINE_DESIGN] and the source text no longer references OPEN_DECISIONS. All 10 docs synthesized; none excluded.

[INFO] Auto-resolved: locked ADR > PRD on minimum clustering candidates
  Note: PRODUCT_CHARTER.md §5 MVP item 4 requires ">= 2 clustering candidates evaluated by an MCDA wrapper"; ARCHITECTURAL_DIRECTION.md §2.3 (locked ADR) requires a "candidate algorithm registry (K-means, GMM, BIRCH at minimum)" — i.e. >= 3. LOCKED ADR wins per precedence; synthesized intel carries the ADR's >= 3 named algorithms, with the PRD's >= 2 retained as the weaker floor in REQ-mvp-segmentation.

[INFO] Auto-resolved: ADR > DOC on API invocation mode
  Note: RESEARCH_SYNTHESIS.md §1 principle 5 asserts "the online API reads precomputed decisions/features" (read-cache only); TECHNICAL_DIRECTION.md §1 (ADR) specifies "a thin synchronous read path (API serves precomputed **or on-demand** single decisions)", and QUALITY_BAR.md AC-1 (SPEC) requires POST /v1/decisions to return a schema-valid Decision "for any valid context", which implies on-demand computation. ADR and SPEC both outrank DOC — the hybrid batch + on-demand model wins. This matches OPEN_DECISIONS.md OD-2 recommendation C ("one engine, two invocation modes"), though OD-2 remains formally unratified.

[INFO] Auto-resolved: SPEC > PRD on the beat-the-baseline acceptance criterion
  Note: PRODUCT_CHARTER.md O2 states as a measurable objective that "the decision policy achieves higher cumulative constrained profit than (a) always discount, (b) always recommend top-seller, and (c) do nothing baselines". QUALITY_BAR.md AC-6 (SPEC) explicitly permits the honest negative: "GBM models beat the rule baseline on decision-level replay profit with reported confidence intervals — or the report explicitly states they don't and the baseline ships", and AC-10 requires only that the comparison report be produced. SPEC outranks PRD — the honest-negative escape hatch stands, so "ML policy wins" is not a gating requirement for done-ness.

[INFO] Auto-resolved: locked ADR > SPEC on the segmentation viability constraint list
  Note: ARCHITECTURAL_DIRECTION.md §2.3 (locked ADR) mandates MCDA selection under four configured constraints — min size, max clusters, activity diversity, compute cost. QUALITY_BAR.md AC-7 (SPEC), which is the testable gate, names only "(min size, max clusters)". PRODUCT_CHARTER.md O3 names three (minimum size, maximum segment count, activity diversity). LOCKED ADR wins — the viability gate should cover all four criteria. AC-7 as written under-tests the locked requirement; flagged so the roadmapper widens the gate rather than narrowing the requirement.

[INFO] OD-7 (artifact versioning) is left explicitly open inside the locked ADR
  Note: ARCHITECTURAL_DIRECTION.md §8 specifies data/artifact versioning as "DVC or content-hashed artifact store [Open: OD-7]" — the locked ADR deliberately asserts no choice. OPEN_DECISIONS.md OD-7 recommends DVC for data/artifacts plus MLflow for runs/models, but that is a DOC-tier recommendation, not a ratified decision. Recorded as ADR-AD-18 in decisions.md with the deferral preserved; synthesis did not promote the DVC recommendation to a decision.

[INFO] OD-1..OD-10 remain formally unratified while two ADRs already encode some of them
  Note: OPEN_DECISIONS.md states its ten decisions "must be ratified (as ADRs) before /gsd:plan-phase" and instructs ratification as ADR-001..ADR-010. No docs/adr/NNN-*.md files exist in the ingest set. Meanwhile TECHNICAL_DIRECTION.md §1 and §2 already cite "[Decision — justified in OPEN_DECISIONS OD-1]" (modular monolith) and "[Decision — OD-4]" (simulator-primary data) as settled, and ARCHITECTURAL_DIRECTION.md (locked) encodes positions consistent with OD-2, OD-3, OD-5, OD-6, OD-8 and OD-10. No contradiction was found between any OD recommendation and the ADR content — the gap is procedural (unratified), not substantive. Ratification is a roadmapper input, not a synthesis blocker.

[INFO] Cross-refs pointing outside the ingest set
  Note: Five referenced documents are not present in the classification set and were excluded from cycle detection as dangling: DEBT.md, EXPERIMENTS.md, README.md, SIMULATOR_ASSUMPTIONS.md, and docs/adr/NNN-*.md (all referenced by QUALITY_BAR.md; SIMULATOR_ASSUMPTIONS.md also referenced by TECHNICAL_DIRECTION.md). These are named as required deliverables by QUALITY_BAR.md §5 and by TECHNICAL_DIRECTION.md §2 honesty rule (1), so they are expected future artifacts rather than missing inputs.
