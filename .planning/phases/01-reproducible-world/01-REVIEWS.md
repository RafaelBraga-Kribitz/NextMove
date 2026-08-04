---
phase: 1
reviewers: [gemini]
reviewers_requested: [codex]
reviewers_failed:
  codex:
    reason: "usage limit exhausted — codex-cli 0.145.0 returned 'You've hit your usage limit … try again at Aug 17th, 2026 11:16 PM' (exit 1, empty output). Not a timeout: the error was captured on stderr after ~2 min."
    substituted_with: gemini
reviewed_at: 2026-08-04T11:53:23Z
review_cycle: 1
plans_reviewed:
  - 01-01-PLAN.md
  - 01-02-PLAN.md
  - 01-03-PLAN.md
  - 01-04-PLAN.md
  - 01-05-PLAN.md
  - 01-06-PLAN.md
  - 01-07-PLAN.md
  - 01-08-PLAN.md
  - 01-09-PLAN.md
  - 01-10-PLAN.md
  - 01-11-PLAN.md
---

# Cross-AI Plan Review — Phase 1: Reproducible World

> **Reviewer availability note.** `/gsd-review --phase 1 --codex` requested Codex. `codex exec`
> failed with a hard account usage limit (quota resets 2026-08-17), producing no review. Per the
> workflow's "log the error and continue" rule, the review was carried out by the other detected
> independent CLI, **Gemini CLI 0.52.0**. The `claude` CLI was skipped for reviewer independence —
> this session runs inside Claude Code (`CLAUDE_CODE_ENTRYPOINT=claude-vscode`). Gemini was run in
> two passes: a broad pass over the full phase artifact set, and a focused adversarial pass over the
> storage / lineage / pipeline contract surface. Both passes are recorded verbatim below.

## Gemini Review (pass 1 — broad)

### 1. Summary
The implementation plans for Phase 1 are exceptionally well-structured, prioritizing engineering discipline and "reproducibility as a first-class feature" over mere simulation logic. The strategy of building a "Wave 0" infrastructure—specifically the determinism, storage, and boundary-enforcement harnesses—before the simulator's realism logic is authored is a high-signal engineering choice that ensures every subsequent change is validated against the project's core claims. The plans strictly adhere to the modular monolith constraints (ENG-01) and simulator honesty rules (SIM-02, SIM-03), while proactively addressing subtle Python-specific nondeterminism risks (RNG streams, hash seeds, DuckDB threading). The dependency graph across the 11 plans is sound, and the use of a "tiny" profile for fast unit/integration tests prevents the suite from becoming a bottleneck.

### 2. Strengths
*   **Determinism Deep-Dive:** The plans address silent nondeterminism sources documented in `RESEARCH.md` (e.g., Python hash randomization, multi-threaded float aggregation in DuckDB) at the storage layer (`01-06-PLAN.md:120`) rather than delegating them to individual producers.
*   **Boundary Enforcement:** The use of `import-linter` with proven "non-vacuous" tests (`01-04-PLAN.md:106`) ensures the simulator/model isolation (SIM-02) is a hard gate, not a pinky-promise.
*   **Point-in-Time Correctness:** Leveraging DuckDB’s native `ASOF JOIN` (`01-10-PLAN.md:125`) for feature computation is a standard-aligned choice that achieves FEAT-02's requirements with minimal custom code.
*   **Config Discipline:** The layered config model with `extra="forbid"` (`01-03-PLAN.md:120`) and canonical hashing ensures that every "business number" is auditable and that the config hash is a reliable proxy for the run state.
*   **Idempotent Ingest:** The decision to implement idempotent append for the canonical event log (`01-09-PLAN.md:112`) allows for pipeline re-runs without data corruption, satisfying the "one command on a clean clone" goal.

### 3. Concerns
*   **RAM/Memory Pressure on Laptop:** `01-08-PLAN.md:196` states that `run_simulation` "accumulates events, and writes" raw tables at the end. At the default scale of 50k customers over 18 months, the event count could easily reach tens of millions. Storing the entire event set as Pydantic objects or in-memory lists before the final write may exceed the memory capacity of a typical laptop (violating ENG-08). **(Severity: MEDIUM)**
*   **import-linter Path Sensitivity:** If `src/` is not in the `PYTHONPATH` during local `just lint` runs, `import-linter` might fail to resolve the `nextmove` root package despite the packages having `__init__.py`. **(Severity: LOW)**
*   **Pandera/Pydantic Performance:** Performing both per-row Pydantic validation and then a whole-dataframe Pandera sweep in the ingest pipeline (`01-09-PLAN.md:144`) is robust but potentially slow for the full 50k customer history. **(Severity: LOW)**

### 4. Suggestions
*   **Incremental Write in Simulator:** Modify `run_simulation` in `01-08-PLAN.md` to flush events to a temporary DuckDB table or a Parquet part-file periodically (e.g., every simulated month) instead of accumulating them in a Python list until the end of the 18-month horizon.
*   **DVC `outs` Granularity:** In `01-11-PLAN.md:95`, ensure the `simulate` stage outputs are defined at the directory level (`data/raw/`) as planned, but consider using `dvc commit` or specific `just` recipes to help reviewers inspect individual Parquet files without re-running the entire 50k customer simulation.
*   **Type Checking Step:** While `ruff` is used for linting, adding a `mypy` or `pyright` step to the CI workflow (`01-04-PLAN.md`) would provide stronger static guarantees for the Pydantic contracts and plugin registries (ENG-02).

### 5. Risk Assessment
**Overall Risk: LOW**

The phase is well-derisked. The primary technical risk—determinism—is mitigated by the storage-layer controls and the golden-file comparison tests. The architectural risk—simulator leakage—is mitigated by both the `import-linter` contract and the data-path isolation test in `01-10-PLAN.md`. The most significant residual risk is the execution time and memory footprint of the full 50k-customer simulation on consumer-grade hardware, but the presence of the `demo` and `tiny` profiles allows for continuous development and verification even if the "production" run is resource-intensive. The dependency order is strictly logical, and the plans establish a high-quality "engineering floor" that later phases can safely build upon.

---

## Gemini Review (pass 2 — focused adversarial, storage/lineage/pipeline contract surface)

This adversarial review identifies several mechanical defects in the storage and pipeline contracts across Phase 1.

### 1. Storage Write + Lineage Call Graph (Infinite Recursion)
*   **Severity:** **HIGH**
*   **Citations:** Plan 06, Line 160; Plan 06, Line 232.
*   **Failure Mechanism:** `repository.write_table` is designed to call `lineage.record_lineage` after every successful write (Line 160). However, `lineage.record_lineage` persists the updated lineage table by calling `repository.write_table` (Line 232). When the `lineage` table itself is being written, this creates an infinite recursion: `write_table("lineage")` → `record_lineage()` → `write_table("lineage")` → …, eventually crashing the process with a `RecursionError`.
*   **Smallest Fix:** Add an optional boolean flag `record_lineage=True` to `write_table`. `record_lineage` must set this to `False` when calling `write_table` to persist the lineage table.

### 2. Module Import Direction (Circular Dependency)
*   **Severity:** **HIGH**
*   **Citations:** Plan 06, Line 50-51; Plan 06, Line 189; Plan 06, Line 232.
*   **Failure Mechanism:** `src/nextmove/storage/repository.py` must import `record_lineage` from `lineage.py` to fulfill its requirement to record lineage on every write. Conversely, `src/nextmove/storage/lineage.py` must import `write_table` from `repository.py` to fulfill its requirement to persist the lineage table atomically. This results in a circular import that will prevent the package from loading.
*   **Smallest Fix:** Use a late import inside the `write_table` function body or move the lineage recording logic to a shared internal helper module that does not depend on the public repository API.

### 3. DVC Stage Outputs and Overlapping Writes
*   **Severity:** **HIGH**
*   **Citations:** Plan 11, Lines 142-147; Plan 06, Lines 160, 229; Plan 09, Line 80.
*   **Failure Mechanism:**
    *   The `simulate` stage (Plan 11) declares `data/raw/` as its output. However, its code (via `write_table` → `record_lineage`) writes the `lineage` table into the `canonical` zone (Plan 06), which resolves to `data/canonical/lineage.parquet`.
    *   The `ingest` stage (Plan 11) declares the entire `data/canonical/` directory as its output.
    *   **Overlap:** `simulate` writes into a directory owned by `ingest`. DVC forbids multiple stages from modifying the same output. If `simulate` runs, it creates `data/canonical/lineage.parquet` as an undeclared side effect. When `ingest` runs, DVC may clean up the "untracked" file or find its output directory already "dirty," breaking the pipeline's integrity.
*   **Smallest Fix:** Move the `lineage` table to its own zone/directory (e.g., `data/lineage/`) and declare it as an `out` in every stage that modifies it, or use DVC's `append` functionality (though the latter is complex; the simplest fix is for each stage to produce a *separate* lineage fragment file).

### 4. DVC Idempotency and `dvc.lock` Stability
*   **Severity:** **HIGH**
*   **Citations:** Plan 11, Line 29; Plan 11, Line 176.
*   **Failure Mechanism:** The criterion "Re-running with nothing changed … leaves dvc.lock byte-identical" (Line 29) cannot hold. Because `simulate` and `features` both write to `data/canonical/lineage.parquet` (which is part of `ingest`'s declared output directory), any run of `simulate` will change the content hash of `ingest`'s outputs. This causes DVC to detect `ingest` as "changed" even if raw inputs are identical, triggering unnecessary re-runs and ensuring `dvc.lock` is frequently updated with new hashes for the same logical state.
*   **Smallest Fix:** Remove `lineage.parquet` from the `data/canonical/` directory. Store lineage in a way that each stage owns a distinct, immutable file.

### 5. Inconsistent `record_lineage` Signature
*   **Severity:** **MEDIUM** *(orchestrator escalated to HIGH — see Consensus Summary)*
*   **Citations:** Plan 06, Line 160; Plan 06, Line 220; Plan 06, Line 229.
*   **Failure Mechanism:** There is a mechanical contradiction in Plan 06 regarding who computes the content hash.
    *   Line 160 says `write_table` calls `record_lineage` **with the hash**.
    *   Line 220-221 says `record_lineage` **must never accept a hash** as a caller-supplied argument to prevent forgery.
    *   Line 229 says `record_lineage` accepts a `LineageRecord`, which Line 222 says **contains the hash**.
    *   If `write_table` (the caller) computes the hash, it violates the "unforgeable" requirement in Line 220. If `record_lineage` is supposed to compute it, it needs the `Path`, which is missing from its described signature.
*   **Smallest Fix:** Update `record_lineage` to accept the `Path` of the written table and compute the content hash internally using `content_hash(path)`. `write_table` should pass the path, not the hash.

### Verification of Stated "FINE" Mechanisms
*   **Import of `sort_events`**: **FINE**. Plan 05 declares and re-exports it; Plan 08/09/10 correctly reference its availability in `ingest.contracts` or the package root.
*   **`config_hash` Lineage**: **FINE**. Plan 06 correctly traces the config hash from the `ResolvedConfig` (Plan 03) into the `LineageRecord` and Parquet metadata.
*   **`CANONICAL_SORT_KEY` Consistency**: **FINE**. Plan 05 defines the tuple, Plan 06 uses it for Arrow table sorting, and Plan 09 uses it for Ingest ordering. The tiebreak mechanism is stable.

---

## Codex Review

**NOT RUN — reviewer unavailable.**

```
ERROR: You've hit your usage limit. To continue using Codex and get access to
GPT-5.3-Codex, start a free trial of Plus today, or try again at Aug 17th, 2026 11:16 PM.
```

`codex exec --ephemeral --dangerously-bypass-hook-trust -C <repo> --skip-git-repo-check` exited 1
after ~2 minutes with the above on stderr and no output file. This is an account quota block, not a
timeout or a sandbox failure — the error text was captured, so the lane is diagnosable rather than
silently dropped. Re-run `/gsd-review --phase 1 --codex` after 2026-08-17 if a second independent
model's verdict is wanted before execution.

---

## Consensus Summary

Only one external reviewer lane was available (Gemini, two passes), so "consensus" here means
agreement between the reviewer and the orchestrator's own source-grounded verification pass rather
than agreement between two independent models. Every HIGH below was **independently reached by the
orchestrator by reading the plan files before the focused reviewer pass ran**, and then confirmed by
the reviewer — the concurrence is genuine, not the reviewer's claim taken at face value.

The broad pass rated overall risk LOW and found no HIGH. That verdict does not survive the focused
pass: the storage layer that plan 01-06 calls "the single place where determinism is either won or
lost" (`01-06-PLAN.md:66-67`) contains a self-referential write path that cannot execute as written,
and its consequences propagate into the phase's headline reproducibility criterion. The broad pass's
LOW rating should be read as "the *architecture* is low-risk", not "the plans are ready to execute".

### Agreed Strengths

*(Reviewer-stated, orchestrator-verified against the plan files.)*

- **Determinism is centralized, not distributed.** Sorted-before-write with a mandatory unique
  tiebreak, `PRAGMA threads=1`, atomic `os.replace`, pinned Parquet writer options, and a hard ban on
  wall-clock metadata all live in one module (`01-06-PLAN.md:147-161`), with `grep`-based acceptance
  criteria (`01-06-PLAN.md:172-177`) that make each one mechanically checkable.
- **The import boundary is proven non-vacuous.** `01-04-PLAN.md` pairs the real contract with a
  deliberately-violating fixture package (`tests/fixtures/contract_probe/`) plus an assertion that
  the contract report names all four forbidden source packages — closing the "a contract that checks
  nothing still exits 0" failure mode explicitly (`01-04-PLAN.md:53`).
- **Point-in-time correctness is enforced on two independent axes.** The import-linter contract bans
  the code path (`01-04-PLAN.md:104-107`) and a separate data-path test bans reading the
  `ground_truth` zone (`01-10-PLAN.md` must_haves; `01-08-PLAN.md:333-336`) — so SIM-02 does not rest
  on the import ban alone.
- **Config discipline makes the determinism claim auditable.** Seeds are config values inside the
  hashed surface rather than CLI flags (D-25, `01-03-PLAN.md`), so a third party can reproduce a run
  from the config hash alone.
- **The wave graph is sound.** Verified independently: every `depends_on` entry resolves to a plan in
  a strictly earlier wave, and no two plans in the same wave modify the same file.

### Agreed Concerns

**HIGH-1 — `write_table` ↔ `record_lineage` infinite recursion.** `01-06-PLAN.md:160` has
`write_table` call `record_lineage` after every successful write; `01-06-PLAN.md:229-232` has
`record_lineage` persist the lineage table "through the repository's sorted atomic write". Writing
the `lineage` table therefore re-enters `record_lineage` unboundedly. There is no carve-out anywhere
in the plan — `write_table`'s signature (`01-06-PLAN.md:147`) has no skip parameter, and no
acceptance criterion exercises writing the lineage table itself. Plan 01-06 is wave 3 and plans
01-08, 01-09, 01-10 and 01-11 all depend on it, so this blocks five downstream plans.
*Fix:* add a `record_lineage: bool = True` parameter to `write_table` and have `record_lineage` pass
`False`; add an acceptance criterion that writing the lineage table terminates.

**HIGH-2 — circular import between `repository.py` and `lineage.py`.** The same two-way call
relationship (`01-06-PLAN.md:50-51`, `:160`, `:191`, `:232`) means each module must import the other
at module scope as described. Distinct failure from HIGH-1 (`ImportError` at package load vs
`RecursionError` at runtime) and needs a distinct fix.
*Fix:* state explicitly in the plan that `write_table` imports `record_lineage` lazily inside the
function body, or factor the atomic-write primitive into a private module both import.

**HIGH-3 — DVC stage outputs overlap; `data/canonical/` is written by all three stages.**
`01-06-PLAN.md:129-131` and `:340` place the `lineage` table in the `canonical` zone. `01-11-PLAN.md:141-147`
declares `simulate → outs data/raw/, data/ground_truth/`, `ingest → outs data/canonical/`,
`features → outs data/features/` with `data/canonical/` as a *dep*. Because every `write_table` call
records lineage, the `simulate` stage's six writes (`01-08-PLAN.md:326-331`) and the `features`
stage's write (`01-10-PLAN.md:227`) both mutate `data/canonical/lineage.parquet` — a directory owned
by `ingest`. The `features` stage therefore writes into its own declared dependency. DVC rejects
overlapping stage outputs, and `ingest` re-materializing its output directory would destroy the
lineage rows the `simulate` stage recorded.
*Consequence (reviewer's item 4):* the acceptance criteria at `01-11-PLAN.md:29` and `:176`
("re-running … leaves `dvc.lock` byte-identical") are unsatisfiable while this holds, which means
**phase success criterion 1 cannot be demonstrated**. Counted as one defect with HIGH-3, since a
single fix closes both.
*Fix:* give lineage its own zone (`data/lineage/`) written as a per-stage fragment file, and declare
each fragment as an `out` of the stage that produces it.

**HIGH-4 — the anti-forgery lineage contract is self-contradictory and its acceptance criterion is
unsatisfiable.** `01-06-PLAN.md:160` has `write_table` pass "the hash of the bytes actually on disk"
into `record_lineage`; `01-06-PLAN.md:217-221` states `record_lineage` "must never accept a hash as a
caller-supplied argument"; `01-06-PLAN.md:222-229` gives `record_lineage` a single `LineageRecord`
parameter whose fields include `content_hash: str`. The acceptance criterion at `01-06-PLAN.md:258`
("`record_lineage` has no parameter that accepts a precomputed content hash for the described table")
cannot be satisfied by the design the same plan specifies. This is not cosmetic: threat mitigation
T-01-14 (`01-06-PLAN.md:359`, Repudiation, rated high) rests entirely on this property, and DATA-04's
value is that lineage is checkable rather than claimed.
*Orchestrator escalated the reviewer's MEDIUM to HIGH* because it makes a stated acceptance gate
impossible to pass and voids a high-rated threat mitigation, not merely because the prose is unclear.
*Fix:* change `record_lineage` to take `(path: Path, record: LineageRecordDraft)` and compute
`content_hash(path)` internally; drop `content_hash` from the caller-supplied model.

**MEDIUM-1 — full-scale run has no memory or runtime budget.** `01-08-PLAN.md:322` has
`run_simulation` "accumulate[] events" across the whole horizon before writing. At the configured
default of `n_customers: 50000` and `horizon_days: 548` (`01-03-PLAN.md:295`), holding every event as
a Pydantic object until the end is plausibly tens of millions of objects — a direct risk to ENG-08's
laptop guarantee. No plan states a memory ceiling, a flush strategy, or a wall-clock budget for the
`default` profile; every test path deliberately uses `tiny`/`demo` (`01-07-PLAN.md:298`), so nothing
in the suite would catch this. The reviewer's LOW note on Pydantic-plus-Pandera double validation
(`01-09-PLAN.md`) is the same root cause and is closed by the same fix.
*Fix:* add a periodic flush (part-file or DuckDB spill) to `01-08-PLAN.md` Task 3, plus an acceptance
criterion stating peak RSS and wall-clock bounds for the `default` profile.

**MEDIUM-2 — four plans modify `justfile` without declaring it.** `01-04`, `01-08` (`:344`), `01-09`
and `01-10` each add a `just` recipe in their action prose, but none lists `justfile` in
`files_modified`; only `01-01` and `01-11` declare it. Related: `01-11-PLAN.md:119-121` tells the
executor that the `simulate`, `ingest` and `features` recipes already exist from plan 01-01, but
`01-01-PLAN.md:190-194` creates only `setup`, `fmt`, `lint`, `test` and a placeholder `reproduce`.
Undeclared writes break commit scoping and per-plan verification.
*Fix:* add `justfile` to `files_modified` in 01-04, 01-08, 01-09, 01-10 and correct the `read_first`
provenance claim in 01-11.

**LOW-1 — `sort_events` is missing from plan 01-05's declared exports.** It is specified in the
action prose (`01-05-PLAN.md:156`, `:161`, `:306`) and consumed by `01-08-PLAN.md:213` and
`01-09-PLAN.md:111`, but the artifact `exports:` array at `01-05-PLAN.md:29` omits it. The reviewer
marked this FINE on the strength of the prose; the orchestrator confirms the prose is correct and
only the machine-readable `exports` list is incomplete — which matters because that list is what
artifact verification checks.
*Fix:* add `"sort_events"` to the `exports` array for `src/nextmove/ingest/contracts.py`.

**LOW-2 — no static type checking, and no stated decision not to have it.** No plan mentions `mypy`
or `pyright`. Given how much of this phase's safety rests on Pydantic contracts and plugin
registries, the absence is defensible for Phase 1 but is currently silent rather than decided.
*Fix:* either add a type-check step to `01-04-PLAN.md`'s CI workflow, or record an explicit deferral
to Phase 2 (ENG-02) in that plan so the omission is a decision rather than an oversight.

### Divergent Views

- **Overall risk rating.** Pass 1 concluded **LOW** ("the phase is well-derisked"); pass 2 found four
  HIGH-severity mechanical defects in the same plan set. The orchestrator sides with pass 2 on
  execution-readiness and with pass 1 on architecture: the design is sound, but plan 01-06 as written
  cannot be implemented literally, and the defect propagates into phase success criterion 1. Treat
  the phase as **MEDIUM risk, not execution-ready**, until 01-06 and 01-11 are amended.
- **`sort_events` (LOW-1).** Pass 2 explicitly marked this FINE; orchestrator verification found the
  frontmatter `exports` array genuinely omits it. Divergence resolved in favour of the narrower
  reading — the prose is fine, the declared contract is not.
- **`record_lineage` severity (HIGH-4).** Reviewer said MEDIUM, orchestrator says HIGH. Recorded as a
  disagreement rather than silently overwritten.

---

## Verification coverage

How each finding above was grounded, so a reader can weigh it:

| Finding | Reviewer pass | Orchestrator independent check | Grounding |
|---|---|---|---|
| HIGH-1 recursion | pass 2 | Yes — found before pass 2 ran, by tracing `01-06-PLAN.md:160` → `:232` and grepping for any carve-out (`recurs\|circular\|skip_lineage\|excluding lineage`) — none exists | Plan text, direct read |
| HIGH-2 circular import | pass 2 | Yes — same trace; `write_table` signature at `:147` confirmed to have no lazy-import note | Plan text, direct read |
| HIGH-3 DVC overlap | pass 2 | Yes — found before pass 2 ran, by cross-reading zone assignment (`01-06-PLAN.md:129-131`, `:340`) against stage `outs` (`01-11-PLAN.md:141-147`) and simulate's write sites (`01-08-PLAN.md:326-331`) | Plan text, cross-plan |
| HIGH-4 hash forgery contradiction | pass 2 (as MEDIUM) | Yes — acceptance criterion `01-06-PLAN.md:258` read against `LineageRecord` fields at `:222` and threat row T-01-14 at `:359` | Plan text, direct read |
| MEDIUM-1 memory budget | pass 1 | Yes — `01-08-PLAN.md:322` confirmed; scale confirmed at `01-03-PLAN.md:295`; grepped 01-08 for `stream\|chunk\|flush\|batch` — no flush strategy present | Plan text, grep |
| MEDIUM-2 undeclared justfile edits | neither | Orchestrator only — scripted comparison of each plan's `files_modified` block against body prose adding `just` recipes | Scripted cross-check |
| LOW-1 `sort_events` export | pass 2 marked FINE | Orchestrator contradicted — `exports` array at `01-05-PLAN.md:29` read directly | Plan text, direct read |
| LOW-2 no type checking | pass 1 (suggestion) | Yes — grepped all 11 plans for `mypy\|pyright\|type.check`; no hit outside an unrelated note | Grep across phase |
| Wave graph soundness | pass 1 (asserted) | Yes — scripted extraction of `wave:`/`depends_on:` for all 11 plans, plus intra-wave `files_modified` collision check; no violation found | Scripted cross-check |

**Repo-access caveat.** This phase is greenfield: the repository contains `.planning/` and ten root
planning documents but no `src/`, `pyproject.toml`, `justfile`, `docs/`, or CI workflow yet. No
finding above asserts anything about implementation code, because none exists. All grounding is
against plan text and cross-plan contracts, which is the only checkable surface at this stage —
verified by direct read at the cited line numbers rather than restated from the plans' own claims.

**Reviewer-count caveat.** One external model, two passes. Cross-model adversarial coverage is
weaker than a normal `/gsd-review` run. Re-running with Codex after its quota resets (2026-08-17)
would materially strengthen confidence, particularly on the plans the focused pass did not cover
(01-01, 01-02, 01-03, 01-04, 01-07).
