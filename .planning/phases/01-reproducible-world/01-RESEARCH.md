# Phase 1: Reproducible World - Research

**Researched:** 2026-07-25
**Domain:** Deterministic simulation engineering, point-in-time feature stores, data-quality gates,
Python monorepo boundary enforcement, layered config validation, data/artifact versioning
**Confidence:** MEDIUM-HIGH (toolchain and mechanics HIGH/CITED; simulator realism mechanics and
exact parameterizations MEDIUM/ASSUMED — see Assumptions Log)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Simulator world shape**
- D-01: The world is a fashion-core retailer plus one low-seasonality contrast category
  (basics/home). Category structure is config-driven, never hardcoded.
- D-02: Default scale ~50k customers over 18 months (two winter peaks). A `demo` profile
  (~2k customers) exists for CI's miniature end-to-end run. Both are config profiles, not code
  paths.
- D-03: Action-response functions are latent-trait driven (price sensitivity, loyalty, fatigue,
  category affinity). Ground-truth uplift is computable per (customer, action) pair.
- D-04: The simulator deliberately includes an exploitable reward-hacking loophole (e.g. a fatigue
  penalty that can be disabled in config). The loophole is Phase 1 scope; the probe that exploits it
  arrives with the contextual bandit in v2.
- D-05: UC1 and UC2 scenarios must genuinely occur in the generated population — acceptance targets
  for the simulator, not hand-built fixtures.

**Micro-conversion (PCR) events**
- D-06: Phase 1 emits scroll/filter/dwell-class micro-events at enough fidelity that weights can
  later be derived empirically. Derivation itself is Phase 4 work. Phase 1 must not ship guessed
  weights as if derived.

**Simulated clock and action injection**
- D-07: The world advances in daily ticks: (1) read scheduled action-delivery queue, (2) apply
  response functions, (3) generate that day's organic behavior. Phase 1 runs with an empty queue —
  pure organic history. One code path, no Phase 3 rewrite.
- D-08: Actions are applied before the same tick's organic generation, so a delivered action can
  change downstream organic behavior.

**Ratified open decisions (DOC-01)**
- D-09: OD-7 ratified: DVC for data/artifacts + MLflow for runs/models. Deciding factor: reviewer
  recognizability.
- D-10: All ten ODs get individually-written ADRs (`docs/adr/001-*.md`…`010-*.md`) with genuine
  Context/Decision/Consequences text.
- D-11: OD-1, 2, 3, 5, 6, 8, 10 ratified as recommended, without re-litigation.
- D-12: OD-9 ratified as three-tier autonomy. Tier membership lives in schema-validated YAML
  (ENG-03).
- D-13: OD-4 ratified as recommendation B — decisions evaluated in simulation; data engineering
  additionally validated against a public e-commerce clickstream dataset in v2. Phase 1's only
  obligation: adapters map external shapes inward, never the reverse.

**Toolchain**
- D-14: `just` is the real operational interface; thin 3-line `Makefile` forwards `make reproduce` →
  `just reproduce`.
- D-15: `uv` for environment/lockfile/installs. `src/` layout (`src/nextmove/`). Python 3.12.
- D-16: CI is GitHub Actions, Linux-only (`ubuntu-latest`): lint (ruff + import-linter) → tests →
  miniature end-to-end on `demo` profile → golden-file comparison. No Windows matrix leg.
- D-17: The ten root planning documents move to `docs/` during Phase 1 via `git mv` (history
  preserved), alongside new `docs/adr/`.

**Storage and features**
- D-18: Canonical event and feature tables are Parquet files tracked by DVC; DuckDB queries them
  directly and is also the transform engine.
- D-19: Features materialized on a daily grid (one snapshot per active customer), and the same
  transform functions exposed for on-demand computation at an arbitrary `as_of_ts`. One definition,
  two call sites.

**Data quality and quarantine**
- D-20: Contract violations land in a queryable rejects table carrying offending row, reason,
  contract version, pipeline stage.
- D-21: Configurable reject-rate threshold (default ~0.1%) fails the run when exceeded. YAML per
  ENG-03. Deliberately not zero-tolerance.
- D-22: Every pipeline run prints a one-line data-quality summary (rows in, rows quarantined, reject
  rate, gates passed).

**Configuration**
- D-23: Config is layered: per-domain base files + thin profile overlays. `config/` holds
  `simulator.yaml`, `features.yaml`, `constraints.yaml`, `actions.yaml`, `mcda.yaml`,
  `experiments.yaml`, `autonomy.yaml`. Profiles (`default`/`demo`/`ci`) override only what differs.
- D-24: Pydantic validates the merged result; config hash taken over the resolved merge.
- D-25: Seeds are config values, not CLI flags.

### Claude's Discretion

No area was delegated wholesale. Within the decisions above, the planner retains normal latitude on:
module-internal structure, exact Pydantic model shapes, test file organization, the specific latent
trait distributions and their parameterization (so long as every one is documented per SIM-03), and
the concrete `just` recipe names beyond `reproduce`.

### Deferred Ideas (OUT OF SCOPE)

- Reward-hacking probe that exploits the D-04 loophole — v2, with the contextual bandit.
- Empirical micro-conversion weight derivation — Phase 4.
- Public-clickstream dataset selection and adapter demo — v2 per D-13. No dataset named.
- Dynamic 3WD thresholds — v2 stretch.
- Uplift learners (T-/X-learner) — v2.
- `.gitignore` for the Python project — flagged during ingest, still absent; small Phase 1
  scaffolding item.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIM-01 | Simulator generates mid-market e-commerce world with action-response functions | §Simulator Realism Mechanics, §Architecture Patterns Pattern 1 |
| SIM-02 | Simulator import-isolated; import-linter contract fails CI | §import-linter contracts (exact config), §Architectural Responsibility Map |
| SIM-03 | Every generative assumption documented in `SIMULATOR_ASSUMPTIONS.md` | §Architecture Patterns, §Don't Hand-Roll |
| SIM-04 | Simulator emits micro-conversion (PCR) events alongside macro events | §Simulator Realism Mechanics |
| DATA-01 | Canonical event schema; adapters map inward only | §Architecture Patterns Pattern 2 |
| DATA-02 | Pydantic-validated, append-only DuckDB landing; contract violations quarantined | §Quarantine/Rejects Table Patterns |
| DATA-03 | Semantic quality checks (price, monotonic ts, referential integrity) as pipeline gates | §Quarantine/Rejects Table Patterns |
| DATA-04 | Every derived table records input content hashes + config hash; lineage printable | §Content-Hash Lineage |
| FEAT-01 | Versioned feature tables keyed (customer_id, as_of_ts): RFM, session dynamics, etc. | §Point-in-Time Correctness / ASOF JOIN |
| FEAT-02 | Features strictly as_of; time-aware splits only; leakage tests in suite | §Validation Architecture, §Point-in-Time Correctness |
| ENG-01 | Modular monolith packages; storage behind thin repository layer | §Architecture Patterns Pattern 3 |
| ENG-03 | Business numbers in schema-validated, git-reviewed YAML | §Layered Config + Pydantic |
| ENG-04 | Byte-identical reruns given same seed + config hash | §Byte-Identical Determinism |
| ENG-08 | Runs entirely on a laptop; justfile operational interface; no cloud dependency | §Environment Availability |
| ENG-09 | Data/model artifacts versioned by ratified mechanism (DVC + MLflow, D-09) | §Content-Hash Lineage, §DVC pipeline stages |
| DOC-01 | OD-1..OD-10 ratified as `docs/adr/001-*.md`…`010-*.md` | §Architecture Patterns (ADR structure), canonical_refs |
</phase_requirements>

## Summary

Phase 1 is a determinism-and-boundary-discipline problem wearing a simulation costume. Every
locked decision in CONTEXT.md already answers "what tools" (`uv`, `just`, DuckDB, Parquet, DVC,
MLflow, Pydantic, ruff, import-linter). What remains is "how to use them so the five success
criteria are actually true" — and every one of the five criteria is a determinism, leakage, or
boundary claim, not a feature claim. The simulator's realism (latent traits, seasonality, UC1/UC2
scenarios) matters, but it is secondary to the engineering discipline that makes the realism
*checkable*: byte-identical reruns, content-hash lineage, ASOF-joined leakage-free features, an
import-linter contract that actually fails CI, and a quarantine table that never silently drops
rows.

The single highest-risk area is **determinism**, because Python's ecosystem has several
well-documented, easy-to-miss nondeterminism sources that don't show up until someone actually
diffs two runs: Python's randomized string hashing (affects `set`/`dict`-derived iteration order
unless `PYTHONHASHSEED` is fixed or all set-derived sequences are explicitly sorted before use),
NumPy's legacy global RNG (`np.random.seed` / bare `np.random.rand`) versus the modern
`Generator`/`SeedSequence` API (the only one that supports the per-entity `spawn()` pattern D-25's
"seeds as config" implies), DuckDB's multi-threaded execution (which the DuckDB team documents can
produce floating-point-level differences in aggregates like `stddev`/`corr` unless threads are
pinned or results are order-independent by construction), and PyArrow's Parquet writer, which
embeds its own version string in file metadata and does not guarantee row order unless the table is
explicitly sorted before writing. None of these are exotic — they are the standard checklist any
senior data engineer runs through when someone says "byte-identical" — but each one is a silent
failure mode until a golden-file test catches it, so the plan must build the diff-based
determinism test *early*, not as a Phase 1 afterthought.

The second area is **point-in-time correctness**, which DuckDB's `ASOF JOIN` makes structurally
easy to get right (it is purpose-built for "give me the value as of this timestamp") and easy to
verify (a leakage test is just: for every feature snapshot, assert no contributing event's
timestamp exceeds `as_of_ts`). The daily materialization grid (D-19) plus the same-function
on-demand path is the standard "batch table + point lookup share one definition" pattern used by
every production feature store (Feast, Tecton, Databricks) — Phase 1 is building a minimal,
DuckDB-native version of that pattern, not inventing a new one.

The third area is **lineage and quarantine**, both of which are well-trodden DVC/Pandera-adjacent
patterns: stamp content hashes and a config hash into each derived table's metadata (or a sidecar
manifest table), and route Pydantic/Pandera validation failures into a rejects table rather than
raising and halting or silently dropping. CONTEXT.md has already decided the "what" (Pydantic
validates events per DATA-02; a queryable rejects table per D-20); this research supplies the "how"
so the plan doesn't have to improvise it during execution.

**Primary recommendation:** Treat the determinism and leakage tests as Wave-0 infrastructure, built
and passing on a trivial fixture *before* the simulator's realism logic is built out, so that every
subsequent simulator/feature change is validated against a working harness rather than retrofitted
against one built at the end.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Customer/catalog/inventory/campaign world generation | Simulator package (`simulator/`) | — | Cross-cutting, import-isolated component (ADR-AD-12); must never be importable by `models/decisions/policies/features` |
| Daily-tick clock + action-queue drain | Simulator package | — | Owns the loop that produces organic + injected behavior (D-07/D-08); Phase 3 reuses the same loop, doesn't rebuild it |
| Event schema validation + quarantine | Ingest package (`ingest/`) | Database/Storage (DuckDB) | Ingest owns the Pydantic contract check; DuckDB is where validated + rejected rows land (DATA-02) |
| Canonical event storage | Database/Storage (DuckDB over Parquet, DVC-tracked) | — | Append-only landing zone; no package reaches into Parquet/DuckDB directly (ENG-01 thin repository layer) |
| Point-in-time feature computation | Feature package (`features/`) | Database/Storage (DuckDB ASOF JOIN) | Feature package owns transform *definitions* in config; DuckDB executes the ASOF join that guarantees no lookahead |
| Content-hash + config-hash lineage stamping | Database/Storage (table metadata / manifest table) | Ingest + Feature packages (call the hashing utility) | Lineage is a storage-layer concern but every producer package must call the same hashing utility — a shared `lineage` helper, not per-package reimplementation |
| Config loading, merge, validation, hashing | Cross-cutting config module (`config/` loader, not a `src/nextmove/` package) | All packages (consumers) | Config is infrastructure every package depends on; must live below all ten packages in the import graph so nothing creates a cycle |
| Import-boundary enforcement | CI (import-linter) | Repository layout (`pyproject.toml`) | Enforcement is a build-time gate, not runtime code — the "tier" is CI itself |
| Reproducibility orchestration (`just reproduce`) | Operational interface (`justfile`) | CI (GitHub Actions) | Thin orchestration layer that calls into the DVC pipeline; not a Python package |

## Standard Stack

### Core
| Library | Version (verified 2026-07-25) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | 2.13.4 [VERIFIED: pip index / official docs pydantic.dev] | Event/feature/config schema validation, layered config models | Locked (D-24, DATA-02); de facto Python validation standard, integrates with DuckDB/Arrow via typed dicts |
| `pyarrow` | 25.0.0 [VERIFIED: pip index / official docs arrow.apache.org] | Parquet read/write, Arrow table sorting before write | Locked (D-18 canonical Parquet tables); DuckDB's native Parquet path also uses Arrow under the hood |
| `duckdb` | 1.5.4 (Python client) [VERIFIED: pip index / official docs duckdb.org] | Query engine + transform engine over Parquet, ASOF JOIN for point-in-time features | Locked (D-18); only mainstream embedded analytical engine with native ASOF JOIN and native Parquet reader |
| `dvc` | 3.67.1 [VERIFIED: pip index / official docs doc.dvc.org] | Content-addressable versioning of Parquet event/feature tables | Locked (D-09, ratifies OD-7) |
| `mlflow` | 3.14.0 [VERIFIED: pip index / official docs mlflow.org] | Run/experiment tracking (used lightly in Phase 1 — real payoff starts Phase 4) | Locked (D-09) |
| `import-linter` | 2.13 [VERIFIED: pip index / official docs import-linter.readthedocs.io] | Forbidden-import contract failing CI (SIM-02) | Locked toolchain (D-16); the standard Python import-boundary linter, purpose-built for this exact contract type |
| `ruff` | 0.16.0 [VERIFIED: pip index / official docs docs.astral.sh/ruff] | Lint + format | Locked (D-16) |
| `numpy` | 2.5.1 [VERIFIED: pip index / official docs numpy.org] | Latent-trait sampling, `Generator`/`SeedSequence` RNG | Underpins deterministic per-entity randomness (D-03, D-25) |
| `pandas` | 2.3.3 (pin to 2.x, not 3.0 — see note) [VERIFIED: pip index] | Intermediate dataframe manipulation before Arrow/Parquet conversion | Widely compatible with pyarrow/pandera; pandas 3.0 is very new (released within the verification window) — pin to latest 2.x for stability unless a specific 3.0 feature is needed |
| `uv` | 0.11.29 [VERIFIED: local install, `uv --version`] | Environment/lockfile/installs | Locked (D-15) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pandera` | 0.32.1 [VERIFIED: pip index / official docs pandera.readthedocs.io] | Semantic dataframe-level checks (DATA-03: negative price, monotonic timestamps, referential integrity) as a layer on top of per-row Pydantic validation | Use for whole-dataframe/statistical checks that are awkward to express as a single Pydantic model validator (e.g., "timestamps within a session are monotonic," "SKU exists in catalog") |
| `pyyaml` | latest stable [ASSUMED — not independently verified this session] | Parsing `config/*.yaml` layered base + profile overlay files | Standard YAML parser for the config layer; alternative `ruamel.yaml` only needed if round-trip comment preservation matters (it doesn't here) |
| `pytest` + `pytest-cov` | latest stable [ASSUMED] | Test runner + coverage (ENG-06 lands fully in Phase 5, but the Wave-0 harness starts here) | Standard; `pytest-cov` feeds the coverage thresholds Phase 5 enforces |
| `hypothesis` | latest stable [ASSUMED] | Property-based tests (used more heavily from Phase 2's DEC-08, but the pattern should be established if any Phase 1 invariant benefits, e.g. "no negative price ever lands validated") | Corpus-mandated pattern (ADR-AD-17); not strictly required in Phase 1 but cheap to adopt early |
| `mkdocs` or plain Markdown | n/a | `docs/adr/NNN-*.md` format | ADR files are plain Markdown; no tooling dependency needed for DOC-01 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pandera for semantic checks | Hand-rolled DuckDB `CHECK`-style SQL assertions | DuckDB SQL assertions are viable and arguably more "DuckDB-native," but Pandera gives typed, testable, reusable schema objects with built-in lazy validation and failure-case extraction — less code to hand-roll for the same DATA-03 guarantee. Either is acceptable; Pandera is recommended for less boilerplate. |
| DVC for artifact versioning | Custom content-hash directory store | Rejected by D-09 (ratified OD-7) for reviewer recognizability. Not re-litigated. |
| `pydantic-settings` for layered config | Plain Pydantic `BaseModel` + hand-written deep-merge function | `pydantic-settings` is designed for env-var/CLI layering, not multi-file YAML base+overlay merging; a small explicit recursive-dict-merge function (≤30 lines) plus `BaseModel.model_validate(merged_dict)` is simpler to reason about and test than bending `pydantic-settings`' source-precedence model to fit YAML profile overlays. Recommend hand-writing the merge (see Code Examples) rather than importing a library for it — this is one of the few places NOT to add a dependency. |

**Installation:**
```bash
uv add pydantic pyarrow duckdb pandera pyyaml
uv add --dev dvc mlflow import-linter ruff pytest pytest-cov hypothesis
```

**Version verification:** All Core and Supporting versions marked `[VERIFIED]` above were checked
via `pip index versions <package>` against PyPI on 2026-07-25 and cross-referenced against each
project's official documentation site. `pandas` 3.0.x exists on PyPI but is very recent; pin to the
latest 2.x line (`pandas>=2.3,<3`) unless a specific pandas 3.0 feature is required, since pyarrow/
pandera compatibility with the pandas 3.0 major version is not yet independently verified in this
session — treat any 3.0 pin as `[ASSUMED]` and re-verify compatibility at install time.

## Package Legitimacy Audit

The `gsd-tools query package-legitimacy check` seam returned `SUS` for every core package checked,
with reasons `too-new` and/or `unknown-downloads`. Investigation shows this is a **checker signal
limitation in this environment**, not a genuine legitimacy concern: `weeklyDownloads` is `null` for
every package (the download-count data source is unavailable here), and `too-new` is measuring the
**most recent patch release date** (e.g. ruff 0.16.0 published 2026-07-23) rather than the
package's first-published date — every actively-maintained package on PyPI ships new patch releases
regularly, so this heuristic flags all healthy, actively-developed projects.

All packages below are independently known (general knowledge, not this-session-verified) to be
long-established, high-profile projects with multi-year histories and canonical GitHub
organizations. They are approved despite the seam's `SUS` verdict, with the reasoning documented
so the disposition is auditable rather than silently overridden.

| Package | Registry | Known Repo | Seam Verdict | Seam Reasons | Disposition |
|---------|----------|-------------|--------|---------|-------------|
| `pydantic` | PyPI | github.com/pydantic/pydantic | SUS | unknown-downloads | **Approved** — seam repo lookup succeeded; downloads-null is an environment data-source gap, not a legitimacy signal |
| `pyarrow` | PyPI | github.com/apache/arrow (Apache project) | SUS | too-new, unknown-downloads | **Approved** — Apache Arrow, foundation-governed project |
| `duckdb` | PyPI | github.com/duckdb/duckdb-python | SUS | too-new, unknown-downloads | **Approved** — seam-confirmed repo |
| `import-linter` | PyPI | github.com/seddonym/import-linter [ASSUMED — repo not returned by seam] | SUS | too-new, unknown-downloads, no-repository | **Approved** — well-known, single-purpose tool referenced throughout the ADR corpus and official docs at import-linter.readthedocs.io |
| `dvc` | PyPI | github.com/iterative/dvc [ASSUMED — seam returned github.com/treeverse/dvc, which is incorrect; treeverse owns lakeFS, not DVC] | SUS | unknown-downloads | **Approved, with a correction flag** — the seam's `repoUrl` for `dvc` is wrong (it returned the lakeFS org). DVC's actual canonical repo is `github.com/iterative/dvc`. Package identity itself is not in doubt (locked by D-09), but this discrepancy is exactly the kind of signal a `checkpoint:human-verify` should catch — planner must add one before the DVC install step |
| `mlflow` | PyPI | github.com/mlflow/mlflow [ASSUMED — not returned by seam] | SUS | unknown-downloads, no-repository | **Approved** — locked by D-09; official docs at mlflow.org confirm identity |
| `pandera` | PyPI | github.com/unionai-oss/pandera (formerly pandera-dev) | SUS | too-new, unknown-downloads | **Approved** — seam-confirmed repo, matches official docs |
| `ruff` | PyPI | github.com/astral-sh/ruff [ASSUMED — seam returned docs URL not repo] | SUS | too-new, unknown-downloads | **Approved** — locked by D-16 |
| `numpy` | PyPI | github.com/numpy/numpy [ASSUMED — not returned by seam] | SUS | too-new, unknown-downloads, no-repository | **Approved** — foundational scientific Python package |
| `pandas` | PyPI | github.com/pandas-dev/pandas [ASSUMED — not returned by seam] | SUS | too-new, unknown-downloads, no-repository | **Approved** — foundational scientific Python package |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** all ten packages checked, per the seam's raw output —
but the disposition above overrides the seam's default action for nine of them based on independent
knowledge of these being canonical, long-established projects. **The one exception the planner must
still gate behind `checkpoint:human-verify`:** the `dvc` package, because the seam's `repoUrl`
signal was factually wrong (pointed at the wrong GitHub org). Before the first `uv add dvc` /
`dvc init` step, the plan should include a lightweight checkpoint confirming the installed package
resolves to `iterative/dvc` on PyPI's project page, not a typosquat.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────── simulator/ (import-isolated) ───────────────────────────────┐
│                                                                                                │
│   config/simulator.yaml ──► World init (customers w/ latent traits, catalog, inventory,      │
│                              campaigns) ──► Daily-tick loop:                                  │
│                              ┌─────────────────────────────────────────────────────┐          │
│                              │ (1) drain action-delivery queue (empty in Phase 1)  │          │
│                              │ (2) apply response functions → mutate world state   │          │
│                              │ (3) generate organic behavior for the day           │          │
│                              │     (sessions, views, add-to-cart, orders,          │          │
│                              │      campaign exposures, micro-conversion events)   │          │
│                              └─────────────────────────────────────────────────────┘          │
│                                                     │ emits typed events (Pydantic)            │
└─────────────────────────────────────────────────────┼────────────────────────────────────────┘
                                                        ▼
                                        ┌───────────────────────────────┐
                                        │  ingest/  (validation gate)   │
                                        │  Pydantic contract check      │
                                        │  + Pandera semantic checks    │
                                        │  (DATA-02, DATA-03)           │
                                        └───────────┬───────────┬───────┘
                                          valid rows │           │ invalid rows
                                                      ▼           ▼
                                   ┌─────────────────────┐  ┌──────────────────┐
                                   │ canonical event      │  │ rejects/quarantine│
                                   │ Parquet tables        │  │ table (D-20)      │
                                   │ (DVC-tracked, DuckDB   │  │ row+reason+stage  │
                                   │ queries directly)      │  └──────────────────┘
                                   └──────────┬─────────────┘
                                              │ + input content hashes + config hash (DATA-04)
                                              ▼
                              ┌─────────────────────────────────────┐
                              │ features/  (daily grid + on-demand)  │
                              │ DuckDB ASOF JOIN: event tables       │
                              │ ──► point-in-time feature snapshots  │
                              │ keyed (customer_id, as_of_ts)        │
                              │ (FEAT-01, FEAT-02)                   │
                              └───────────────┬───────────────────────┘
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                    daily materialized grid          on-demand as_of_ts lookup
                    (batch training input)           (same transform fns, Phase 2's
                                                        POST /v1/decisions caller)

  CI gate (parallel to the above): import-linter contract fails the build if models/,
  decisions/, policies/, or features/ import simulator/  (SIM-02)
```

### Recommended Project Structure
```
src/nextmove/
├── simulator/          # world gen, latent traits, daily tick, response functions (import-isolated)
├── ingest/              # Pydantic contracts, Pandera semantic checks, quarantine routing
├── features/            # DuckDB ASOF transforms, daily grid materialization, on-demand lookup
├── segmentation/        # stubbed boundary only (Phase 4 populates)
├── models/              # stubbed boundary only (Phase 4 populates) — import-linter target
├── rules/                # stubbed boundary only (Phase 2 populates)
├── decisions/            # stubbed boundary only (Phase 2 populates) — import-linter target
├── policies/             # stubbed boundary only (Phase 2 populates) — import-linter target
├── explain/               # stubbed boundary only (Phase 2 populates)
├── evaluate/               # stubbed boundary only (Phase 3 populates)
└── api/                     # stubbed boundary only (Phase 2 populates)
config/
├── simulator.yaml        # world params, latent trait distributions, seasonality curve, seeds
├── features.yaml          # feature list, daily grid config
├── constraints.yaml        # (stub — Phase 2)
├── actions.yaml              # (stub — Phase 2)
├── mcda.yaml                  # (stub — Phase 4)
├── experiments.yaml            # (stub — Phase 3)
├── autonomy.yaml                 # D-12 tiers
└── profiles/
    ├── default.yaml         # ~50k customers, 18 months
    ├── demo.yaml              # ~2k customers, thin overlay
    └── ci.yaml                 # miniature, thin overlay
docs/
├── adr/001-*.md … 010-*.md  # DOC-01, from git mv of root planning docs + new ADRs
├── SIMULATOR_ASSUMPTIONS.md  # SIM-03
└── ...                        # ten root docs moved here per D-17
tests/
├── unit/
├── property/
├── golden/              # byte-identical rerun fixtures (ENG-04)
└── leakage/              # FEAT-02 as_of tests
dvc.yaml                  # pipeline stages: simulate → ingest → features
justfile                  # `just reproduce` and friends (D-14)
Makefile                  # 3-line forward to justfile (D-14)
pyproject.toml            # uv project, import-linter contracts, ruff config
```

### Pattern 1: Latent-trait-driven response functions with per-entity deterministic RNG

**What:** Each customer is assigned latent traits (price sensitivity, loyalty, fatigue, category
affinity) at world-init time, sampled from configured distributions using a per-customer RNG stream
derived from the run seed. Action-response functions read these traits plus context (inventory,
season) to compute a deterministic (given traits+context) or seeded-stochastic response.

**When to use:** For every organic-behavior and action-response computation in `simulator/`.

**Example:**
```python
# Source: NumPy official docs (numpy.org/doc/stable/reference/random/parallel.html), CITED
import numpy as np

def customer_rng(root_seed: int, customer_id: int) -> np.random.Generator:
    """Deterministic, independent RNG stream per customer.

    Combining [customer_id, root_seed] into SeedSequence entropy gives every customer
    an independent, reproducible stream -- reruns with the same root_seed produce the
    same per-customer draws regardless of iteration order, and customers never share
    correlated randomness.
    """
    return np.random.default_rng([customer_id, root_seed])

def sample_latent_traits(root_seed: int, customer_id: int, config: "SimulatorConfig") -> "LatentTraits":
    rng = customer_rng(root_seed, customer_id)
    price_sensitivity = rng.beta(config.price_sensitivity_alpha, config.price_sensitivity_beta)
    loyalty = rng.beta(config.loyalty_alpha, config.loyalty_beta)
    # ... fatigue, category_affinity similarly, all from config-defined distribution params
    return LatentTraits(price_sensitivity=price_sensitivity, loyalty=loyalty, ...)
```

**Anti-pattern to avoid:** calling `np.random.seed(root_seed)` once and then drawing from the
legacy global `np.random.rand()` / `np.random.choice()` API for each customer in a loop. This is
order-dependent — parallelizing the loop, changing customer iteration order, or adding a customer
mid-population all silently change every downstream draw. The per-entity `default_rng([entity_id,
root_seed])` pattern above is immune to iteration order and to population changes elsewhere.

### Pattern 2: Canonical event schema with inward-only adapters

**What:** One `event(event_id, customer_id, session_id, ts, type, payload, source)` Pydantic model
with a `payload: EventPayload` discriminated union keyed by `type` (view, add_to_cart, purchase,
campaign_exposure, action_delivered, override, scroll/filter/dwell micro-events). The simulator
emits events in this shape directly; any future adapter (public dataset, GA4, CSV — v2) maps its
external shape *into* this schema, never the reverse.

**When to use:** Every event the simulator emits, from the first line of `ingest/`.

**Example:**
```python
# Source: locked ADR-TD-06 (TECHNICAL_DIRECTION.md §2) + Pydantic discriminated union pattern
from typing import Literal, Union
from pydantic import BaseModel, Field

class ViewPayload(BaseModel):
    type: Literal["view"] = "view"
    sku: str
    category: str

class AddToCartPayload(BaseModel):
    type: Literal["add_to_cart"] = "add_to_cart"
    sku: str
    quantity: int = Field(gt=0)

EventPayload = Union[ViewPayload, AddToCartPayload, ...]  # discriminated on `type`

class Event(BaseModel):
    event_id: str
    customer_id: str
    session_id: str
    ts: "datetime"   # tz-aware, UTC — see Common Pitfalls
    type: str
    payload: EventPayload = Field(discriminator="type")
    source: Literal["simulator", "adapter"] = "simulator"
```

### Pattern 3: Storage behind a thin repository layer

**What:** No package (`ingest/`, `features/`, etc.) calls `pyarrow.parquet.write_table` or opens a
DuckDB connection directly. A single `nextmove.storage` (or similarly-named cross-cutting) module
exposes `write_events(df, table_name, lineage)`, `read_asof(table_name, as_of_ts)`, etc., and is the
only place Parquet/DuckDB APIs are imported.

**When to use:** Every read/write of a canonical or feature table.

**Rationale:** ENG-01 requires this explicitly ("storage sits behind a thin repository layer"), and
it is also the natural place to enforce sorted-row-order-before-write (determinism) and
lineage-stamping (DATA-04) exactly once instead of at every call site.

### Anti-Patterns to Avoid
- **Global `np.random` calls anywhere in `simulator/`:** breaks per-entity reproducibility and makes
  parallelization unsafe later. Always thread an explicit `Generator` through function signatures.
- **Iterating over a Python `set` (or `dict.keys()` built from a set) to determine output row
  order:** Python's string hash is randomized per-process by default (`PYTHONHASHSEED`), so set
  iteration order is not stable across runs unless the hash seed is pinned. Sort explicitly before
  any operation whose result affects file bytes or table row order — do not rely on `PYTHONHASHSEED`
  pinning as the *only* safeguard, since it's easy to forget in a subprocess or CI runner.
- **Multi-threaded DuckDB aggregation for outputs claimed byte-identical:** DuckDB documents that
  floating-point aggregates (`stddev`, `corr`, others) can differ under parallel execution because
  local-then-merge summation order isn't guaranteed identical across runs. For any table whose
  bytes are compared in a golden-file test, either `PRAGMA threads=1` for that query or make the
  computation order-independent (fixed `ORDER BY` before aggregation with a deterministic tiebreak
  column).
- **Writing Parquet straight from a pandas DataFrame without an explicit sort:** row order from
  upstream computation (especially anything that touched a `set`, a `dict` keyed by hash, or ran
  under multiprocessing) is not guaranteed stable. Call `.sort_values([...])` or `pa.Table.sort_by`
  on a deterministic key tuple (e.g., `(customer_id, ts, event_id)`) immediately before
  `write_table`.
- **Embedding wall-clock time in table metadata:** any custom Parquet key-value metadata that
  includes `datetime.now()` (e.g., "generated_at") will break byte-identical comparison between
  two runs at different times. Lineage metadata should carry the input content hashes and config
  hash (both stable), not a wallclock timestamp.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Point-in-time feature joins | A custom "find the latest row before timestamp X" loop in Python/pandas | DuckDB `ASOF JOIN` | Purpose-built, correctly handles ties and missing-right-side rows, and is the same mechanism production feature stores (Feast, Tecton, Databricks) use under the name "point-in-time join" / "time travel" — hand-rolling it in Python is slower and easy to get subtly wrong on tie-breaking |
| Import-boundary enforcement | A custom AST-walking script that greps for `import simulator` | `import-linter` forbidden contract | Already handles transitive imports, TYPE_CHECKING-guarded imports, and produces a clean CI-failing exit code; a hand-rolled grep will miss indirect imports through a re-export |
| Data/artifact versioning | Custom content-hash directory store with a manifest JSON | DVC | Explicitly ratified by D-09/OD-7 — not to be re-litigated; DVC already solves content-addressable storage, `dvc.lock` staleness detection, and remote storage swapping |
| Dataframe-level semantic validation (negative price, monotonic session timestamps) | Hand-written `for row in df.itertuples()` validation loops | Pandera schema with checks, `lazy=True` | Vectorized, produces structured `failure_cases` with row index + check name for free — directly feeds the D-20 rejects table's "reason" column without extra bookkeeping |
| Config merge + hash | A bespoke YAML-deep-merge-plus-hash library dependency | ~20-line recursive dict merge + `json.dumps(..., sort_keys=True)` + `hashlib.sha256` | The merge logic needed here (later profile overlay wins per-key) is simple enough that a small, fully-tested in-repo function is more auditable than an external dependency, and avoids adding a library whose merge semantics might not match "override only what differs" exactly |

**Key insight:** Every "don't hand-roll" item above already has a decision precedent in CONTEXT.md
(DuckDB, import-linter, DVC are all locked toolchain). The one place worth deliberately *not*
reaching for a library is config merging — it's simple enough, and specific enough to D-23's "thin
overlay" semantics, that a small hand-written function is the more honest and more testable choice.

## Runtime State Inventory

Not applicable — this is a greenfield phase with no existing runtime state, deployed services, or
prior data to migrate. There is no rename/refactor/migration in scope for Phase 1.

**Nothing found in any category** — verified by direct inspection of the repository root (only
`.git`, `.planning/`, and the ten root planning `.md` files exist; no `src/`, no databases, no
deployed services, no OS-registered tasks, no secrets files).

## Common Pitfalls

### Pitfall 1: Timezone-naive timestamps breaking monotonicity checks and ASOF joins
**What goes wrong:** Simulator emits `datetime.now()`-style naive timestamps, or mixes naive and
tz-aware timestamps across tables; DuckDB ASOF JOIN and DATA-03's monotonic-timestamp check then
silently misbehave (comparisons between naive and aware datetimes raise, or naive timestamps get
implicitly treated as UTC/local inconsistently).
**Why it happens:** The simulator's clock is a virtual daily-tick clock, not wall-clock time, and
it's easy to construct timestamps as naive Python `datetime` objects out of habit.
**How to avoid:** Every timestamp the simulator emits is tz-aware UTC from a `SimClock` object
driven by the config-defined start date + tick count — never `datetime.now()`. Pydantic event
models type `ts` as a tz-aware `datetime` and reject naive values.
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` anywhere in
tests; ASOF join returning unexpected NULLs.

### Pitfall 2: Reject-rate threshold silently masking a broken generator, not just bad data
**What goes wrong:** D-21's configurable reject-rate threshold (default ~0.1%) is meant to catch
slow real-world data degradation, but if the simulator itself has a bug that produces, say, 0.05%
malformed rows deterministically, the threshold never fires and the bug ships silently, "validated"
by a passing pipeline.
**Why it happens:** The threshold is a data-quality gate, not a correctness gate — it says nothing
about *why* rows are rejected.
**How to avoid:** The one-line data-quality summary (D-22) must be inspected in CI logs, not just
asserted `< threshold`; additionally, a Phase 1 test should assert the *simulator's own* reject
rate is exactly zero on a golden-seed run (the simulator should never generate a malformed event by
construction — the quarantine table exists for the ingest layer's benefit and for the future
public-dataset track, not to give the simulator an excuse to be sloppy).
**Warning signs:** Nonzero reject rate on a simulator-only (no adapters) golden-seed run.

### Pitfall 3: Config hash instability from float formatting or dict key order
**What goes wrong:** Two runs with logically identical resolved config produce different config
hashes because YAML parsing, Pydantic serialization, or Python's default `repr()`/`json.dumps()`
formats a float (e.g. `0.1` vs `0.10000000000000001` vs scientific notation) or orders dict keys
differently.
**Why it happens:** `json.dumps()` without `sort_keys=True` preserves insertion order (which is
YAML-file-order, itself stable per file but not guaranteed identical across a base+overlay merge
unless the merge function is careful); floats serialized via different paths (raw YAML float vs.
a value computed at runtime) can differ in string representation even when numerically equal.
**How to avoid:** Hash the *canonical* serialization: `json.dumps(model.model_dump(mode="json"),
sort_keys=True, separators=(",", ":"))`, then `hashlib.sha256(...).hexdigest()`. Never hash a
Python `repr()` or an unsorted dict. Round or explicitly format floats that come from computed
defaults (not directly from YAML) if bit-for-bit float repr stability matters.
**Warning signs:** Config hash changes between two runs where no YAML file changed.

### Pitfall 4: import-linter contract passes locally but the CI job doesn't actually run it
**What goes wrong:** `lint-imports` is added to `pyproject.toml` and works when run manually, but
the CI workflow step either isn't wired to fail the build on nonzero exit, or runs `lint-imports`
against a stale/incomplete `src/` layout (e.g., before `models/`, `decisions/`, `policies/` exist as
real packages with `__init__.py`), so the contract silently has nothing to check.
**Why it happens:** SIM-02 requires the contract to fail CI specifically when `models/`,
`decisions/`, `policies/`, or `features/` import `simulator` — but if those packages are still empty
stub directories without `__init__.py` when Phase 1 lands, import-linter may not register them as
importable modules and the contract passes vacuously.
**How to avoid:** Every one of the ten `src/nextmove/` packages gets a real `__init__.py` (even if
the module body is a docstring + `NotImplementedError` stub) in Phase 1's scaffolding step, and a
CI smoke test asserts `lint-imports` output mentions all four forbidden-source packages by name (not
just that the exit code is 0).
**Warning signs:** CI green on a PR that actually adds `from nextmove.simulator import ...` inside
`nextmove.models`.

## Code Examples

### Layered config merge + Pydantic validation + stable hash
```python
# Source: pattern synthesized from Pydantic official docs (docs.pydantic.dev/latest/concepts/config/)
# CITED for Pydantic mechanics; the merge function itself is hand-written per "Don't Hand-Roll".
import hashlib
import json
from pathlib import Path
import yaml
from pydantic import BaseModel

def deep_merge(base: dict, overlay: dict) -> dict:
    """Overlay wins per-key; nested dicts merge recursively (D-23 'override only what differs')."""
    merged = dict(base)
    for key, overlay_value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(overlay_value, dict):
            merged[key] = deep_merge(merged[key], overlay_value)
        else:
            merged[key] = overlay_value
    return merged

def load_resolved_config(domain_files: list[Path], profile_file: Path, model: type[BaseModel]) -> tuple[BaseModel, str]:
    base: dict = {}
    for f in domain_files:
        base = deep_merge(base, yaml.safe_load(f.read_text()) or {})
    overlay = yaml.safe_load(profile_file.read_text()) or {}
    resolved = deep_merge(base, overlay)
    validated = model.model_validate(resolved)   # Pydantic validates the merged result (D-24)
    canonical = json.dumps(validated.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return validated, config_hash
```

### DuckDB ASOF JOIN for point-in-time feature computation
```sql
-- Source: DuckDB official docs (duckdb.org/docs/current/guides/sql_features/asof_join), CITED
-- Given: events(customer_id, ts, ...) and a target grid of (customer_id, as_of_ts) rows,
-- fetch the latest event state at or before each as_of_ts -- guarantees no lookahead.
SELECT
    grid.customer_id,
    grid.as_of_ts,
    events.* EXCLUDE (customer_id, ts)
FROM feature_grid AS grid
ASOF LEFT JOIN events
    ON grid.customer_id = events.customer_id
   AND grid.as_of_ts >= events.ts
ORDER BY grid.customer_id, grid.as_of_ts;  -- explicit ORDER BY for deterministic output row order
```

### Leakage test pattern (FEAT-02)
```python
# Source: pattern synthesized from point-in-time-correctness testing literature (Databricks docs,
# Feast docs) -- CITED as a design pattern, not a copied library API.
def test_no_feature_snapshot_leaks_future_events(feature_table, event_table):
    """For every (customer_id, as_of_ts) snapshot, no contributing event's ts may exceed as_of_ts."""
    joined = feature_table.merge(event_table, on="customer_id", suffixes=("_feat", "_evt"))
    violations = joined[joined["ts_evt"] > joined["as_of_ts"]]
    assert violations.empty, f"{len(violations)} leakage violations found: {violations.head()}"
```

### Golden-file determinism test (ENG-04)
```python
# Source: pattern synthesized from golden-file testing literature; hashing approach is standard
# practice, CITED conceptually rather than to one library.
import hashlib
import subprocess

def sha256_of_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def test_two_seeded_runs_are_byte_identical(tmp_path_factory):
    run_a = tmp_path_factory.mktemp("run_a")
    run_b = tmp_path_factory.mktemp("run_b")
    for out_dir in (run_a, run_b):
        subprocess.run(["just", "reproduce", "--profile", "ci", "--out", str(out_dir)], check=True)
    for table in ("events.parquet", "features.parquet"):
        assert sha256_of_file(run_a / table) == sha256_of_file(run_b / table), f"{table} not byte-identical"
```

### import-linter forbidden contract
```toml
# Source: import-linter official docs (import-linter.readthedocs.io/en/stable/get_started/configure/), CITED
[tool.importlinter]
root_packages = ["nextmove"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "simulator internals must never reach the learned/decision layers"
type = "forbidden"
source_modules = [
    "nextmove.models",
    "nextmove.decisions",
    "nextmove.policies",
    "nextmove.features",
]
forbidden_modules = ["nextmove.simulator"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Manual "asof merge" via pandas `merge_asof` | DuckDB native `ASOF JOIN` | DuckDB 0.9+ (2023) | `merge_asof` requires globally sorted single-key input and pandas in memory; DuckDB's ASOF JOIN works directly on Parquet with SQL semantics and multi-column join keys, avoiding a full pandas materialization step |
| `np.random.seed()` + legacy global RNG functions | `np.random.default_rng()` / `Generator` + `SeedSequence` | NumPy 1.17 (2019), now the documented recommended API | Legacy global RNG is order-dependent and not parallel-safe; `Generator`/`SeedSequence.spawn()` is the only path that supports reproducible per-entity independent streams, which D-25's "seeds as config" implicitly requires |
| Feast / Tecton-style external feature store for MVP | DuckDB-native feature transforms directly on Parquet | N/A — deliberate MVP scoping decision (ADR-AD-03), not an industry-wide shift | Feast rejected for MVP as "complexity without payoff"; DuckDB's native SQL + ASOF JOIN covers the point-in-time correctness guarantee Feast would otherwise provide, at much lower operational cost for a single-laptop system |
| MLflow file-based tracking store (`./mlruns`) | MLflow now recommends the database-backed tracking store for anything beyond throwaway local experiments | MLflow docs currently mark the file store as "maintenance mode" | For Phase 1's lightweight tracking usage (heavier payoff starts Phase 4), the default local `./mlruns` file store is acceptable and simplest, but note this for Phase 4 planning — a SQLite-backed tracking URI (`sqlite:///mlflow.db`) may be worth switching to before model-comparison volume increases |

**Deprecated/outdated:**
- `np.random.seed()` / bare `np.random.rand()`, `np.random.choice()` at module scope: still works,
  but NumPy's own docs steer new code toward `Generator`. Not technically deprecated/removed, but
  the wrong choice for this project's per-entity determinism requirement.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact GitHub org/repo URLs for `dvc` (iterative/dvc), `mlflow` (mlflow/mlflow), `numpy`, `pandas`, `ruff`, `import-linter` — not returned or returned incorrectly by the package-legitimacy seam this session | Package Legitimacy Audit | Low for numpy/pandas/ruff (extremely well-known, no realistic ambiguity); Medium for `dvc` specifically since the seam actively returned a wrong repo (treeverse/lakeFS) — planner must add a `checkpoint:human-verify` before the DVC install step as directed |
| A2 | `pandas` 3.0.x compatibility with `pyarrow`/`pandera` not independently verified this session; recommendation to pin `pandas>=2.3,<3` is a precaution, not a confirmed incompatibility | Standard Stack | Low — worst case is an unnecessary version ceiling that gets relaxed later; re-verify at install time |
| A3 | Latent-trait distribution family choices (Beta for price sensitivity/loyalty) in the Pattern 1 code example are illustrative, not a locked recommendation — CONTEXT.md explicitly leaves "the specific latent trait distributions and their parameterization" to planner/implementer discretion | Architecture Patterns Pattern 1 | Low — CONTEXT.md already delegates this; document whatever distributions are chosen in `SIMULATOR_ASSUMPTIONS.md` per SIM-03 regardless of which family is picked |
| A4 | Synthetic e-commerce agent-based simulation design pattern (latent traits → response functions) is drawn from general retail-simulation research literature (RetailSynth, agent-based pricing papers) surfaced via WebSearch, not from an authoritative single source specific to this project's exact trait set | Simulator Realism Mechanics (Summary) | Low-Medium — the general pattern (latent traits parameterize response functions) is well-supported across multiple independent sources, but exact functional forms are a design choice the plan must still make explicitly, not treat as externally validated |
| A5 | `pyyaml`, `pytest`, `pytest-cov`, `hypothesis` versions not independently checked against PyPI this session (listed as "latest stable") | Supporting stack table | Low — all are extremely stable, widely-used libraries; verify exact pinned versions at `uv add` time |
| A6 | MLflow's file-store-vs-database-store guidance and its "maintenance mode" framing reflects the state of MLflow's own docs at research time; exact wording/status may have shifted by execution time | State of the Art | Low — doesn't block Phase 1 (file store is fine for now); worth a quick re-check before Phase 4 when tracking volume increases |

**If this table is empty:** N/A — see entries above.

## Open Questions

1. **Exact latent-trait distribution families and parameters for D-03**
   - What we know: CONTEXT.md requires price sensitivity, loyalty, fatigue, and category affinity
     as documented latent traits with ground-truth-computable uplift; distribution choice is
     explicitly Claude's/planner's discretion.
   - What's unclear: No specific distribution family (Beta, LogNormal, mixture) is mandated by any
     source document.
   - Recommendation: The plan should pick simple, well-understood distributions (Beta(α,β) bounded
     [0,1] traits are a reasonable default, as illustrated in Pattern 1) and document the exact
     parameterization in `SIMULATOR_ASSUMPTIONS.md` per SIM-03 — the choice matters less than the
     documentation discipline around it.

2. **Whether lineage (content hash + config hash) is stamped as Parquet file-level key-value
   metadata or as a separate sidecar manifest/lineage table**
   - What we know: D-18 says DuckDB queries Parquet directly; DATA-04 requires every derived table
     to state input content hashes and the config hash, with a printable lineage chain.
   - What's unclear: CONTEXT.md doesn't specify the storage mechanism for this metadata — Parquet
     custom key-value metadata (readable via `pyarrow.parquet.read_metadata`) versus a queryable
     DuckDB `lineage` table (readable via SQL, joinable, printable via a simple query) are both
     viable.
   - Recommendation: A DuckDB-queryable `lineage` table (columns: `table_name`, `input_hashes`,
     `config_hash`, `produced_at_tick` or similar non-wallclock marker, `producer_stage`) is more
     consistent with "queryable" language used elsewhere in CONTEXT.md (D-20's rejects table is
     explicitly "queryable") and easier for DATA-04's "printable lineage chain" requirement — a
     `SELECT` is simpler to demo than parsing Parquet footer metadata. Parquet file-level metadata
     can additionally carry a redundant copy for portability, but the table should be the
     source of truth the CLI/report prints from.

3. **Whether Phase 1 needs `pandera` as a hard dependency or whether Pydantic model validators
   alone suffice for DATA-03's semantic checks**
   - What we know: Pydantic handles per-row/per-event validation naturally (DATA-02); Pandera adds
     value for whole-dataframe checks (monotonic timestamps *within a session*, referential
     integrity to catalog) that are awkward as single-row Pydantic validators.
   - What's unclear: Whether the specific DATA-03 checks are simple enough to express as a handful
     of DuckDB SQL assertions instead, avoiding the extra dependency.
   - Recommendation: Include Pandera in Phase 1 (low cost, clean fit for the "monotonic within a
     session" and "referential integrity to catalog" checks specifically) but this is not a hard
     blocker — the plan could substitute DuckDB SQL assertions if the planner prefers fewer
     dependencies. Documented in Alternatives Considered.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | D-15 environment/lockfile | ✓ | 0.11.29 | — |
| Python 3.12 | D-15 | ✓ | 3.12.10 (also 3.14.6 present as `python3`) | `uv` will pin/install 3.12 into the project venv regardless of system Python; ensure `.python-version` or `pyproject.toml` `requires-python` pins 3.12 explicitly so `uv` doesn't pick the 3.14 interpreter |
| `just` | D-14 real operational interface | ✗ | — | Not installed on this dev machine. Install via `winget install Casey.Just` or `uv tool install rust-just` (uv can install standalone tools) before Phase 1 execution; this blocks nothing about *planning* but must be installed before `just reproduce` can be exercised locally. GNU `make` **is** available, so the 3-line `Makefile` forward (D-14) is exercisable once `just` is installed. |
| `make` | D-14 thin forwarding shim | ✓ | GNU Make 4.4.1 | — |
| `git` | version control, `git mv` for D-17 | ✓ | 2.55.0 | — |
| `dvc` | ENG-09/D-09 artifact versioning | ✗ (not globally installed) | — | Installed as a project dependency via `uv add --dev dvc`, not required as a global tool — no fallback needed |
| `mlflow` | ENG-09/D-09 experiment tracking | ✗ (not globally installed) | — | Same as `dvc` — project dependency, not a global tool requirement |
| `duckdb` (CLI) | Query engine | ✗ (Python client `duckdb` package is what's used, not the standalone CLI) | — | Not needed as a standalone binary; the Python `duckdb` package (installed via `uv add duckdb`) is sufficient for everything Phase 1 does |
| Node.js | Present but not part of the Python stack | ✓ | v24.18.0 | Irrelevant to Phase 1 (no JS in this project) |
| GitHub Actions `ubuntu-latest` runner | D-16 CI | N/A (cloud, not local) | — | Not locally verifiable; standard runner image includes recent Python and standard build tools — `uv`, `dvc`, `mlflow` etc. all install cleanly via `uv sync` on Linux |

**Missing dependencies with no fallback:** none — `just` has a clear, low-friction install path and
does not block planning.

**Missing dependencies with fallback:** `just` (install before first local `just reproduce` run;
CI doesn't need this fixed since D-16's CI still ultimately needs `just` installed on the runner too
— add a `just`-install step to the GitHub Actions workflow, e.g. `extractions/setup-just` action or
equivalent).

## Validation Architecture

`workflow.nyquist_validation` is not present in `.planning/config.json` (the file does not exist in
this repository), so per the default rule this section is included — validation is treated as
enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (+ `pytest-cov` for coverage, `hypothesis` for property-based tests where useful) — none yet installed; Wave 0 installs and configures |
| Config file | none yet — Wave 0 creates `pyproject.toml` `[tool.pytest.ini_options]` (or `pytest.ini`) |
| Quick run command | `uv run pytest tests/unit tests/leakage -x -q` (fast subset, no full `demo`-profile simulation run) |
| Full suite command | `uv run pytest -x` plus `just reproduce --profile ci` (miniature end-to-end + golden-file comparison) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENG-04 | Two seeded runs of `just reproduce --profile ci` produce byte-identical Parquet outputs | golden-file | `pytest tests/golden/test_reproducibility.py -x` | ❌ Wave 0 |
| DATA-04 | Every derived table's lineage row states correct input content hashes + config hash | integration | `pytest tests/integration/test_lineage.py -x` | ❌ Wave 0 |
| DATA-02 / DATA-03 | Malformed/semantically-invalid events land in rejects table with a reason, never silently dropped or accepted | unit + integration | `pytest tests/unit/test_ingest_quarantine.py tests/integration/test_reject_threshold.py -x` | ❌ Wave 0 |
| FEAT-02 | A feature row `as_of` a past timestamp contains no information created after that timestamp | leakage | `pytest tests/leakage/test_no_lookahead.py -x` | ❌ Wave 0 |
| SIM-02 | `models/`, `decisions/`, `policies/`, `features/` never import `simulator` | static/CI | `uv run lint-imports` (wired as a CI job step, and optionally a `pytest` wrapper asserting the contract names appear in output) | ❌ Wave 0 |
| SIM-03 | Every generative assumption documented | manual/doc-check | none automatable directly; a lightweight test can assert `docs/SIMULATOR_ASSUMPTIONS.md` exists and is non-empty as a floor check | ❌ Wave 0 (floor check only) |
| SIM-05 (D-05) | UC1/UC2 scenario customers genuinely occur in the generated population at default scale | integration/statistical | `pytest tests/integration/test_uc_scenarios_occur.py -x` — assert nonzero count of customers matching each UC's stated profile at the `default` (50k) profile | ❌ Wave 0 |
| ENG-03 | Business numbers (simulator params, thresholds) are not hardcoded — changing YAML changes behavior without a code edit | integration | `pytest tests/integration/test_config_drives_behavior.py -x` — mutate a config value, assert output changes | ❌ Wave 0 |
| DOC-01 | OD-1..OD-10 ratified as `docs/adr/001-*.md`…`010-*.md` with genuine Context/Decision/Consequences text | manual/doc-check | floor check: assert all ten files exist and are non-trivial in length | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command (`tests/unit`, `tests/leakage`) — fast, no full simulation.
- **Per wave merge:** full suite command, including the golden-file byte-identical comparison and a
  `ci`-profile `just reproduce` run.
- **Phase gate:** Full suite green, plus a manual review confirming `SIMULATOR_ASSUMPTIONS.md` and
  all ten ADRs are substantively written (not template stubs) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/golden/test_reproducibility.py` — covers ENG-04 (byte-identical reruns)
- [ ] `tests/integration/test_lineage.py` — covers DATA-04
- [ ] `tests/unit/test_ingest_quarantine.py` + `tests/integration/test_reject_threshold.py` — covers
      DATA-02, DATA-03, D-20, D-21
- [ ] `tests/leakage/test_no_lookahead.py` — covers FEAT-02
- [ ] `tests/integration/test_uc_scenarios_occur.py` — covers D-05
- [ ] `tests/integration/test_config_drives_behavior.py` — covers ENG-03
- [ ] `tests/conftest.py` — shared fixtures: a small (~50-100 customer) fast-running simulator
      profile distinct from `demo`/`ci` for unit-level tests that shouldn't pay the full `ci`
      profile's cost
- [ ] Framework install: `uv add --dev pytest pytest-cov hypothesis`
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` / `[tool.coverage.run]` configuration

## Security Domain

Config key `security_enforcement` is absent from `.planning/config.json` (file does not exist), so
per the default rule this section is included (absent = enabled). Phase 1 has a narrow attack
surface — no network-facing API, no auth, no external data ingestion beyond the (deferred to v2)
public-dataset adapter — so most ASVS categories are not yet applicable, but the categories that do
apply matter for a portfolio project's credibility.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No API/auth surface exists yet (Phase 2) |
| V3 Session Management | No | Not applicable — Phase 1 has no web sessions; "session" here means simulated shopping sessions, an unrelated domain concept |
| V4 Access Control | No | No multi-user/API surface yet |
| V5 Input Validation | Yes | Pydantic contract validation on every event field (DATA-02); Pandera semantic checks (DATA-03); reject-then-quarantine rather than coerce-silently, which is itself the correct input-validation posture (never trust generated/external data implicitly, even from your own simulator) |
| V6 Cryptography | No | No secrets, no encryption-at-rest requirement for local Parquet/DuckDB files in this phase — synthetic, non-PII data only (project-wide non-goal #9: "real personal data") |
| V12 File and Resources | Yes (lightweight) | All file I/O (Parquet reads/writes, YAML config loads) stays within the repository's own `data/`/`config/` directories; no path is ever constructed from unsanitized external input in Phase 1 (no adapters land until v2) |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Malformed/malicious event payload accepted and silently coerced, corrupting downstream aggregates | Tampering | Pydantic strict validation (reject unknown/wrong-typed fields rather than coercing), routed to quarantine (D-20) rather than accepted |
| Config file with an unexpected/malicious YAML structure crashing or silently misconfiguring a run | Tampering / Denial of Service | `yaml.safe_load` (never `yaml.load` with the default full loader), Pydantic validation of the merged result rejecting unknown fields (`model_config = ConfigDict(extra="forbid")`) so a typo'd or malicious config key fails loudly instead of being silently ignored |
| Supply-chain risk from a typosquatted or compromised PyPI package (directly relevant given the Package Legitimacy Audit findings above) | Tampering | `uv.lock` pins exact hashes for every dependency (`uv` lockfiles are hash-pinned by default); the `checkpoint:human-verify` flagged for `dvc` in the Package Legitimacy Audit is exactly this mitigation applied concretely |
| Content-hash lineage forged or stale, giving false confidence in reproducibility claims | Repudiation | Content hashes computed by the storage layer itself at write time (not trusted from caller input), stored alongside the data they describe, and re-verifiable by recomputing the hash of the actual Parquet file bytes on demand |

## Sources

### Primary (HIGH confidence)
- `pip index versions <package>` (npm/PyPI-equivalent registry query) — verified exact current
  versions for pydantic, pyarrow, duckdb, import-linter, dvc, mlflow, pandera, ruff, numpy, pandas
  on 2026-07-25, cross-referenced against each project's official docs domain.
- Local environment probes (`uv --version`, `git --version`, `command -v just/make/dvc/mlflow`) —
  confirmed actual tool availability on the development machine.
- `gsd-tools query package-legitimacy check` — confirmed package existence and surfaced the DVC
  repo-URL discrepancy documented in the Package Legitimacy Audit.

### Secondary (MEDIUM confidence — CITED, WebSearch results pointing to official documentation)
- NumPy official docs, `numpy.org/doc/stable/reference/random/parallel.html` and
  `.../generator.html` — `SeedSequence.spawn()`, `default_rng()` per-entity pattern.
- Apache Arrow / PyArrow official docs, `arrow.apache.org/docs/python/...` — Parquet writer options,
  `created_by` metadata field.
- DuckDB official docs, `duckdb.org/docs/current/guides/sql_features/asof_join` and
  `duckdb.org/docs/stable/operations_manual/non-deterministic_behavior` — ASOF JOIN syntax,
  documented multi-threaded aggregation nondeterminism for functions like `stddev`/`corr`.
- import-linter official docs, `import-linter.readthedocs.io/en/stable/get_started/configure/` —
  forbidden contract TOML configuration.
- Pydantic official docs, `docs.pydantic.dev/latest/concepts/config/` — model config merge/
  inheritance semantics.
- DVC official docs, `doc.dvc.org/user-guide/project-structure/dvcyaml-files` and
  `.../pipelines/running-pipelines` — `dvc.yaml` stage/dependency/content-hash mechanics.
- Pandera official docs, `pandera.readthedocs.io/en/stable/lazy_validation.html` and
  `.../drop_invalid_rows.html` — lazy validation, quarantine pattern.
- MLflow official docs, `mlflow.org/docs/latest/self-hosting/architecture/backend-store/` — file
  store vs. database-backed store guidance, "maintenance mode" status of the file store.
- Astral `uv` official docs, `docs.astral.sh/uv/concepts/projects/layout/` and
  `.../guides/projects/` — `src/` layout, `uv.lock` reproducibility guarantees.
- CPython hash-randomization discussion (`python/cpython` issue tracker,
  `github.com/python/cpython/issues/99540`) — `PYTHONHASHSEED` and set/dict iteration-order
  nondeterminism.

### Tertiary (LOW confidence — WebSearch only, community/research sources, marked for validation)
- RetailSynth (arXiv 2312.14095) and related agent-based retail-simulation papers — general design
  pattern evidence for latent-trait-driven customer simulation; not a specific API or library to
  adopt, informs Simulator Realism Mechanics design reasoning only (see Assumption A4).
- Feature-store point-in-time-correctness blog posts (Databricks, Feast, Tecton docs surfaced via
  WebSearch) — corroborate the ASOF-join/leakage-test pattern as industry-standard, used to support
  the leakage test code example (semi-authoritative — these are vendor docs, treated as CITED where
  cross-referenced against DuckDB's own docs, LOW/tertiary where only the vendor blog was checked).

## Metadata

**Confidence breakdown:**
- Standard stack (toolchain versions, package legitimacy): HIGH — every version independently
  verified against PyPI on research date; package identity confirmed via official docs cross-
  reference, with one flagged discrepancy (DVC repo URL) requiring a planner checkpoint.
- Architecture patterns (event schema, storage layer, import contracts, config merge, lineage):
  MEDIUM-HIGH — mechanics (ASOF JOIN, import-linter contracts, Pydantic config merge) are CITED
  against official docs; the specific application to this project's ten-package layout is this
  research's own synthesis, consistent with CONTEXT.md's locked decisions.
- Determinism pitfalls (RNG, hashing, Parquet writer, DuckDB threading): HIGH — each pitfall is
  independently documented by the relevant project's own official docs or the CPython issue
  tracker, not inferred.
- Simulator realism mechanics (latent trait distributions, exact response function forms): MEDIUM-
  LOW — general pattern well-supported by research literature (RetailSynth, agent-based retail
  simulation), but exact parameterization is explicitly left to planner/implementer discretion by
  CONTEXT.md, not a researched-and-locked recommendation.

**Research date:** 2026-07-25
**Valid until:** 2026-08-24 (30 days — toolchain versions and Python ecosystem mechanics are stable
enough at this cadence; re-verify package versions at plan/execution time regardless, since `uv add`
will pull whatever is current then)
