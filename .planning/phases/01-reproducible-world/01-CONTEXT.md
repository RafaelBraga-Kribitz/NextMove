# Phase 1: Reproducible World - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

A clean clone produces a complete, queryable, deterministic simulated e-commerce history — the data
foundation every later claim rests on — with the module boundaries, config discipline, and ratified
decisions that keep it honest.

**In scope (16 requirements):** SIM-01..04, DATA-01..04, FEAT-01..02, ENG-01, ENG-03, ENG-04,
ENG-08, ENG-09, DOC-01.

**Not in scope:** no decision engine, no models, no API, no segmentation. Phase 1 produces organic
history and the seams later phases plug into — nothing that consumes them.

</domain>

<decisions>
## Implementation Decisions

### Simulator world shape

- **D-01:** The world is a **fashion-core retailer plus one low-seasonality contrast category**
  (basics/home). Fashion carries the winter peak that makes UC1 literal; the contrast category
  exists so segmentation and seasonality effects are visible *by contrast* rather than asserted.
  Category structure is config-driven, never hardcoded.
- **D-02:** Default scale is **~50k customers over 18 months** — two winter peaks, so seasonality
  and longitudinal fatigue are learnable, and enough population for Phase 3's 3WD experiments to
  reach MDE on segment-level effects. A **`demo` profile (~2k customers)** exists for CI's miniature
  end-to-end run. Both are config profiles, not code paths.
- **D-03:** Action-response functions are **latent-trait driven**: each customer carries latent
  price sensitivity, loyalty, fatigue and category affinity, and an action's effect is a documented
  function of those traits plus context (inventory, season). Ground-truth uplift is therefore
  computable per `(customer, action)` pair — which is what lets Phase 4 measure how wrong the
  propensity-as-uplift approximation (OD-6) actually is, a result the charter wants as a headline.
- **D-04:** The simulator deliberately includes an **exploitable reward-hacking loophole** (e.g. a
  fatigue penalty that can be disabled in config) so QUALITY_BAR's mandated reward-hacking probe has
  something real to catch. **The loophole is Phase 1 scope; the probe that exploits it arrives with
  the contextual bandit in v2.** Phase 3's evaluation harness can already demonstrate it with a
  naive profit-maximizing policy.
- **D-05:** UC1 and UC2 scenarios must **genuinely occur** in the generated population — a
  winter-jacket cart abandoner with low stock and low price sensitivity pre-Christmas; a recently
  purchased, satisfied, high-fatigue customer. These are acceptance targets for the simulator, not
  hand-built fixtures.

### Micro-conversion (PCR) events

- **D-06:** Phase 1 **emits** scroll / filter / dwell-class micro-events at enough fidelity that
  weights can later be derived empirically as `P(micro-action → macro-conversion)`. **The derivation
  itself is Phase 4 work**, alongside the learned layer. Phase 1 must not ship guessed weights as if
  they were derived.

### Simulated clock and action injection

- **D-07:** The world advances in **daily ticks**. Each tick (1) reads a queue of scheduled action
  deliveries, (2) applies their response functions, then (3) generates that day's organic behavior.
  Phase 1 runs with an **empty queue** — pure organic history — while Phase 3's replay fills it from
  policy decisions. **One code path, no Phase 3 rewrite.** The daily grain matches the batch /
  near-line cadence the MVP commits to (real-time is an explicit non-goal).
- **D-08:** Because actions are applied *before* the same tick's organic generation, a delivered
  action can change downstream organic behavior — which is what makes the closed loop and the
  longitudinal fatigue story honest.

### Ratified open decisions (DOC-01)

- **D-09:** **OD-7 is ratified: DVC for data/artifacts + MLflow for runs/models.** This closes the
  `[Open: OD-7]` marker inside locked decision AD-18. Deciding factor is reviewer recognizability —
  a hiring manager knows DVC on sight, whereas a custom hash-store needs explaining. Accepted cost:
  some workflow friction and a second tool to install.
- **D-10:** **All ten ODs get individually-written ADRs** (`docs/adr/001-*.md` … `010-*.md`) with
  genuine Context / Decision / Consequences text — not batch rubber-stamping.
- **D-11:** Seven of them (**OD-1, 2, 3, 5, 6, 8, 10**) are ratified **as recommended, without
  re-litigation** — each is already substantively encoded in the locked ADR set (AD-14, AD-11+TD-03/04,
  AD-12, AD-09/15, AD-08, AD-10, AD-06 respectively). The gap was procedural, and this was confirmed
  after a per-OD review rather than assumed.
- **D-12:** **OD-9 is ratified as three-tier autonomy.** Tier 1 auto-applies on a 3WD Accept verdict:
  content and ranking micro-changes (variant assignments, ranking-weight nudges). Tier 2 requires
  human sign-off: policy and model promotions, segment redefinitions. Tier 3 is human-only and never
  automatic: anything touching price or discount ceilings. **Tier membership lives in
  schema-validated YAML** (ENG-03), so the autonomy boundary is reviewable config, not code. This
  shapes Phase 3's gateway behavior and the override surface Phase 2 builds.
- **D-13:** **OD-4 is ratified as recommendation B** — decisions evaluated in simulation (always
  labeled "in simulation"), data engineering additionally validated against a public e-commerce
  clickstream dataset. **That validation track is v2.** Phase 1's only obligation is what DATA-01
  already requires: adapters map external shapes *inward* to the canonical schema, never the reverse.
  No dataset is named yet.

### Toolchain

- **D-14:** **`just` is the real operational interface**, with a thin 3-line `Makefile` forwarding
  `make reproduce` → `just reproduce`. Rationale: `just` works natively in PowerShell on the
  development machine (Windows 11), while the shim keeps the published success metric —
  "`make reproduce` from a clean clone" — literally true for Linux/macOS reviewers.
- **D-15:** **`uv`** for environment, lockfile and installs. **`src/` layout** (`src/nextmove/` with
  the ten packages beneath it). **Python 3.12** — mature wheels for XGBoost / LightGBM / SHAP /
  DuckDB across platforms. The lockfile is what makes "a clean clone reproduces" credible.
- **D-16:** **CI is GitHub Actions, Linux-only** (`ubuntu-latest`): lint (ruff + the import-linter
  contract) → tests → miniature end-to-end on the `demo` profile → golden-file comparison. The
  deliverable ships as a Linux container; the Windows dev experience is covered by running the same
  `just` recipes locally. No Windows matrix leg.
- **D-17:** The ten root planning documents **move to `docs/` during Phase 1** scaffolding, via
  `git mv` (history preserved), alongside the new `docs/adr/` directory that DOC-01 creates. This
  matches QUALITY_BAR §5's stated documentation standard and keeps the repo root for
  README / pyproject / justfile.

### Storage and features

- **D-18:** **Canonical event and feature tables are Parquet files tracked by DVC; DuckDB queries
  them directly** (native Parquet reader) and is also the transform engine. Rationale: DVC versions
  immutable, content-addressable files — which is what it is actually good at — rather than a
  mutable multi-GB `.duckdb` blob, and it keeps DATA-04's per-table content hashes meaningful.
- **D-19:** Features are materialized on a **daily grid** (one snapshot per active customer) for
  batch and training, **and the same transform functions are exposed for on-demand computation at an
  arbitrary `as_of_ts`**. One definition, two call sites — the direct expression of OD-2's "one
  engine, two invocation modes". The grid also makes FEAT-02's leakage tests straightforward: take
  any snapshot, assert nothing in it post-dates its `as_of_ts`.

### Data quality and quarantine

- **D-20:** Contract violations land in a **queryable rejects table** carrying the offending row,
  the reason, the contract version, and the pipeline stage.
- **D-21:** A **configurable reject-rate threshold** (default low, ~0.1%) **fails the run when
  exceeded**, so slow silent degradation cannot hide behind a "successful" run computed on partial
  data. The threshold is YAML per ENG-03. This is deliberately not zero-tolerance — the v2
  public-dataset track (D-13) will meet real-world data that reliably contains malformed rows.
- **D-22:** Every pipeline run prints a **one-line data-quality summary** (rows in, rows
  quarantined, reject rate, gates passed).

### Configuration

- **D-23:** Config is **layered: per-domain base files + thin profile overlays**.
  `config/` holds `simulator.yaml`, `features.yaml`, `constraints.yaml`, `actions.yaml`,
  `mcda.yaml`, `experiments.yaml`, `autonomy.yaml` (the last carrying D-12's tiers). Profiles
  (`default` / `demo` / `ci`) override **only what differs**, so the 2k-customer CI profile is a
  few-line diff rather than a duplicated tree.
- **D-24:** **Pydantic validates the merged result**, and the **config hash is taken over the
  resolved merge** — so a run's hash captures exactly what it ran with, satisfying ENG-04.
- **D-25:** **Seeds are config values, not CLI flags** — they must be part of the hashed, versioned
  surface for determinism to be auditable.

### Claude's Discretion

No area was delegated wholesale. Within the decisions above, the planner retains normal latitude on:
module-internal structure, exact Pydantic model shapes, test file organization, the specific latent
trait distributions and their parameterization (so long as every one is documented per SIM-03), and
the concrete `just` recipe names beyond `reproduce`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

Note: per D-17 these files move to `docs/` during this phase. Paths below are current (repo root)
as of context gathering; after the scaffolding move they become `docs/<NAME>.md`.

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 1: Reproducible World" — goal, the 16 mapped requirements, and the
  five success criteria this phase is judged against
- `.planning/REQUIREMENTS.md` — full text and acceptance criteria for SIM-01..04, DATA-01..04,
  FEAT-01..02, ENG-01/03/04/08/09, DOC-01
- `.planning/PROJECT.md` — core value, the eleven constraints, and the full Key Decisions table
  (18 locked AD-*, 18 proposed TD-*)

### Locked architecture (cannot be overridden without a superseding ADR)
- `ARCHITECTURAL_DIRECTION.md` §2.1 — event ingestion: Pydantic + DuckDB; SQLite and Kafka rejected
- `ARCHITECTURAL_DIRECTION.md` §2.2 — feature layer: versioned SQL + Python transforms, definitions
  in config, keyed `(customer_id, as_of_ts)`; Feast rejected for MVP but the interface must not
  preclude it
- `ARCHITECTURAL_DIRECTION.md` §2.11 — the simulator as a cross-cutting component and why it exists
- `ARCHITECTURAL_DIRECTION.md` §5 — the ten package boundaries and the eight plugin registries
- `ARCHITECTURAL_DIRECTION.md` §8 — MLOps expectations; note this is where `[Open: OD-7]` sits,
  now closed by D-09

### Technical direction
- `TECHNICAL_DIRECTION.md` §2 — data philosophy: contracts first, canonical event schema,
  lineage, quality checks as gates, point-in-time correctness, and the **four simulator honesty
  rules** (assumptions documented; response functions never importable by models; results labeled
  "in simulation"; public-dataset adapter demo)
- `TECHNICAL_DIRECTION.md` §5 — configuration philosophy: behavior changes are config changes;
  hardcoded business logic is a rejected change

### Quality gates this phase must satisfy
- `QUALITY_BAR.md` §1 — AC-11 (`make reproduce` reproduces published tables), AC-12 (coverage:
  `rules/`, `decisions/`, `evaluate/` ≥ 85%; overall ≥ 75%)
- `QUALITY_BAR.md` §3 — the ten prohibited anti-patterns; #7 (leakage-tolerant evaluation) and
  #8 (architecture astronautics) bind this phase most directly
- `QUALITY_BAR.md` §4 — technical debt policy; unacceptable shortcuts include unseeded randomness
  and simulator assumptions leaking into models
- `QUALITY_BAR.md` §5 — documentation standards; the source of D-17's `docs/` move and of the
  `SIMULATOR_ASSUMPTIONS.md` / `DEBT.md` / `EXPERIMENTS.md` obligations

### Decisions being ratified in this phase (DOC-01)
- `OPEN_DECISIONS.md` — OD-1..OD-10 with trade-offs and recommendations; **OD-7** (§Technical
  Trade-offs) is the genuinely open one closed by D-09, **OD-9** by D-12, **OD-4** by D-13
- `.planning/intel/decisions.md` — all 36 synthesized decisions (18 locked AD-*, 18 proposed
  TD-01..18) in one place, with provenance
- `.planning/INGEST-CONFLICTS.md` — the ingest conflict report; records the resolved
  `REQ-timing-channel` split and the note that AC-7 under-tests the locked ADR's four-criteria
  viability gate

### Contract targets (Phase 1 does not build these, but must not foreclose them)
- `DECISION_ENGINE_DESIGN.md` §2 — the decision inputs Phase 2 will demand of the feature layer
- `DECISION_ENGINE_DESIGN.md` §3 — the typed `Decision` contract, including
  `action.params.send_delay_hours` / `channel` per the resolved timing/channel split
- `PRODUCT_CHARTER.md` §4 — UC1 and UC2, which D-05 makes acceptance targets for the simulator

</canonical_refs>

<code_context>
## Existing Code Insights

**Greenfield — no source code exists.** This phase creates the repository from zero, so there are no
reusable assets or established patterns to inherit. The constraints below function as the
equivalent: they are pre-committed structure the phase must realize rather than discover.

### Structure to establish
- Ten packages under `src/nextmove/`: `simulator / ingest / features / segmentation / models /
  rules / decisions / policies / explain / evaluate / api` (ENG-01). Phase 1 populates
  `simulator`, `ingest`, `features`; the rest are created as boundaries with their public
  interfaces stubbed so import-linter has something real to enforce.
- Storage sits behind a **thin repository layer** (ENG-01) — no package reaches into Parquet or
  DuckDB directly.

### Enforcement to establish
- **import-linter contract failing CI** (SIM-02): no module under `models/`, `decisions/`,
  `policies/`, `features/` may import `simulator`. This is the single most load-bearing test in the
  phase — if simulator internals reach the models, every downstream result is fake.
- Leakage tests in the suite (FEAT-02), enabled by D-19's daily grid.
- Golden-file tests for byte-identical reruns (ENG-04), enabled by D-24/D-25's hashed resolved
  config and in-config seeds.

### Integration points this phase must leave open
- The **action queue** the daily tick drains (D-07) — Phase 3's replay is its first real producer.
- The **on-demand feature path** (D-19) — Phase 2's `POST /v1/decisions` is its first caller.
- The **`IngestAdapter` registry** — the v2 public-clickstream track (D-13) is its first non-simulator
  implementation.

</code_context>

<specifics>
## Specific Ideas

- **"One code path, no Phase 3 rewrite"** was the deciding criterion for the clock design (D-07):
  the empty-queue Phase 1 run and the policy-driven Phase 3 replay must be the same code, differing
  only in queue contents.
- **Reviewer recognizability** was the explicit deciding factor for OD-7 (D-09) over technical
  elegance — a portfolio artifact is judged partly on what a reviewer recognizes at a glance.
- The reward-hacking loophole (D-04) is wanted **from the start**, not retrofitted — the user chose
  the option that builds the failure mode in early so the later probe is genuine rather than staged.
- The CI profile should be a **few-line overlay** (D-23), explicitly not a duplicated config tree —
  profile drift was the named concern.
- Determinism should be **auditable, not just claimed**: seeds in hashed config rather than CLI
  flags (D-25) is what makes the claim checkable by a third party.

</specifics>

<deferred>
## Deferred Ideas

- **Reward-hacking probe** that actually exploits the D-04 loophole — arrives with the contextual
  bandit in **v2**. (The loophole itself is Phase 1 scope.)
- **Empirical micro-conversion weight derivation** — **Phase 4**, with the learned layer, since it
  wants calibrated macro-conversion data Phase 4 produces.
- **Public-clickstream dataset selection and the adapter demo** — **v2** per D-13. No dataset named;
  Phase 1 only preserves the inward-mapping seam.
- **Dynamic 3WD thresholds** — v2 stretch; Phase 3 ships static MDE + indifference margin (OD-8).
- **Uplift learners (T-/X-learner)** — v2; MVP uses the propensity-delta approximation whose error
  D-03 makes measurable (OD-6).
- **`.gitignore` for the Python project** — flagged during the ingest commit and still absent. Small,
  belongs to Phase 1 scaffolding; noted so it is not forgotten.

</deferred>

---

*Phase: 1-Reproducible World*
*Context gathered: 2026-07-25*
