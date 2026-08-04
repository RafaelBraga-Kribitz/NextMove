---
phase: 1
reviewers: [gemini]
reviewers_requested: [codex]
reviewers_failed:
  codex:
    reason: "usage limit exhausted — codex-cli 0.145.0 returned 'You've hit your usage limit … try again at Aug 17th, 2026 11:16 PM' (exit 1, empty output) when requested in review cycle 1. Today is 2026-08-04, so the quota window has not reopened; the lane was not re-attempted this cycle to avoid a known-certain failure. Not a timeout and not a sandbox fault — the error text was captured on stderr."
    substituted_with: gemini
reviewer_passes:
  gemini_pass_1_broad: succeeded
  gemini_pass_2_focused: "failed — Gemini API returned 503 UNAVAILABLE ('This model is currently experiencing high demand') on two separate attempts (207 KB and 93 KB prompts, each with retries). Provider capacity, not a timeout or prompt-size limit: a 426 KB prompt succeeded in pass 1 minutes earlier. Seven of the eleven new findings therefore carry orchestrator verification only, including four of the five HIGHs."
reviewed_at: 2026-08-04T12:39:47Z
review_cycle: 2
previous_cycle_commit: 97eee74
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
plans_amended_since_cycle_1: [01-04, 01-05, 01-06, 01-08, 01-09, 01-10, 01-11]
plans_unchanged_since_cycle_1: [01-01, 01-02, 01-03, 01-07]
---

# Cross-AI Plan Review — Phase 1: Reproducible World (convergence cycle 2)

> **Reviewer availability note.** Codex was requested in cycle 1 and returned a hard account quota
> block (`codex-cli 0.145.0`, "You've hit your usage limit … try again at Aug 17th, 2026"). Today is
> 2026-08-04, so Codex remains unavailable and was not re-invoked. The `claude` CLI was skipped for
> reviewer independence — this session runs inside Claude Code. The review was therefore carried out
> by **Gemini CLI 0.52.0**, plus an independent orchestrator verification pass that read every cited
> line directly. Two Gemini passes were attempted: the broad convergence pass succeeded and is
> recorded verbatim; the focused follow-up pass hard-failed twice on a provider-side 503, which is
> documented below rather than silently dropped. This cycle is therefore **one reviewer pass**, down
> from two in cycle 1 — weigh the orchestrator-only findings accordingly.

> **Method note.** The planner's cycle-1 changelog was treated as a set of *claims to be falsified*,
> not as evidence. Every cycle-1 finding disposition below was re-derived from the current plan text
> at cited line numbers before the reviewer's verdict was consulted.

---

## Gemini Review (pass 1 — full-set convergence verification)

### Phase 1, CONVERGENCE CYCLE 2 — Adversarial Plan Review  *(reviewer output, verbatim; headings demoted one level)*

This report presents a thorough, line-by-line adversarial review of the amended implementation plans for Phase 1 of **NextMove**. The repository is currently in a greenfield state (only `.planning/` and root planning markdown exist). This review verifies the planner's resolution claims for Cycle 1 findings and hunts for any new design defects introduced by the amendments or within the previously unreviewed, unchanged plans.

---

### Summary

The Convergence Cycle 2 amendments represent a monumental leap in the engineering maturity of the NextMove implementation design. The planner has successfully untangled the circular dependency, recursion, and DVC output overlap issues that plagued Cycle 1. 

By restructuring the storage layer into a strict directed acyclic graph (DAG) around a private `_parquet.py` primitive and splitting lineage records into isolated, per-stage fragment files, the design achieves complete mathematical and operational consistency. The core success metric—a deterministic, byte-identical, no-op `dvc repro` run on a laptop—is now structurally and procedurally guaranteed.

However, our adversarial deep-dive has uncovered **two new design defects** (one HIGH regarding staging path resolution and one MEDIUM regarding a hardcoded simulation constant that violates `ENG-03`), alongside **one minor arithmetic/naming inconsistency** in the untouched plans. These concerns are highly localized and can be easily resolved without systemic re-engineering.

---

### Cycle-1 Finding Disposition

| Finding | Verdict | Cited Evidence & Resolution Analysis |
|:---|:---:|:---|
| **HIGH-1 (unbounded re-entry / RecursionError)** | **RESOLVED** | `01-06-PLAN.md:28-29`, `01-06-PLAN.md:249-253`, `01-06-PLAN.md:289-291`, `01-06-PLAN.md:374-377`. Lineage is persisted via the private primitive `_parquet.py` (`write_parquet_atomic`) rather than through `write_table`. Calling `write_table` on `Zone.lineage` is explicitly blocked by raising a `ValueError`. Calling `write_table` also features a `record_lineage` boolean switch which defaults to `True` but is bypassed when writing lineage. |
| **HIGH-2 (circular import)** | **RESOLVED** | `01-06-PLAN.md:30`, `01-06-PLAN.md:208-212`, `01-06-PLAN.md:286-288`, `01-06-PLAN.md:340-343`, `01-06-PLAN.md:427-430`, `01-06-PLAN.md:484-488`. The storage internal package is structured as a clear DAG: `paths.py` -> `_parquet.py` -> `lineage.py` -> `repository.py`. Direct subprocess import tests are implemented to prove no circular references exist at package load. |
| **HIGH-3 (DVC output overlap)** | **RESOLVED** | `01-06-PLAN.md:31`, `01-06-PLAN.md:185-196`, `01-06-PLAN.md:370-373`, `01-06-PLAN.md:378-382`, `01-11-PLAN.md:29`, `01-11-PLAN.md:154-171`, `01-11-PLAN.md:205-216`, `01-11-PLAN.md:220-224`. Lineage is split into per-stage fragments (`data/lineage/simulate.parquet`, etc.) which are registered as the single, exclusive outputs of their corresponding stages. This avoids directory out overlaps, and stages do not read other stages' fragments. No-op `dvc repro` runs successfully leave `dvc.lock` byte-identical. |
| **HIGH-4 (anti-forgery contract self-contradiction)** | **RESOLVED** | `01-06-PLAN.md:28`, `01-06-PLAN.md:347-353`, `01-06-PLAN.md:359-368`, `01-06-PLAN.md:421-427`, `01-06-PLAN.md:492-496`, `01-06-PLAN.md:566-571`. `LineageRecordDraft` carries no `content_hash` or `input_hashes` fields. The caller only provides the paths and `record_lineage` reads and hashes files directly from disk at write-time, proven by a file-mutation test. |
| **MEDIUM-1 (full-scale run has no memory or runtime budget)** | **RESOLVED** | `01-06-PLAN.md:261-267`, `01-08-PLAN.md:31-33`, `01-08-PLAN.md:343-361`, `01-08-PLAN.md:377-387`, `01-08-PLAN.md:402-416`, `01-08-PLAN.md:467-476`, `01-09-PLAN.md:29`, `01-09-PLAN.md:169-179`, `01-09-PLAN.md:212-214`. High-horizon simulation events and ground-truth uplift values are flushed periodically to part-files using `write_table` with `record_lineage=False` to bound Python heap usage. After completion, they are merged via `write_table_from_parts` and the staging directory is deleted. The flush cadence is proven not to affect output bytes, and per-profile memory and runtime budgets are explicitly enforced by integration tests. Pydantic/Pandera ingestion validation is similarly batched to prevent materializing whole-history event lists. |
| **MEDIUM-2 (four plans modify `justfile` without declaring it)** | **RESOLVED** | `01-04-PLAN.md:9`, `01-08-PLAN.md:14`, `01-09-PLAN.md:13`, `01-10-PLAN.md:12`, `01-11-PLAN.md:9`, `01-11-PLAN.md:120-128`. All modified plans now correctly list `justfile` under `files_modified`, and `01-11-PLAN.md`'s `read_first` provenance claim accurately lists prior recipe additions. |
| **LOW-1 (`sort_events` missing exports)** | **RESOLVED** | `01-05-PLAN.md:29`. `"sort_events"` is now explicitly included in the `exports` array for `src/nextmove/ingest/contracts.py`. |
| **LOW-2 (no static type checking)** | **RESOLVED** | `01-04-PLAN.md:26`, `01-04-PLAN.md:72-92`, `01-04-PLAN.md:260-272`, `01-04-PLAN.md:290-293`, `01-04-PLAN.md:360-363`. The plan explicitly documents the decision to defer static type checking (with `mypy` or `pyright`) to Phase 2 (ENG-02) within both the planner notes and as a permanent comment block inside the CI workflow `.github/workflows/ci.yml`. No type check step is run, ensuring CI remains stable. |

---

### New Concerns

During our adversarial review of the amended and unchanged plans, we identified the following new defects:

#### Concern 1: Path Resolution Failure on Temporary Staging Files
* **Severity:** **HIGH**
* **Cited Line:** `01-06-PLAN.md:197-200`, `01-06-PLAN.md:238`, `01-08-PLAN.md:351`
* **Failure Mechanism:** In `01-08-PLAN.md:351`, the simulation's periodic flushing writes part-files to `data/_staging/events_raw/` using `write_table`. However, `write_table` does not accept a custom root destination and relies on `resolve_table_path(table_name, zone)` internally. `resolve_table_path` strictly asserts that the resolved path is a descendant of the zone directory determined by the `Zone` enum (which only has `raw`, `canonical`, `features`, `ground_truth`, and `lineage` as members). Since `data/_staging/` is a sibling of these zone directories and is not a descendant of any of them, any attempt by `write_table` to write there will cause `resolve_table_path` to raise a `ValueError` (intended to prevent path traversal, per `T-01-15`). Thus, the staging flush logic will crash on execution.
* **Smallest Fix:**
  Add a `staging` or `temp` member to the `Zone` StrEnum in `src/nextmove/storage/paths.py` (e.g. `Zone.staging = "_staging"`). This registers `data/_staging/` as a legitimate, secure storage zone that can be addressed by `resolve_table_path` and `write_table` (with `record_lineage=False`) without escaping boundary checks.

#### Concern 2: Hardcoded Simulation Constant `UPLIFT_SNAPSHOT_EVERY_TICKS` Violates `ENG-03`
* **Severity:** **MEDIUM**
* **Cited Line:** `01-08-PLAN.md:85-89`, `01-08-PLAN.md:344`, `01-08-PLAN.md:381-384`, `01-08-PLAN.md:573-575`
* **Failure Mechanism:** Under `01-08-PLAN.md:344` and Task 3, the materialization cadence for `ground_truth_uplift` is hardcoded as a constant `UPLIFT_SNAPSHOT_EVERY_TICKS = 30` in `run.py`. Because this controls the cadence of precomputed ground-truth uplift values (crucial for Phase 4's evaluation of propensity-as-uplift error), it is a business/simulation parameter. However, `ENG-03` mandates that all business numbers and simulator parameters must reside in schema-validated, git-reviewed YAML configurations under `config/` so behavior changes can be controlled without editing code. Hardcoding it as a constant in `run.py` directly violates `ENG-03` and success criterion 5 (which states that changing a simulator parameter in YAML must change behavior with no code edit).
* **Smallest Fix:**
  Remove the hardcoded constant from `run.py`. Move `uplift_snapshot_every_ticks` into `SimulatorConfig` in `src/nextmove/config/models.py` and declare its default (e.g. `30`) in `config/simulator.yaml`. This allows `run_simulation` to read it dynamically from the `ResolvedConfig` (`resolved.config.simulator.uplift_snapshot_every_ticks`), making it fully configurable and profile-overridable (e.g., setting it to 1 in `tiny.yaml` or `demo.yaml` for testing, and 30 in `default.yaml`), aligning with `ENG-03` and success criterion 5.

#### Concern 3: Naming Contradiction for `ENG-01` Package Inventory
* **Severity:** **LOW**
* **Cited Line:** `01-01-PLAN.md:36`, `01-01-PLAN.md:73`, `01-01-PLAN.md:218`, `01-01-PLAN.md:268`
* **Failure Mechanism:** `01-01-PLAN.md` repeatedly refers to the project having a "ten-package modular-monolith layout" or "exactly the ten named packages" (e.g. lines 36, 73, 218). However, the actual list of core packages specified in lines 36-37 and in requirement `ENG-01` contains exactly **eleven** packages (`simulator`, `ingest`, `features`, `segmentation`, `models`, `rules`, `decisions`, `policies`, `explain`, `evaluate`, `api`). When the 2 infrastructure packages (`config` and `storage`) are added, there are 13 subdirectories. The test `test_package_layout.py` and the acceptance criterion `ls src/nextmove/*/__init__.py | wc -l` expect `13` packages, which is correct for 11 + 2, but the plan's text remains arithmetically contradictory by calling them "the ten named packages".
* **Smallest Fix:** Clean up the prose in `01-01-PLAN.md` to consistently refer to the layout as an "eleven-package core modular-monolith" (excluding the two infrastructure packages) or "13 packages in total under `src/nextmove/`", removing any mentions of a "ten-package" layout.

---

### Strengths

1. **Perfect Isolation and Boundary Enforcement:** The combination of `import-linter` contracts and custom AST-walking verification rules (`tests/unit/test_import_contract.py` and `tests/leakage/test_ground_truth_isolation.py`) ensures that code and data isolation boundaries cannot be bypassed. The simulator is genuinely walled off from the models, and models are statically and dynamically blocked from seeing simulator ground-truth answers.
2. **Ironclad Determinism Underpinnings:** The implementation of `write_parquet_atomic` in `_parquet.py` serves as a single audit point for all file I/O. Sorting on a guaranteed unique primary key tuple immediately before write, pinning single-threaded connection states for DuckDB aggregation, and strictly stripping host clock and library version metadata from Parquet footers completely eliminates all sources of analytical drift.
3. **Pervasive Threat Verification:** The test suites go beyond standard validation to actively verify threat mitigations. The `contract_probe` asserts that the import linter can actually go red, and the lineage tests mutate files on disk to verify that hashes are computed from physical bytes rather than caller claims.
4. **First-Class Performance and Memory Planning:** Bounding heap allocations via a well-designed flush strategy, and verifying it via sub-linear heap scaling assertions (`tracemalloc`) in `test_simulation_budget.py`, guarantees that the default scale runs effortlessly on a laptop, fulfilling `ENG-08`.

---

### Risk Assessment

* **Rating:** **LOW**
* **Justification:** The Phase 1 implementation plans have reached an outstanding degree of rigor and engineering readiness. All critical architectural risk clusters—including circular imports, infinite recursions, and overlapping DVC outputs—have been structurally resolved. The new concerns raised during this Convergence Cycle 2 pass are highly localized, straightforward to adjust, and do not threaten the underlying modular architecture or validation logic. Applying these minor fixes will result in a flawless, highly robust execution path.

---

## Gemini Review (pass 2 — focused: storage API surface and DVC stage graph)

**NOT RUN — reviewer API unavailable (server-side capacity, two attempts).**

A focused adversarial pass was prepared and invoked twice against the same reviewer, to put the
findings the broad pass did not reach (HIGH-6, HIGH-7, HIGH-8) in front of an independent model
rather than leaving them orchestrator-only. Both attempts hard-failed:

```
_ApiError: got status: UNAVAILABLE. {"error":{"code":503,"message":"This model is currently
experiencing high demand. Spikes in demand are usually temporary. Please try again later.",
"status":"UNAVAILABLE"}}
```

- Attempt 1: 207 KB prompt (plans 01-06, 01-08, 01-09, 01-10, 01-11, four focused questions) —
  4 retries with backoff, then 503.
- Attempt 2: 93 KB prompt (plans 01-06 and 01-11, three focused questions) — retried, then 503.

This is a capacity failure on the provider side, not a timeout, not a prompt-size limit and not a
malformed invocation: the same CLI, the same auth and a 426 KB prompt succeeded minutes earlier in
pass 1. Recorded rather than silently dropped, per the workflow's rule that an absent lane must be
diagnosable. **Consequence: seven of the eleven new findings below carry no independent-reviewer
confirmation and rest on orchestrator verification alone — including four of the five HIGHs.** They are marked as such in the
Verification coverage table, and each cites the plan lines a reader can check directly.

---

## Codex Review

**NOT RUN — reviewer unavailable (account quota, unchanged since cycle 1).**

```
ERROR: You've hit your usage limit. To continue using Codex and get access to
GPT-5.3-Codex, start a free trial of Plus today, or try again at Aug 17th, 2026 11:16 PM.
```

The quota window reopens 2026-08-17. Re-running `/gsd-review --phase 1 --codex` after that date
would add the second independent model this phase has never had. Recorded here again so the audit
trail stays honest rather than silently showing a one-reviewer run as a normal cross-AI review.

---

## Consensus Summary

**Verdict: the cycle-1 knot is genuinely cut. Five new HIGH findings block execution.**

All four cycle-1 HIGHs are **fully resolved**, and the resolution is structural rather than cosmetic.
`_parquet.py` is a real module beneath both public storage modules, not a lazy-import patch; the
storage import graph is a DAG (`paths` → `_parquet` → `lineage` → `repository`) proven by
fresh-interpreter subprocess imports rather than by the suite happening to pass; `Zone.lineage` and
the `Stage` enum give each pipeline stage exactly one declarable lineage output; and
`LineageRecordDraft` genuinely carries no hash field, with a mutate-the-file-after-the-draft test
that a caller-supplies-the-hash design would fail.

That said, the amendments introduced defects of their own, and the orchestrator's independent pass
found four additional mechanical contradictions the cycle-1 focused pass never reached. **Five
HIGHs remain.** Four of them share a shape with cycle-1 HIGH-4: an acceptance criterion that cannot
be satisfied by the design the same plan set specifies. Notably, two of the five (HIGH-5, HIGH-9)
are failures *of the MEDIUM-1 memory fix itself* — the simulator's flush mechanism cannot address
its own destination, and the ingest stage claims the same fix while not applying it. The phase is
**not execution-ready**.

### Agreed Strengths

*(Reviewer-stated, orchestrator-verified at the cited lines.)*

- **The recursion knot is cut three independent ways, and each way is separately testable.** Lineage
  persists through `write_parquet_atomic` and never through `write_table`
  (`01-06-PLAN.md:377-381`); `write_table` and `write_table_from_parts` both raise on `Zone.lineage`
  (`:249-252`, `:267`, acceptance `:289-290`); and an explicit `record_lineage: bool = True` switch
  exists for callers that must opt out (`:238-239`, `:254-259`). A counting-wrapper test asserts
  exactly one recording call per write (`:429`). Threat T-01-31 (`:579`) now has a real mitigation.
- **The import DAG is proven by construction, not asserted.** `_parquet.py` "must import only
  `pyarrow`, the standard library, and `paths.py`" (`01-06-PLAN.md:204-208`), with a grep criterion
  that fails on any `repository`/`lineage` import (`:287`) and two fresh-interpreter subprocess
  imports (`:288`, `:428`, `:489-490`). This is the durable fix; a lazy import inside `write_table`
  would have been the shortcut and was correctly refused (`:123-124`).
- **The anti-forgery contract is now achievable and its residual is named.** The draft declares no
  `content_hash` and no `input_hashes` (`01-06-PLAN.md:349-356`); `record_lineage(path, draft,
  input_paths, root)` hashes the table and every input from disk (`:363-368`); the acceptance
  criteria pin the exact parameter tuple (`:424`) and require a test that mutates the file *after*
  the draft is built (`:425`). `config_hash` is retained as a caller-supplied field with the reason
  stated and the residual recorded in T-01-14 (`:576`) — an honest carve-out rather than a silent one.
- **Lineage fragments are inside the byte-comparison, not outside it.** `01-11-PLAN.md:246-257`
  deliberately includes the three fragments in the twelve-file golden digest set, on the reasoning
  that they are "the artifact most likely to acquire a wall-clock field". A weaker plan would have
  compared only the data tables and left the provenance layer unguarded.
- **The memory fix was designed not to become a determinism hazard.** `flush_every_ticks` is a
  function parameter deliberately outside the hashed config surface, with the reasoning written out
  (`01-08-PLAN.md:364-367`), and a flush-invariance test asserts equal digests at flush intervals of
  1 and of more-than-the-horizon (`:410-413`, acceptance `:467`). The part-file-count assertion
  (`:468`) means a silently-disabled flush fails loudly instead of merely getting slower.
- **The undeclared-`justfile` problem is fully closed.** Scripted check: all six plans that add a
  recipe (`01-01`, `01-04`, `01-08`, `01-09`, `01-10`, `01-11`) now declare `justfile` in
  `files_modified`, and each sits in a distinct wave (1, 2, 4, 5, 6, 7), so no two ever write it
  concurrently. `01-11-PLAN.md:120-126` now states the accumulated recipe set correctly.
- **The wave graph remains sound after the amendments.** Scripted re-verification: every `depends_on`
  entry resolves to a plan in a strictly earlier wave, and no two plans in the same wave share a
  `files_modified` entry.

### Agreed Concerns

---

**HIGH-5 (NEW) — the flush destination `data/_staging/` is unreachable through the storage API the
plans declare, so the entire MEDIUM-1 memory fix cannot execute.**

*Concurred: Gemini pass 1 (Concern 1, HIGH) and the orchestrator, independently.*

`01-08-PLAN.md:358-360` instructs the executor to write flush part files "to a numbered part file
under `data/_staging/events_raw/` via `write_table` with `record_lineage=False`", and `:386` applies
the same mechanism to `ground_truth_uplift`. `01-08-PLAN.md:518-519` names both staging
subdirectories as artifacts.

But `write_table`'s declared signature (`01-06-PLAN.md:238-239`) has no root, destination or path
parameter of any kind. It resolves its destination through `resolve_table_path(name, zone, root)`,
which "asserts the result is a descendant of the zone directory — raising `ValueError` naming the
offending table name otherwise" (`01-06-PLAN.md:199-202`). `Zone` has exactly five members —
`raw`, `canonical`, `features`, `ground_truth`, `lineage` (`:188-191`) — and `data/_staging/` is a
sibling of all five, not a descendant of any. The escape route is closed explicitly: `:297` asserts
`resolve_table_path` raises for a table name containing a parent-directory segment.

The three obvious workarounds each break a stated acceptance criterion in another plan:

| Workaround | Breaks |
|---|---|
| Add a sixth `Zone` member | `01-06-PLAN.md:292` asserts `sorted(z.value for z in Zone)` prints exactly the five names |
| Write the part files with `pyarrow` directly | `01-04-PLAN.md:140-149` contract two forbids `pyarrow` in `nextmove.simulator`; `01-08-PLAN.md:473` asserts `lint-imports` exits 0 |
| Put part files in `data/raw/` instead | Contradicts `01-06-PLAN.md:407-408` and `:557-558` (`.dvcignore`d transient dir) and `01-08-PLAN.md:464` (`data/_staging/` must not exist after the run) |

This is not a naming quibble: `01-06-PLAN.md:258-259` explicitly endorses `write_table` as the
writer for "the staging part-files described in plan 01-08" while its own resolver forbids the
destination. Plan 01-08 Task 3 halts on its first flush, which voids threat T-01-34
(`01-08-PLAN.md:542`, DoS, high) and with it ENG-08's laptop guarantee — the exact thing MEDIUM-1
was raised to fix.

*Smallest fix:* give `write_table` and `write_table_from_parts` an explicit destination escape for
transient artifacts — either a sixth `Zone.staging` member (and amend `01-06-PLAN.md:292`
accordingly), or a separate `write_part_file(rows, dest, sort_key)` primitive re-exported from
`nextmove.storage` that routes through `write_parquet_atomic` without zone resolution. Whichever is
chosen, state it in `01-06`, because `01-08` cannot invent public storage API.

---

**HIGH-6 (NEW) — `out_root` is declared by four plans and plumbed by none, so plan 01-11's
two-root golden reproducibility test cannot be written.**

*Orchestrator finding; Gemini pass 1 did not reach it.*

Three producer functions and three CLIs declare an output-root override:

- `run_simulation(resolved, out_root: Path | None = None, ...)` — `01-08-PLAN.md:345`; CLI `--out`
  at `:395`
- `ingest_events(raw_records, resolved, adapter_name, out_root=None, ...)` — `01-09-PLAN.md:166`;
  CLI `--out` at `:341`
- `compute_as_of(..., out_root=None)` and `materialize_grid(resolved, out_root=None)` —
  `01-10-PLAN.md:228`, `:232`; CLI `--out` at `:257`

Trace `out_root` to disk through plan 01-06's declared API and it terminates immediately. Of the
storage functions, only `resolve_table_path` (`01-06-PLAN.md:199`), `record_lineage` (`:363-364`),
`read_lineage` (`:389`) and `print_lineage_chain` (`:395`) accept a `root`. The four functions a
producer actually calls do not: `write_table` (`:238-239`), `write_table_from_parts` (`:261-262`),
`read_table` and `table_exists` (`:269`), `query` (`:270-271`). `DATA_ROOT` is a module constant
(`:185`, `:545`), not a parameter. A producer holding an `out_root` has nowhere to put it.

This is load-bearing, not cosmetic. `01-11-PLAN.md:245` specifies the headline golden test as
"running the `ci` profile twice into two separate output roots and asserting that the sha256 of
every produced Parquet file matches", and `:250` walks "the output root". `01-11-PLAN.md:304`
asserts that suite exits 0. As the API stands, both runs write the same `DATA_ROOT` and the second
overwrites the first, so the test is either unwritable or vacuous. Phase success criterion 1 rests
on it.

The charitable reading — that `DATA_ROOT` is cwd-relative, so running from two directories yields
two roots without any parameter — is ruled out by the plan itself: `01-11-PLAN.md:272-275` specifies
"different working directories" as a *separate* assertion from the two-output-roots one at `:245`.
If cwd were the root-selection mechanism the two assertions would be the same test. Relatedly,
`01-06-PLAN.md:185` defines `DATA_ROOT` only as "the repository-relative `data/` directory" without
saying relative to what — cwd, the git root, or `__file__` — and that ambiguity is part of the same
gap.

Note this defect is *pre-existing* — cycle-1's `write_table(rows, table_name, zone, sort_key,
resolved_config, input_tables=())` (`git show 4005e0e:…/01-06-PLAN.md:147`) had no root either — but
it was never raised, and the cycle-2 amendments added `root` to three lineage functions without
adding it to the write path, which makes the asymmetry newly conspicuous.

*Smallest fix:* add `root: Path | None = None` to `write_table`, `write_table_from_parts`,
`read_table`, `table_exists` and `query` in `01-06`, forward it to `resolve_table_path` and on to
`record_lineage`, and add an acceptance criterion that two runs under different roots produce equal
digests.

---

**HIGH-7 (NEW) — plan 01-11's static DVC non-overlap check, added to close HIGH-3, fails on the
`dvc.yaml` that the same plan specifies.**

*Orchestrator finding; Gemini pass 1 recorded HIGH-3 as cleanly resolved and did not test the new
criterion against the new stage graph.*

`01-11-PLAN.md:207` requires a script that fails when "any stage's `outs` path is equal to or a
parent of another stage's `outs` **or `deps`** path … comparing each stage's outs against every
other stage's outs and deps".

Apply it literally to the stage graph at `01-11-PLAN.md:158-165`:

| Stage A | A's `outs` | Stage B | B's `deps` | Verdict |
|---|---|---|---|---|
| `simulate` | `data/raw/` | `ingest` | `data/raw/` | equal → **script fails** |
| `ingest` | `data/canonical/` | `features` | `data/canonical/` | equal → **script fails** |

Those two edges *are the pipeline*. A DVC DAG is wired precisely by one stage's `outs` being the
next stage's `deps`; a check that forbids it fails on every correct pipeline and can never go green.
`01-11-PLAN.md:304` and the Task 1 verify block depend on this criterion passing.

The plan's own prose has the rule right — `01-11-PLAN.md:167` says "Every path a stage writes is
declared as an out of that stage and of no other", which is outs-vs-outs disjointness, and `:168-170`
correctly scopes the both-sides-of-the-graph prohibition to *lineage fragments only*. The acceptance
criterion over-generalized that lineage-specific rule to all paths.

The same over-generalization is baked into `01-11-PLAN.md:29`'s `must_haves` truth: "no stage writes
into another stage's declared dependency or output". `simulate` writes `data/raw/`, which is
`ingest`'s declared dependency, so the truth is false of the design it describes.

*Smallest fix:* restate `01-11-PLAN.md:207` as two rules — (a) no path appears in more than one
stage's `outs`; (b) no stage's `outs` path is equal to or a parent of another stage's `deps` path
**unless that same path is declared as this stage's own out**, i.e. exempt the legitimate
producer→consumer edge — and keep an explicit clause that no lineage fragment may appear as any
stage's `dep`, which is the property HIGH-3 actually needed. Correct `:29` to match.

---

**HIGH-8 (NEW) — `write_parquet_atomic`'s sort-key precondition is violated by at least three of the
nine tables the phase writes, blocking waves 4 and 6.**

*Orchestrator finding; neither reviewer pass reached it.*

`01-06-PLAN.md:212-213` requires `write_parquet_atomic` to "require the final element of `sort_key`
to be a column with unique values and raise if it is not", and `01-06-PLAN.md:296` restates it as an
acceptance criterion: "`write_table` raises when the final element of `sort_key` is not unique across
the supplied rows". The check is on the *final column's values*, not on the tuple.

Audit of every table written through `write_table` in this phase:

| Table | Declared sort key | Final element | Unique? |
|---|---|---|---|
| `events_raw` / `events` | `CANONICAL_SORT_KEY` = `(customer_id, ts, event_id)` (`01-05:155-157`) | `event_id` | yes |
| `rejects` | `reject_id` (`01-09:189`) | `reject_id` | yes |
| `catalog` | `sku` (`01-08:371`) | `sku` | yes |
| `campaigns` | `campaign_id` (`01-08:371-372`) | `campaign_id` | yes |
| `customer_traits` | **none declared**; one row per customer (`01-08:377-378`) | inferable as `customer_id` | yes, if inferred |
| **`inventory_snapshots`** | **`(tick, sku)`** (`01-08:371`) | **`sku`** | **no — repeats once per tick** |
| **`feature_grid`** | **`(customer_id, as_of_ts)`** (`01-10:234-235`, criterion `01-10:212`) | **`as_of_ts`** | **no — repeats across customers** |
| **`ground_truth_uplift`** | **none declared** (`01-08:379-381`) | — | **no single unique column exists in `(customer_id, action_type, tick, uplift)`** |

`inventory_snapshots` holds one row per `(tick, sku)`, so `sku` recurs for every tick.
`feature_grid` holds "one row per (customer, as_of_ts)" (`01-10-PLAN.md:232-233`), so `as_of_ts`
recurs for every customer. In both cases the *tuple* is unique and the sort is a genuine total
order — but the precondition as written checks the last column alone and raises.

The design intent is visible at `01-06-PLAN.md:24` ("with a unique tiebreak column") and is correct;
the precondition is the wrong mechanical form of it. As written, `01-08-PLAN.md:461` (four raw
tables exist after a `tiny` run) and `01-10-PLAN.md:212` (grid sorted by `(customer_id, as_of_ts)`)
cannot both hold with `01-06-PLAN.md:296`. There is no carve-out anywhere: grepping `01-06` for
`tiebreak|unique` returns only lines `24`, `173`, `212`, `296`, `361`, `578`, none of which exempt a
composite key.

*Smallest fix:* change `01-06-PLAN.md:212-213` and `:296` to require the sort key **tuple** to be
unique across the supplied rows (raising and naming the first duplicate tuple), which is the property
that actually makes the order total; keep the "unique tiebreak column" language as guidance for
single-column keys. Separately, declare sort keys for the two `Zone.ground_truth` tables in `01-08`:
`:369-370` promises "each with its declared sort key" for the four raw tables and delivers them at
`:370-372`, but the `customer_traits` and `ground_truth_uplift` writes at `:377-381` state none, so
two of the nine tables reach `write_table` with a required argument the plan never specifies.

---

**HIGH-9 (NEW) — plan 01-09 claims to close the ingest half of MEDIUM-1 by batching, but its landing
step still materializes the whole event history, and its own streaming acceptance criterion is
unsatisfiable by the design it specifies.**

*Orchestrator finding; neither reviewer pass reached it.*

`01-09-PLAN.md:106-114` states that the reviewer's Pandera/Pydantic memory concern "is closed here
the same way" as MEDIUM-1, because `ingest_events` "consumes its input in batches and never
materializes the whole event history as live Pydantic objects". The batching at `:166-171` does
bound the *validation* working set, and `:169-171` names the hazard explicitly ("the same
laptop-memory hazard the simulator's flush strategy exists to avoid").

The landing step then does exactly what the plan says it does not. `01-09-PLAN.md:181-183`: "read the
existing table if present, union it with the new events keyed on `event_id`, drop rows already
present by `event_id` …, sort by `CANONICAL_SORT_KEY`, and write through `write_table`". A union,
a dedupe and a global sort followed by one terminal `write_table` require every valid `Event` from
every batch to be live simultaneously, plus the entire pre-existing canonical table. The batch loop
bounds only the validation frontier; peak memory is still the full 50k-customer, 548-day event set.

Two things make this a HIGH rather than a repeat of MEDIUM-1:

1. **The acceptance criterion at `01-09-PLAN.md:214` cannot pass.** It requires "a test passing a
   generator that raises if fully materialized before the first write". Under a single terminal
   write, the generator is necessarily fully consumed before that write, so the generator raises and
   the test fails. The criterion presumes a streaming design; the action prose specifies a
   collect-then-write one.
2. **The tool was read and not used.** `01-09-PLAN.md:126-127`'s `read_first` explicitly directs the
   executor to read "the signatures of `write_table` **and `write_table_from_parts`**" — but
   `write_table_from_parts` appears nowhere in 01-09's action, and grepping 01-09 for
   `flush|part file|part-file|_staging` returns only the line naming the hazard (`:171`). Plan 01-08
   built the exact mechanism that solves this one wave earlier; 01-09 references it and then writes
   a single-shot design.

There is also no budget test on this path: `tests/integration/test_simulation_budget.py` is
simulator-only (`01-08-PLAN.md:405-436`), and 01-09's criteria (`:204-216`) contain no heap or
wall-clock assertion. So nothing in the suite would catch it, which is the same blind spot MEDIUM-1
was raised about.

*Smallest fix:* mirror 01-08 Task 3 in `01-09`: write each validated batch to a numbered part file,
merge with `write_table_from_parts` after the last batch, and state how the `event_id` dedupe and the
canonical sort are performed across parts without a full in-memory union (a DuckDB
`SELECT DISTINCT ON … ORDER BY` over the part files through `query` is the natural route, and keeps
the Parquet/DuckDB access inside the storage layer). Note this fix depends on HIGH-5 being closed
first — 01-09 would need the same reachable part-file destination that 01-08 currently lacks.

---

**MEDIUM-3 (NEW) — `UPLIFT_SNAPSHOT_EVERY_TICKS` is a code literal that materially determines a
shipped table's contents, contradicting ENG-03 and plan 01-03's own stated invariant.**

*Concurred: Gemini pass 1 (Concern 2, MEDIUM) and the orchestrator, with different reasoning.*

`01-08-PLAN.md:343-344` declares `UPLIFT_SNAPSHOT_EVERY_TICKS = 30` as a module-level constant in
`src/nextmove/simulator/run.py`, and `:380-385` makes it the sampling cadence of the shipped
`ground_truth_uplift` table (18 snapshots, ~7.2M rows at default scale). ENG-03
(`REQUIREMENTS.md:215-218`) names "simulator parameters" explicitly among the business numbers that
must live in schema-validated YAML. Plan 01-03's `must_haves` truth is stricter still: "no such
number is a literal in `src/nextmove/`" (`01-03-PLAN.md:30`, restated at `:404`).

The sharper argument is internal to plan 01-08. At `:364-367` the plan reasons that
`flush_every_ticks` is deliberately *not* a config value "because two runs that differ only in flush
cadence must be byte-identical and a config difference would imply a legitimate output difference" —
and backs it with an invariance test. That reasoning is correct, and its converse applies directly to
`UPLIFT_SNAPSHOT_EVERY_TICKS`: changing it *does* change the output bytes legitimately, so it must be
inside the hashed surface. As it stands, two runs with different cadences produce different
`ground_truth_uplift` bytes under an identical config hash, and the lineage row asserts a
reproducibility property that no longer holds — the same failure family as cycle-1 HIGH-4, which the
phase went to considerable trouble to close.

*Smallest fix:* move the cadence to `SimulatorConfig` (`01-03-PLAN.md:41`) with its default in
`config/simulator.yaml`, read it from `ResolvedConfig` in `run_simulation`, and keep
`FLUSH_EVERY_TICKS` exactly as it is. This also closes MEDIUM-4 below at no extra cost.

---

**MEDIUM-4 (NEW) — the uplift-cadence flagged assumption never reaches the reviewer-facing document,
and the doc floor check structurally cannot catch it.**

*Orchestrator finding.*

The assumption itself is **genuinely surfaced**, and this deserves saying plainly: it is a
`flagged_assumptions` entry with `status: unresolved` (`01-08-PLAN.md:85-89`), it is repeated in the
task prose with a "must be raised before phase verification" instruction (`:386-387`), and the
SUMMARY template carries it forward (`:573-575`). That is a real mechanism, not a formality — it
answers the question of whether the planner buried the ~219M-row discovery.

What is missing is the reviewer-facing half. SIM-03 requires every generative assumption to be
documented, and `01-11` Task 3 owns `docs/SIMULATOR_ASSUMPTIONS.md`. Its required-content list
(`01-11-PLAN.md:358-372`) never names the uplift snapshot cadence, and grepping `01-11-PLAN.md` for
`uplift` returns only lines `160`, `248` and `422` — all DVC/golden plumbing, none documentation.
Worse, the floor check at `01-11-PLAN.md:400` only asserts that "every top-level key under
`simulator:` in `config/simulator.yaml`" appears in the document. Because the cadence is deliberately
*not* a config key, the check cannot ever catch its absence. A reader of the shipped repo would find
a 7.2M-row ground-truth table with no stated sampling rate.

*Smallest fix:* fixing MEDIUM-3 fixes this automatically — once the cadence is a `simulator:` config
key, `01-11-PLAN.md:400`'s floor check requires it in the document. Failing that, add the cadence
explicitly to `01-11` Task 3's `## Known Limitations` content list.

---

**MEDIUM-5 (NEW) — plan 01-09's append-only canonical-landing invariant is vacuous under
`dvc repro`, and nothing tests it where it actually matters.**

*Orchestrator finding.*

`01-09-PLAN.md:181-187` specifies append-only landing: "read the existing table if present, union it
with the new events keyed on `event_id`, drop rows already present … Never delete or mutate an
already-landed row." `01-11-PLAN.md:162` declares `data/canonical/` as the `ingest` stage's `outs`
with no `persist` flag. `dvc repro` removes a stage's non-persistent outs before executing it, so
under the pipeline the "read the existing table if present" branch never finds one — every run is a
full rebuild from `data/raw/`.

That is not necessarily wrong (a full rebuild is deterministic and idempotent), but the plans do not
say which semantics they intend, and the only test of the property runs outside the pipeline:
`01-09-PLAN.md:210` asserts "a second identical ingest leaves the canonical file's sha256 unchanged"
via a direct `ingest_events` call, which passes regardless. The DATA-02 flagged assumption at
`01-09-PLAN.md:67` explicitly says re-ingest semantics are unspecified by any source artifact and
must be raised before phase verification — so this is a known-open question whose most likely
real-world trigger (running under DVC) is untested.

*Smallest fix:* state in `01-09` that under `dvc repro` the canonical zone is fully rematerialized
from `data/raw/`, so the append-only path serves direct `just ingest` invocation only; and add an
acceptance criterion in `01-11` asserting the canonical digest after two consecutive `dvc repro`
runs is unchanged, which tests the property in the mode that actually ships.

---

**MEDIUM-6 (NEW) — plan 01-10 declares a `pyarrow.Table` return annotation inside a package that
plan 01-04's import contract forbids from importing `pyarrow`.**

*Orchestrator finding.*

`01-10-PLAN.md:228` declares `compute_as_of(customer_ids, as_of_ts, resolved, out_root=None) ->
pyarrow.Table` in `src/nextmove/features/`. `01-04-PLAN.md:140-149` defines contract two with
`source_modules` explicitly including `nextmove.features` and `forbidden_modules = ["pyarrow",
"duckdb"]`, and `01-04-PLAN.md:23` states the invariant as "No package other than `nextmove.storage`
imports pyarrow or duckdb". `01-06-PLAN.md:295` and `01-10-PLAN.md:276` both assert `lint-imports`
exits 0.

The natural implementation of that annotation — `import pyarrow`, or a `TYPE_CHECKING`-guarded
import — drives `lint-imports` red. A bare `from __future__ import annotations` with no import at
all technically passes the linter but leaves an unresolvable annotation. Notably `01-10-PLAN.md:276`
describes its own criterion as proving `features` "acquired neither a **duckdb** import nor a
simulator import" — silently dropping `pyarrow` from what it claims to prove, which suggests the
tension was half-noticed. `01-04-PLAN.md:55`'s flagged assumption already names "a
TYPE_CHECKING-guarded import" as an unresolved SIM-02 edge, so the category is open but undecided.

*Smallest fix:* have `nextmove.storage` export a public type alias (e.g. `Table`) that consumers
annotate against, and change `01-10-PLAN.md:228` to use it — or state explicitly in `01-04` that
annotation-only references are permitted and how the linter is configured to allow them.

---

**LOW-3 (NEW) — plan 01-01 calls its package list "ten" while enumerating eleven, and its own
acceptance criterion assumes eleven.**

*Concurred: Gemini pass 1 (Concern 3, LOW) and the orchestrator.*

`01-01-PLAN.md:36` enumerates `simulator, ingest, features, segmentation, models, rules, decisions,
policies, explain, evaluate, api` — eleven names, matching ENG-01 verbatim
(`REQUIREMENTS.md:208-210`) — but calls them "exactly the ten named packages" and says "adding an
eleventh … fails the package-inventory test". The word "ten" recurs at `:73`, `:78`, `:81`, `:106`,
`:218`, `:231`, `:247`, `:257`, `:260`, `:328`. The arithmetic elsewhere is correct for eleven:
`:268` asserts `ls src/nextmove/*/__init__.py | wc -l` outputs `13` (eleven core plus `config` and
`storage`) and `:323` says "all thirteen modules".

This is actionable rather than cosmetic because `:231` instructs the executor to "Create the ten
ENG-01 packages". An executor who counts rather than reads the list creates ten and then fails
`:268`.

*Smallest fix:* replace "ten" with "eleven" throughout `01-01-PLAN.md`, including at `:36`'s
"adding an eleventh" clause.

---

**LOW-4 (NEW) — the `budget` recipe is missing from plan 01-11's `justfile` inventory.**

*Orchestrator finding.*

`01-08-PLAN.md:401-402` adds two recipes, `simulate` **and** `budget`, and lists both at `:509`.
`01-11-PLAN.md:218`'s acceptance criterion enumerates eleven recipes without `budget`, and
`:429-430`'s recipe-ownership inventory attributes only `simulate` to plan 01-08. Non-blocking — the
criterion says "lists", not "lists exactly", so an extra recipe does not fail it — but plan 01-11 is
the phase's inventory of record and it is wrong.

*Smallest fix:* add `budget` to `01-11-PLAN.md:218` and to the 01-08 attribution at `:429-430`.

---

### Cycle-1 finding disposition

| Cycle-1 finding | Verdict | Grounding (current line numbers) |
|---|---|---|
| **HIGH-1** `write_table` ↔ `record_lineage` infinite recursion | **FULLY RESOLVED** | Three independent mechanisms: lineage persists via `write_parquet_atomic` (`01-06:377-381`), `write_table`/`write_table_from_parts` raise on `Zone.lineage` (`:249-252`, `:267`), explicit `record_lineage` switch (`:238-239`). Criteria `:289-290`, `:429-430`. Threat T-01-31 (`:579`). |
| **HIGH-2** circular import `repository.py` ↔ `lineage.py` | **FULLY RESOLVED** | New `_parquet.py` (`01-06:10`, `:38-41`) imports only pyarrow/stdlib/`paths.py` (`:204-208`); `lineage.py` must not import `repository` (`:341-344`). Grep criteria `:287`, `:427`; fresh-interpreter subprocess imports `:288`, `:428`, `:489-490`. Structural, not a lazy-import patch (`:123-124`). |
| **HIGH-3** DVC stage-output overlap | **FULLY RESOLVED** *(but see HIGH-7)* | `Zone.lineage` + per-stage fragments (`01-06:131-136`, `:370-375`); per-stage `outs` (`01-11:158-165`, `:421-425`); `Stage` enum shared with DVC stage names (`01-06:194-197`, criterion `01-11:206`). No stage writes a directory another owns. The *overlap* is gone; the *check added to prove it* is broken — filed separately as HIGH-7. |
| **HIGH-4** anti-forgery contract self-contradictory | **FULLY RESOLVED** | Draft has no `content_hash`/`input_hashes` (`01-06:349-356`); `record_lineage(path, draft, input_paths, root)` hashes from disk (`:363-368`); criteria `:423-426` including the mutate-after-draft test; T-01-14 rewritten with `config_hash` as a stated residual (`:576`). The criterion at `:424` is now satisfiable by the design at `:363-364` — the exact property that failed in cycle 1. |
| **MEDIUM-1** no memory/runtime budget at full scale | **RESOLVED IN DESIGN, BLOCKED IN MECHANISM** | Design is thorough: flush loop (`01-08:351-362`), `write_table_from_parts` (`01-06:261-267`), `tests/integration/test_simulation_budget.py` with per-profile `(max_peak_heap_mb, max_wall_clock_s)`, flush invariance, part-file count, sub-linear growth, on-demand `default` gate (`01-08:405-436`, criteria `:467-470`), T-01-34/T-01-35 (`:542-543`). The flush *destination* is unreachable — filed as HIGH-5. Not double-counted below. |
| **MEDIUM-2** four plans modify `justfile` undeclared | **FULLY RESOLVED** | Scripted: all six touching plans declare it, each in a distinct wave. Provenance corrected at `01-11:120-126`. Residual inventory slip filed as LOW-4. |
| **LOW-1** `sort_events` missing from 01-05 exports | **FULLY RESOLVED** | `01-05:29` exports array now contains `"sort_events"`; package-root re-export criterion at `:174`. |
| **LOW-2** no static type checking, no stated decision | **FULLY RESOLVED** | Explicit deferral to Phase 2/ENG-02 as a `must_haves` truth (`01-04:26`), planner note (`:72-92`), a comment block written into the CI workflow itself (`:265-271`), and criteria asserting both that the comment names `mypy` and `ENG-02` and that no type-check step exists (`:290-291`) — so the deferral is real rather than a comment contradicting the file. |

### Divergent Views

- **Overall risk rating.** Gemini pass 1 rated the phase **LOW** risk and characterized the
  remaining issues as "highly localized … will result in a flawless execution path". The
  orchestrator rates it **MEDIUM, not execution-ready**: five HIGHs remain, four of which make a
  stated acceptance criterion unsatisfiable by the same plan set, and three of which (HIGH-7,
  HIGH-8, HIGH-9) would surface only when an executor runs the criterion and finds it cannot go
  green. Note also that Gemini rated MEDIUM-1 cleanly RESOLVED while two of the five HIGHs are
  failures of that very fix (HIGH-5, HIGH-9). As in cycle 1,
  read the LOW rating as a verdict on the *architecture*, which is genuinely strong, not on
  execution-readiness.
- **HIGH-3's closure.** Gemini pass 1 marked HIGH-3 cleanly RESOLVED and cited `01-11:205-216` as
  supporting evidence. The orchestrator agrees the *overlap* is resolved but found that one of the
  criteria in that very range (`:207`) cannot pass. Recorded as a divergence rather than silently
  overwriting the reviewer's verdict: both readings are correct about different things.
- **`UPLIFT_SNAPSHOT_EVERY_TICKS` severity and reasoning.** Gemini framed it purely as an ENG-03
  config-hygiene violation. The orchestrator agrees on severity (MEDIUM) but grounds it additionally
  in plan 01-08's own stated rule at `:364-367` and in the ENG-04 auditability consequence — a
  constant outside the hashed surface that changes output bytes makes the lineage row claim a
  property it no longer has.
- **Whether the flagged assumption is adequately surfaced.** The orchestrator's verdict is **yes** —
  frontmatter `status: unresolved`, task prose, and SUMMARY carry-forward are a genuine mechanism
  (MEDIUM-4 concerns only the reviewer-facing doc, not the planning trail). Gemini did not evaluate
  the surfacing mechanism, only the constant's config placement.

---

## Verification coverage

How each finding above was grounded, so a reader can weigh it:

| Finding | Reviewer pass | Orchestrator independent check | Grounding |
|---|---|---|---|
| HIGH-1 resolved | pass 1 | Yes — read `01-06:238-259`, `:289-290`, `:377-381`, `:429-430` directly and grepped for any remaining `write_table` path to the lineage zone | Plan text, direct read |
| HIGH-2 resolved | pass 1 | Yes — traced the declared import direction of all three storage modules and confirmed `_parquet.py`'s import restriction is stated (`:204-208`) and grep-asserted (`:287`) | Plan text, direct read |
| HIGH-3 resolved | pass 1 | Yes — cross-read zone assignment (`01-06:131-136`) against stage `outs` (`01-11:158-165`) and each producer's declared writes (`01-08:369-387`, `01-09:193-196`, `01-10:234-237`) | Plan text, cross-plan |
| HIGH-4 resolved | pass 1 | Yes — read the criterion at `01-06:424` against the signature at `:363-364` and the draft fields at `:349-356`; the cycle-1 failure mode is genuinely absent | Plan text, direct read |
| **HIGH-5** `_staging` unreachable | pass 1 (Concern 1, HIGH) | Yes — found independently before pass 1 returned, by reading `01-08:358-360` against `01-06:188-202`, `:238-239`, `:292`, `:297`; enumerated all three workarounds and the criterion each breaks | Plan text, cross-plan |
| **HIGH-6** `out_root` unplumbed | not reached | Orchestrator only — grepped `out_root\|DATA_ROOT\|--out` across all 11 plans, then enumerated every 01-06 signature for a `root` parameter; confirmed pre-existing via `git show 4005e0e` | Grep + cross-plan + git history |
| **HIGH-7** DVC criterion overreach | not reached | Orchestrator only — applied `01-11:207`'s rule by hand to the stage graph at `:158-165`; two producer→consumer edges fail it | Plan text, manual application |
| **HIGH-8** sort-key uniqueness | not reached | Orchestrator only — tabulated every table written via `write_table` across 01-05/08/09/10 against the precondition at `01-06:212-213`; grepped `01-06` for `tiebreak\|unique` to confirm no carve-out | Plan text, cross-plan audit |
| **HIGH-9** ingest still materializes the full history | not reached | Orchestrator only — read the claim at `01-09:106-114` against the landing step at `:181-183`, then grepped 01-09 for `write_table_from_parts\|flush\|part.file\|_staging` (only the read_first at `:126` and the hazard note at `:171`); checked criteria `:204-216` for any heap assertion (none) | Plan text + grep, cross-plan |
| **MEDIUM-3** uplift cadence hardcoded | pass 1 (Concern 2, MEDIUM) | Yes — verified ENG-03 verbatim (`REQUIREMENTS.md:215-218`), plan 01-03's stricter truth (`:30`, `:404`), and the internal contradiction with `01-08:364-367` | Plan text + requirements |
| **MEDIUM-4** cadence absent from SIMULATOR_ASSUMPTIONS.md | not reached | Orchestrator only — grepped `01-11` for `uplift` (3 hits, all plumbing); read the required-content list `:358-372` and the floor check `:400` | Grep + plan text |
| **MEDIUM-5** append-only vacuous under DVC | not reached | Orchestrator only — read `01-09:181-187` against `01-11:162` (no `persist` flag) and `01-09:210`'s test scope | Plan text, cross-plan |
| **MEDIUM-6** `pyarrow` annotation vs contract | not reached | Orchestrator only — read `01-10:228` against contract two's source list at `01-04:140-149`; noted `01-10:276` drops pyarrow from its own claim | Plan text, cross-plan |
| **LOW-3** ten vs eleven packages | pass 1 (Concern 3, LOW) | Yes — scripted count of the names on `01-01:36` returns 11; cross-checked ENG-01 (`REQUIREMENTS.md:208-210`) and the `wc -l = 13` criterion at `:268` | Scripted count + direct read |
| **LOW-4** `budget` recipe missing from inventory | not reached | Orchestrator only — compared `01-08:401-402`/`:509` against `01-11:218`/`:429-430` | Plan text, cross-plan |
| Wave graph soundness (re-check) | pass 1 (asserted) | Yes — scripted re-extraction of `wave`/`depends_on`/`files_modified` for all 11 plans after the amendments; no dependency inversion, no intra-wave file collision | Scripted cross-check |
| `justfile` declaration (MEDIUM-2 closure) | pass 1 | Yes — scripted per-plan `files_modified` grep; all six declare it, all in distinct waves | Scripted cross-check |

**Repo-access caveat.** This phase is greenfield: the repository contains `.planning/` and root
planning documents but no `src/`, `pyproject.toml`, `justfile`, `dvc.yaml`, `docs/` or CI workflow.
No finding above asserts anything about implementation code, because none exists. All grounding is
against plan text and cross-plan contracts at the cited line numbers, which is the only checkable
surface at this stage.

**Reviewer-count caveat — weaker than cycle 1.** One external model, one successful pass (the focused
second pass hard-failed on provider capacity, see above), plus an orchestrator verification pass.
Seven of the eleven new findings were reached only by the orchestrator, including four of the five
HIGHs. Cycle 1 had two reviewer passes; this cycle had one. Treat the orchestrator-only findings as
*grounded but unconfirmed* — each cites plan lines a reader can check in under a minute, and that
check is the substitute for the missing second opinion. Two concrete strengthening options:
re-invoke `/gsd-review --phase 1 --gemini` once provider capacity recovers to run the prepared
focused pass, and re-run with Codex after its quota reopens on 2026-08-17. Plans 01-02, 01-03, 01-05
and 01-07 have still had no focused interrogation in either cycle.

**Convergence note.** Cycle 1 raised 4 HIGH; all 4 are fully resolved, and the resolution is
structural rather than cosmetic — that is real progress and should not be flattened by the count.
Cycle 2 raises 5 new HIGH: one (HIGH-5) found independently by both the reviewer and the
orchestrator, one (HIGH-6) pre-existing and missed by cycle 1, and three (HIGH-7, HIGH-8, HIGH-9)
newly surfaced.

The *class* of defect has narrowed. Cycle 1's HIGHs were architectural — one self-referential design
knot with four faces. Cycle 2's are interface-level: a parameter that does not exist (HIGH-6), a
destination that cannot be addressed (HIGH-5), two predicates that are the wrong mechanical form of a
correct intent (HIGH-7, HIGH-8), and one plan claiming a fix it did not apply (HIGH-9). All five are
local edits to `01-06`, `01-08`, `01-09`, `01-10` and `01-11`. None touches the wave graph, the
module decomposition, or any design decision recorded in CONTEXT.md.

**One pattern worth naming for cycle 3.** Three of the five HIGHs (5, 8, 9) sit on the boundary
between `01-06`'s storage API and the three producers that call it, and two of those (HIGH-5, HIGH-9)
are the MEDIUM-1 memory fix failing at that boundary. `01-06`'s `<output>` block (`:604-611`) already
instructs the executor to record the exact `write_table` / `write_table_from_parts` /
`record_lineage` signatures in its SUMMARY because "plans 01-08, 01-09 and 01-10 all call into them".
That instinct is right and should be pushed one step earlier: the next amendment pass should settle
the full storage call surface — root parameter, staging destination, sort-key contract, and the
part-file merge path — *in `01-06`*, then make 01-08/01-09/01-10 conform, rather than letting each
producer describe a call the API cannot service.
