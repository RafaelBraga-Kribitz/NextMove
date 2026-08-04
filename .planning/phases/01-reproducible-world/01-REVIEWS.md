---
phase: 1
reviewers: []
reviewers_requested: [gemini, codex]
reviewers_failed:
  codex:
    reason: "usage limit exhausted — codex-cli 0.145.0 returned 'You've hit your usage limit … try again at Aug 17th, 2026 11:16 PM' (exit 1, empty output) when requested in review cycle 1. Today is 2026-08-04, so the quota window has not reopened; the lane was not re-attempted this cycle to avoid a known-certain failure. Not a timeout and not a sandbox fault — the error text was captured on stderr."
    substituted_with: none
  gemini:
    reason: "Google free-tier quota exhausted — five invocations attempted, all blocked with HTTP 429 before any model output. Not a 503 (cycle 2's failure mode), not a timeout, and not a prompt-size limit: a 30-byte probe request between attempts 3 and 4 returned normally, proving the CLI, auth and network were healthy. The first attempt (496 KB, full 11-plan set) tripped 'generate_content_free_tier_input_token_count, limit: 250000'; the gemini-cli retry storm that followed then consumed 'generate_content_free_tier_requests, limit: 20'. Attempts 2-4 (192 KB three-plan set, 192 KB with -m gemini-2.5-flash, 130 KB two-plan set with a no-tools directive) were each blocked on the request metric. Attempt 5 (54 KB single-plan set) returned 'limit: 0' for both metrics on gemini-3.1-pro — the daily allocation is fully spent. Root cause of the multiplication: gemini-cli runs agentically and re-sends the full context each turn, so a 33k-token prompt over ~8 turns exceeds the 250k/min input budget on its own."
    attempts:
      - "pass 1 (496 KB, all 11 plans) — blocked: input_token_count limit 250000"
      - "pass A (192 KB, 01-06/01-08/01-09) — blocked: requests limit 20"
      - "pass A retry (192 KB, -m gemini-2.5-flash) — blocked: requests limit 20 (CLI routed to its default model regardless of the flag)"
      - "pass B (130 KB, 01-06/01-09, no-tools directive) — blocked: requests limit 20"
      - "pass C (54 KB, 01-09 only, storage signatures inlined) — blocked: limit 0, allocation exhausted"
  claude:
    reason: "skipped deliberately for reviewer independence — this session runs inside Claude Code, so the claude CLI is not an external reviewer."
reviewer_passes:
  orchestrator_verification: succeeded
  external_reviewer_passes: 0
review_cycle: 3
review_cycle_note: "FINAL convergence cycle before escalation to the user. All findings below carry orchestrator verification only — see '## Verification coverage' for how each was grounded and what that is worth."
reviewed_at: 2026-08-04T15:47:00Z
previous_cycle_commit: ed7a5fc
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
plans_amended_since_cycle_2: [01-01, 01-04, 01-06, 01-08, 01-09, 01-10, 01-11]
plans_unchanged_since_cycle_2: [01-02, 01-03, 01-05, 01-07]
---

# Cross-AI Plan Review — Phase 1: Reproducible World (convergence cycle 3, FINAL)

> **Reviewer availability note — read this before weighing anything below.**
>
> This cycle obtained **zero external reviewer passes**, which is a genuine reduction in review
> strength and is stated up front rather than buried.
>
> - **Codex** was requested in cycle 1 and returned a hard account quota block (`codex-cli 0.145.0`,
>   "You've hit your usage limit … try again at Aug 17th, 2026"). Today is 2026-08-04, so Codex
>   remains unavailable and was not re-invoked.
> - **Gemini CLI 0.52.0** was invoked five times with progressively smaller prompts (496 KB → 192 KB
>   → 192 KB with an explicit model flag → 130 KB → 54 KB) and was blocked by Google's free-tier
>   quota every time. A 30-byte probe request between attempts confirmed the CLI, credentials and
>   network were healthy — the block is quota, not capacity (cycle 2's 503), not a timeout, and not
>   prompt size. The final attempt returned `limit: 0` for both the request and input-token metrics,
>   meaning the account's daily allocation is fully spent.
> - **The `claude` CLI was skipped for reviewer independence**, since this session runs inside
>   Claude Code.
>
> The review was therefore carried out entirely by an **orchestrator verification pass** that read
> every cited line directly in the current plan files. Where cycle 2 could corroborate some findings
> against a reviewer pass, this cycle cannot corroborate any. Weigh the findings on their cited
> evidence, which is why every one of them carries line numbers and a stated mechanism.

## Gemini Review

*No output. Five invocations, all blocked by Google free-tier quota before any model output was
produced. Full per-attempt diagnostics are in the `reviewers_failed.gemini` frontmatter block above.
Not silently dropped, and not substituted with a second orchestrator pass presented as a reviewer.*

## Codex Review

*Not invoked. Account quota block active until 2026-08-17; see the frontmatter.*

---

## Consensus Summary

This cycle is **one reviewer identity** — the orchestrator verification pass — because both external
CLIs were quota-blocked (see the availability note above). Every finding below was grounded by
reading the cited plan lines directly; none is impressionistic, and none is inherited from a prior
cycle's text without re-checking the current line.

The headline result is that **the cycle-2 amendment did the hard architectural work correctly.**
Four of the five cycle-2 HIGHs are cleanly, structurally closed, and two of them (HIGH-5, HIGH-7)
are closed with a quality of reasoning that is above the bar for this project: the staging fix
refused the easy sixth-`Zone` shortcut and built a parallel containment-checked resolver instead,
and the DVC fix replaced a broken universal rule with four separately-checkable rules including a
*positive* requirement that the producer→consumer edges exist, which is the part that makes the
check impossible to satisfy by accident. All four cycle-2 MEDIUMs and one of the two LOWs are fully
closed.

The remaining problem is that the fifth HIGH — HIGH-9, the ingest memory claim — was closed in the
half that was easy to measure and left open in the half that was not. Both halves are the same
recurring pattern the review was asked to hunt: **prose that disagrees with mechanism**. Cycle 1
claimed a flush destination its own API could not address. Cycle 2 claimed streaming while the
mechanism collected. Cycle 3 claims bounded memory while the mechanism moves the full
materialization from Python objects (which the budget test measures) into Arrow (which it does not),
and while a whole-dataframe Pandera sweep — half of the original concern — sits outside the measured
function entirely. That is the third consecutive cycle in which this one requirement, ENG-08's
laptop guarantee, has been asserted in prose ahead of its mechanism.

Two further HIGHs are new and unrelated to that lineage: an ingest-CLI ordering defect that makes
D-21's reject-rate threshold structurally unable to fire on semantic violations, and a type
mismatch in plan 01-10 where the storage layer's read surface and its write surface do not compose.

Verdict: **MEDIUM risk, not execution-ready.** The architecture is sound and the call surface is now
genuinely settled in one place, which is a real improvement over both prior cycles. But four HIGHs
remain, three of them concentrated in the memory-budget lineage that has now survived three
amendment rounds, and one of them (HIGH-13) blocking the features producer outright.

### Agreed Strengths

- **The storage call surface is settled in exactly one plan and the consumers conform to it.**
  `01-06-PLAN.md:158-159` states the principle ("the call surface is settled here, once, and plans
  01-08, 01-09 and 01-10 conform to it rather than each describing its own dialect"), and the three
  consumer plans each carry a `read_first` entry pointing at `01-06-SUMMARY.md` with an explicit
  instruction to call the API *as recorded there, not as sketched here*
  (`01-08-PLAN.md:342-344`, `01-09-PLAN.md:175-178`, `01-10-PLAN.md:196-198`). That instruction is
  the structural answer to the cross-plan drift that produced cycle 1's and cycle 2's HIGHs.
- **HIGH-5 is closed by the right mechanism, not the convenient one.** `01-06-PLAN.md:278-285`
  explicitly rejects widening `Zone` and explains why (a zone is lineage-bearing and DVC-declarable;
  staging is neither), then builds `resolve_staging_path` with the identical
  absolute-resolve-then-assert-descendancy discipline (`:271-276`). `write_part_file` takes no
  `zone` and no `record_lineage` "not by a flag the caller may forget, but because it has no lineage
  parameter at all" (`:169-171`), and the criterion at `:461` asserts exactly that absence.
  `Zone` membership is pinned at `:453`.
- **HIGH-7's replacement criterion is correct against the graph it governs.** Scripted check of the
  four rules at `01-11-PLAN.md:233` against the stage definitions at `01-11-PLAN.md:160-167`: (a)
  outs-vs-outs disjointness holds — no out path is equal to or a parent of another stage's out; (b)
  no stage's deps intersect its own outs; (c) no `data/lineage/` path appears in any deps; (d) two
  producer→consumer edges exist (`simulate.outs data/raw/` = `ingest.deps data/raw/`, and
  `ingest.outs data/canonical/` = `features.deps data/canonical/`). The `must_haves` truth at
  `01-11-PLAN.md:29` was corrected to match. Rule (d) being a *positive* requirement is the detail
  that matters: it means the other three cannot be satisfied by declaring a disconnected graph.
- **HIGH-8's fix is grounded in the tables that actually exist.** `01-06-PLAN.md:300-308` enumerates
  the three composite-key tables and shows the tuple is unique in each, and notes the degenerate
  case ("where a table has a single-column key … the tuple check degenerates to the column check, so
  nothing is lost"). The two previously key-less ground-truth tables now declare keys at
  `01-08-PLAN.md:429-431`, and `01-08-PLAN.md:539` asserts them by name.
- **HIGH-6's plumbing is complete on the read side as well as the write side.** All eight
  disk-touching functions carry `root` (`01-06-PLAN.md:465`), `DATA_ROOT` is re-anchored to
  `Path(__file__)` with the reason stated (`:251-258`), and — the part that makes it a real
  experiment — `01-11-PLAN.md:283-290` explicitly refuses to drive the two-root test through
  `dvc repro`, because the pipeline writes to the default root by design, and drives it through
  `--out` on the three stage modules instead.
- **MEDIUM-3's fix carries its own structural enforcement.** Moving the uplift cadence into
  `SimulatorConfig` (`01-08-PLAN.md:362-373`) makes it a top-level `simulator:` key, which brings it
  inside `01-11-PLAN.md:463`'s doc-floor check automatically — and `01-11-PLAN.md:464` says so
  explicitly. `01-08-PLAN.md:412-417` states the converse rule for `flush_every_ticks` and explains
  why the two knobs are treated differently. That is a principled distinction, not an ad-hoc one.
- **The wave graph and file ownership survive the amendment.** `01-08-PLAN.md:14-15` correctly adds
  `src/nextmove/config/models.py` and `config/simulator.yaml` to `files_modified` for the MEDIUM-3
  fix, and 01-03 (which owns those files) has no criterion pinning an exhaustive `SimulatorConfig`
  field set — `01-03-PLAN.md:188` asserts the module *defines all of* a class list, which is
  additive. The three plans untouched since the cycle-1 replan (01-02, 01-03, 01-07) contain no
  storage-API call site at all — a grep for `write_table|read_table|table_exists|query(|record_lineage|resolve_table_path|Zone\.|DATA_ROOT|out_root`
  across them returns exactly one hit, `01-07-PLAN.md:350`, which is a prose cross-reference in a
  threat-model row and depends on no signature. **The broad `root` signature change orphaned
  nothing.**
- **LOW-3 was fixed without collateral damage.** `01-01-PLAN.md:36`, `:231` and `:235` now say
  eleven, and `:235` adds "trust the list rather than any summary word". The surviving "ten" at
  `:78` and `:106` refers to the ten *dependency* packages in the Legitimacy Audit, not the eleven
  ENG-01 packages — checked, and correct in its own context.

### Agreed Concerns

---

**HIGH-10 (NEW) — `write_table_from_parts` concatenates every part into one Arrow table, so the
merge step's peak allocation is the whole table; both memory budgets assert only `tracemalloc`, and
both plans justify that exclusion with a claim that is false of this function.**

*Orchestrator finding. No external reviewer pass was obtained this cycle.*

`01-06-PLAN.md:381-383` specifies the merge literally: it "reads the supplied Parquet part files in
the given order through `read_parquet_file`, **concatenates them into one Arrow table**, applies the
`dedupe_on` reduction if one is given, and hands the result to the identical `write_parquet_atomic`
call". `write_parquet_atomic` then sorts (`01-06-PLAN.md:293-294`), producing a second full-size
buffer, and `dedupe_on` sorts and groups again (`:389-391`). Peak allocation at the merge is
therefore a small multiple of the entire table — not of one part.

Plan 01-06 is itself careful about this. `01-06-PLAN.md:385-386` says the function exists so a
producer "can bound its **peak Python heap** by flushing periodically", and `:393-395` says the
producer "never has to union its parts **as live Python objects**". Both statements are true and
narrowly scoped. The two consumer plans then widen them into a claim about laptop memory that the
mechanism does not support:

| Where | What it says | Why it is false of the merge |
|---|---|---|
| `01-08-PLAN.md:481-483` | "`tracemalloc` measures Python object allocation specifically, which is the quantity at risk here — Arrow's buffers are off-heap and are **bounded separately by the part-file size**" | The merge holds *all* parts concurrently, so the Arrow buffer is bounded by the total, not by a part |
| `01-09-PLAN.md:307-309` | "Arrow's merge buffers are off-heap and **bounded separately by the part-file set**" | "Bounded by the set" is bounded by the whole thing; the phrase reads as a bound but states none |
| `01-08-PLAN.md:632` (T-01-34) | Threat is "Full-scale run exhausting **laptop memory**"; mitigation concludes "peak **Python heap** tracks the flush window" | The threat is stated in RSS terms and the mitigation is proven in tracemalloc terms |
| `01-09-PLAN.md:574` (T-01-37) | Threat is "Ingest exhausting laptop memory **by materializing the whole event history to deduplicate and sort it**"; mitigation moves exactly that materialization into `write_table_from_parts` | The mitigation relocates the named hazard out of the measurement rather than removing it |

The measurement is structurally blind by construction. `01-08-PLAN.md:531` and `01-09-PLAN.md:340`
assert peak **traced** heap only. The one place RSS appears — `01-08-PLAN.md:497-499` — says to
"record process RSS alongside the traced heap and **report both in the failure message**". Recording
and reporting is not asserting; nothing goes red on RSS. The sub-linear-growth assertions
(`01-08-PLAN.md:485-487`, `01-09-PLAN.md:311-314`) are also tracemalloc-based, so they would confirm
sub-linear *Python* growth over a design whose Arrow footprint grows strictly linearly.

Scale, from the plans' own numbers: `01-08-PLAN.md:394` estimates "tens of millions of live Pydantic
objects" for `n_customers: 50000` over `horizon_days: 548`, and `01-08-PLAN.md:429-430` /
`01-11-PLAN.md:429-430` put `ground_truth_uplift` near 7.2 million rows. Concatenating tens of
millions of event rows into one Arrow table, then sorting it, is precisely the allocation ENG-08
exists to forbid, and both budget suites would pass while it happened.

This is the third consecutive cycle in which ENG-08's laptop guarantee has been asserted ahead of
its mechanism (cycle 1: an unaddressable flush destination; cycle 2: a collect-then-write landing
step; cycle 3: an unmeasured Arrow merge). The pattern is not carelessness — each amendment fixed a
real defect — but the measurement has moved with the claim each time, so the suite has never been
able to falsify it.

*Smallest fix:* two changes, both in `01-06`. First, state how `write_table_from_parts` bounds its
own footprint — a streaming `pyarrow.parquet.ParquetWriter` over row-group batches, or a DuckDB
`COPY (SELECT … ORDER BY …) TO` over the part files through the existing single-threaded connection,
either of which keeps the merge out-of-core; then say so where the two consumer plans currently
claim it. Second, add an assertion that can actually fail: make peak process RSS (not traced heap) a
red/green criterion in `01-08-PLAN.md:531` and `01-09-PLAN.md:340`, skipping with a stated reason
only where the platform provides no reading. A budget that cannot fail is not a budget.

---

**HIGH-11 (NEW) — plan 01-09's semantic gates are a whole-dataframe Pandera sweep over the landed
events, run outside `ingest_events` and outside the budget test — which is the exact half of the
original memory concern that three cycles of batching fixes have never touched.**

*Orchestrator finding.*

The concern this lineage started from is quoted in the plan itself. `01-09-PLAN.md:116-119`: "The
reviewer noted that per-row Pydantic validation **followed by a whole-dataframe Pandera sweep** is
robust but potentially slow and memory-hungry over the full 50k-customer history." Every amendment
since has addressed the first clause. The second clause is untouched, and is now load-bearing:

- `01-09-PLAN.md:407` declares `run_semantic_gates(events_df, catalog_df, config)` — a dataframe of
  events plus the catalog, not an iterator and not a batch.
- `01-09-PLAN.md:471-472` places the call in the CLI: it "runs `ingest_events`, runs
  `run_semantic_gates` **over the landed events**". The landed events are the entire canonical
  table.
- The gates are inherently cross-row as specified: `01-09-PLAN.md:395-396` groups by `session_id`
  across the frame, `:403-405` builds a membership set from the whole catalog, and `:388` runs every
  schema with `lazy=True` "so all violations are collected in one pass" — which also means every
  failure case is retained for the whole sweep.
- `must_haves` truth `01-09-PLAN.md:30` requires that "every row is still validated by both the
  contract **and the semantic gates**", so the sweep cannot be sampled or scoped down without
  breaking a stated truth.

And the budget test cannot see it. `01-09-PLAN.md:305-306` runs "the `demo` profile's simulator
output through **`ingest_events`** under `tracemalloc`" — `ingest_events`, not the CLI, and
`run_semantic_gates` is not called from `ingest_events` anywhere in Task 1's action
(`01-09-PLAN.md:207-296`). So `must_haves` truth `01-09-PLAN.md:32` — "Peak Python heap during
ingest is bounded by the batch size rather than by the input length, asserted by a test with a
stated budget" — is asserted over a function that excludes the largest allocation on the ingest
path. Note this is *not* an import-contract problem: `01-04-PLAN.md:170-172` explicitly permits
dataframe libraries anywhere ("only the Parquet and DuckDB I/O surface is confined"). It is purely a
memory and measurement problem.

*Smallest fix:* state in `01-09` how each gate is evaluated without a whole-history frame — the
monotonicity gate is per-`session_id` and the referential-integrity gate is a membership test
against a set built once, so both are expressible per batch inside the existing batch loop with the
catalog set hoisted out; the price gate is already per-row. Move the gate call inside
`ingest_events` so semantic rejects join the same part-file flush as contract rejects (which also
closes HIGH-12), and extend `tests/integration/test_ingest_budget.py` to measure the full CLI path
rather than `ingest_events` alone.

---

**HIGH-12 (NEW) — semantic rejects are produced after `ingest_events` has already returned and
landed the canonical table, so D-21's reject-rate threshold can never fire on a semantic violation,
semantically-invalid rows stay in `events`, and no storage call is specified for writing them.**

*Orchestrator finding.*

The CLI sequence is stated in one sentence at `01-09-PLAN.md:470-474`: it "runs `ingest_events`,
runs `run_semantic_gates` over the landed events, quarantines any semantic violations into the same
rejects table, calls `evaluate_reject_rate`, prints the summary line, and exits non-zero when the
threshold was exceeded or a fail-fast gate failed." Trace each consequence:

1. **The threshold cannot see semantic rejects.** `evaluate_reject_rate(result: IngestResult,
   config)` raises "when `result.reject_rate` exceeds `config.max_reject_rate`"
   (`01-09-PLAN.md:459-461`). `result` is the `IngestResult` built inside `ingest_events`
   (`01-09-PLAN.md:218-220`), which returns before any gate runs. `reject_rate` therefore counts
   contract rejects only. `must_haves` truth `01-09-PLAN.md:26` — "A configurable reject-rate
   threshold fails the run when exceeded, so slow silent degradation cannot hide behind a successful
   run computed on partial data" — is false for exactly the degradation class DATA-03 exists to
   catch. Only a gate explicitly marked fail-fast escapes this, and the DATA-03 flagged assumption
   at `01-09-PLAN.md:82` states plainly that the intended default is the opposite: "semantic
   failures quarantine their rows with a reason, and the run fails only when the resulting reject
   rate exceeds the configured threshold".
2. **Semantically-invalid rows remain in the canonical table.** Contract rejects are kept out by
   construction (`01-09-PLAN.md:194`, `:235-239`). Semantic violations are detected only after the
   merge has already landed `events` (`01-09-PLAN.md:256-262`), and nothing in the plan removes,
   rewrites or re-merges the canonical table afterwards. A row therefore appears in `events` *and*
   in `rejects` — which makes "quarantine" nominal, and contradicts `must_haves` truth
   `01-09-PLAN.md:23` ("quarantined into a rejects table … rather than silently dropped or
   coerced") in spirit and DATA-03's "gates that fail the run" in letter.
3. **`IngestResult.gates_passed` / `gates_failed` are never populated.** They are declared at
   `01-09-PLAN.md:219`, but the only function that constructs an `IngestResult` never runs a gate.
   `format_dq_summary(result, gate_results)` (`01-09-PLAN.md:465`) takes gate results as a *separate*
   argument, which is the tell that the two halves were designed apart. Two always-empty fields on a
   frozen public model is a small thing; it is cited because it corroborates the ordering defect
   rather than as a finding of its own.
4. **No storage call is specified for the second rejects write.** `ingest_events` finishes by
   merging the rejects parts and then calling `clear_staging(root=out_root)` "so no part file
   outlives the run" (`01-09-PLAN.md:271-276`). The CLI must then write additional reject rows into
   "the same rejects table" with the staging tree already gone. `01-09-PLAN.md:531-535`'s inventory
   of storage calls this plan makes does not include that write. An executor has no specified route.

The acceptance criteria do not catch any of this, because the only end-to-end assertion is
`01-09-PLAN.md:497` — "a `tiny`-profile simulator-only run ingests with `rows_quarantined == 0` and
no failed gate" — and `rows_quarantined` is the contract-only counter on a run designed to produce
zero of both.

*Smallest fix:* run the gates inside `ingest_events`, per batch, before the part-file flush, so a
semantic failure diverts its row into the rejects part instead of the events part and is counted in
the single `IngestResult` that `evaluate_reject_rate` then reads. That makes quarantine real, makes
the threshold cover both stages, populates `gates_passed`/`gates_failed` from the one place that
builds the result, and removes the need for any post-hoc rejects write. It also composes with
HIGH-11's fix rather than competing with it.

---

**HIGH-13 (NEW) — plan 01-10's `materialize_grid` composes `query`'s Arrow return value into
`write_table`'s row-iterable parameter; the two declared types do not compose, and the only literal
route between them is a full Python round-trip of the largest table the phase produces.**

*Orchestrator finding.*

`01-10-PLAN.md:252-256` specifies `materialize_grid` as: build the full daily grid, "run the
identical composed SQL, and write `feature_grid` into `Zone.features` **through `write_table`**".
The SQL runs through the storage layer's `query` (`01-10-PLAN.md:249`, `:266`), and
`01-06-PLAN.md:428` declares `query(sql: str, root: Path | None = None, **table_bindings) -> Table`
— an Arrow table. But `01-06-PLAN.md:357-358` declares `write_table`'s first parameter as
"`rows` (an iterable of Pydantic models or mappings)", converted "to a `pyarrow.Table` with an
explicitly constructed schema — never inferred from the first record".

There is no declared adapter between the two. The executor has three routes and each breaks
something:

| Route | What it breaks |
|---|---|
| `write_table(grid.to_pylist(), …)` | Materializes the whole grid as Python dicts. `01-10-PLAN.md:309` states the row count is "the number of active customers times the configured horizon days" — 50 000 × 548 ≈ 27.4 M rows at the shipped default. This is the ENG-08 hazard, on the one producer with **no** memory budget: 01-10 contains no `tracemalloc`, heap or wall-clock criterion anywhere |
| Extend `write_table` to accept an Arrow table | Invents public storage API from a consumer plan, which `01-06-PLAN.md:158-159` exists to forbid ("the call surface is settled here, once, and plans 01-08, 01-09 and 01-10 conform to it rather than each describing its own dialect") |
| Have `features/` write Parquet itself | Breaks `01-04-PLAN.md`'s second import contract; `01-10-PLAN.md:239-246` explicitly forecloses this |

The plan half-notices the gap. `01-10-PLAN.md:238` gives `compute_as_of` the return type `Table` and
spends eight lines (`:239-246`) on why the annotation must go through the `nextmove.storage` alias —
so the Arrow-typed *read* path was carefully designed. The Arrow-typed *write* path was not: nothing
in 01-06's surface accepts an Arrow table as input except `write_table_from_parts`, which takes
*paths*, not tables.

This is the same shape as cycle 1's HIGH-5 — a producer describing a call the storage API cannot
service — and it is the reason HIGH-5's lesson ("`01-08` cannot invent public storage API") was
written down. It reappeared in the one producer plan that cycle 2's storage amendment touched least.

*Smallest fix:* add a declared Arrow-input write to `01-06`'s surface —
`write_arrow_table(table: Table, table_name, zone, sort_key, resolved_config, producer_stage,
input_paths=(), record_lineage=True, root=None)` sharing `write_parquet_atomic` with `write_table`,
with `write_table` documented as the row-iterable convenience wrapper over it — and change
`01-10-PLAN.md:254` to call it. Add a peak-memory criterion to `01-10` while doing so; it is
currently the only producer of a horizon-scale table with no budget at all.

---

**MEDIUM-7 (NEW) — `write_table_from_parts` has no defined behaviour for an empty `part_paths` list,
yet two plans carry acceptance criteria that require one.**

*Orchestrator finding.*

`01-06-PLAN.md:224` states the contract for "N part files" and `:455` and `:463` exercise three and
ten parts respectively. Zero parts is never mentioned, and it is the case that determines the
schema: with no part to read, `read_parquet_file` yields nothing to concatenate and there is no
source for the Arrow schema at all.

Two criteria depend on the answer. `01-09-PLAN.md:334`: "A test asserts an empty input produces an
existing, empty `events` table and an existing, empty `rejects` table" — and under
`01-09-PLAN.md:256-262` the `events` table is produced *only* by the part merge, so with zero
batches there are zero parts. `01-11-PLAN.md:26` states the same property as a phase-level truth ("A
pipeline stage that receives zero input rows writes a zero-row Parquet file carrying the full schema
rather than a missing file"), and `01-11-PLAN.md`'s Task 2 empty assertion tests it end to end.

The rejects path already has the answer written down — `01-09-PLAN.md:273-275`: "Write the table
even when it is empty — call `write_table` with an empty row set in that case" — and `write_table`
constructs its schema explicitly (`01-06-PLAN.md:357-358`), so it handles zero rows fine. The events
path never states the equivalent fallback.

*Smallest fix:* one sentence in `01-06-PLAN.md` near `:381` stating that `write_table_from_parts`
with an empty `part_paths` writes a zero-row table carrying the explicitly constructed schema (or
raises, if that is the intent), and one sentence in `01-09-PLAN.md` near `:256` applying the same
empty-set fallback to `events` that `:273-275` already applies to `rejects`.

---

**MEDIUM-8 (NEW) — plan 01-08 Task 3 sequences a whole-root `clear_staging` before the second table
is flushed, which makes one of its own acceptance criteria unsatisfiable and puts the uplift parts
one reordering away from deletion.**

*Orchestrator finding.*

`01-08-PLAN.md:399-401` ends the `events_raw` sequence with: "merge them into the single sorted
`events_raw` table with `write_table_from_parts`, and call `clear_staging(root=out_root)` to remove
the staging tree." `clear_staging` with no `part_dir` "removes … the whole staging root"
(`01-06-PLAN.md:421-422`). `ground_truth_uplift` is flushed *later* in the same action —
`01-08-PLAN.md:444-445`: "Flush this table in parts on the same mechanism as `events_raw`, using
`part_dir="ground_truth_uplift"`."

Read literally, the sequence is: flush events parts → merge → delete the entire staging root → …
later … → flush uplift parts → merge → (no second cleanup stated). Two consequences:

1. `01-08-PLAN.md:535` asserts that "during a `tiny` run `data/_staging/events_raw/` and
   `data/_staging/ground_truth_uplift/` **both contain part files mid-run**". Under the stated
   sequence the events parts are deleted before the first uplift part is written, so there is no
   instant at which both hold parts. The criterion cannot go green.
2. `01-08-PLAN.md:527` asserts `data/_staging/` does not exist after the run, but no cleanup is
   stated after the uplift merge — so the run as written would leave `data/_staging/ground_truth_uplift/`
   behind, which would also break `01-11-PLAN.md:296-297`'s twelve-file discovery assertion.

The intended design is obvious (flush both, merge both, one `clear_staging` at the end) and
`01-06-PLAN.md:421` even provides the scoped `clear_staging(part_dir=…)` form for the alternative.
The plan just does not say which.

*Smallest fix:* move the `clear_staging(root=out_root)` call in `01-08-PLAN.md:401` to after the
`ground_truth_uplift` merge and say so explicitly, or scope both calls with `part_dir`; then restate
`:535` against whichever ordering is chosen.

---

**MEDIUM-9 (NEW) — the `ingest` and `features` DVC stages declare no dependency on
`src/nextmove/storage/` or `src/nextmove/config/`, so a storage-layer change that alters their
output but not `data/raw/` leaves both stages reported up to date.**

*Orchestrator finding.*

`01-11-PLAN.md:160-167` declares the three stages. `simulate` depends on `config/`,
`src/nextmove/simulator/`, `src/nextmove/config/` **and** `src/nextmove/storage/`. `ingest` depends
on `data/raw/`, `src/nextmove/ingest/` and `config/data_quality.yaml`. `features` depends on
`data/canonical/`, `src/nextmove/features/` and `config/features.yaml`. Neither of the latter two
lists the storage or config packages.

Most changes cascade anyway, because a storage change usually alters `data/raw/` and DVC then
invalidates downstream. The uncovered case is a change confined to a code path the simulator does
not exercise. The clearest example is inside this very phase: `dedupe_on`'s tie-break rule
(`01-06-PLAN.md:389-393`) is used only by `ingest`; changing which row survives a duplicate group
changes `data/canonical/events.parquet` and leaves `data/raw/` byte-identical, so `dvc repro` would
report `ingest` up to date over a stale canonical table. `query`'s `PRAGMA threads=1`
(`01-06-PLAN.md:339-343`) is the analogous case for `features`.

That is a reproducibility hole in the plan whose entire purpose is `ENG-09` staleness detection, and
`01-11-PLAN.md`'s idempotency criteria (`:240-241`, the twice- and thrice-repeated `dvc.lock`
comparisons) would all stay green through it.

*Smallest fix:* add `src/nextmove/storage/` and `src/nextmove/config/` to both the `ingest` and
`features` stage `deps` in `01-11-PLAN.md:163-167`. This does not touch any of the four HIGH-7
rules — those packages are nobody's `outs`, so outs-vs-outs disjointness, the own-out rule, the
lineage rule and the two-edge requirement are all unaffected.

---

**MEDIUM-10 (NEW) — plan 01-10 requires `write_table` to stamp `FEATURE_SET_VERSION`, but
`write_table` stamps a closed metadata set "and nothing else" and exposes no parameter for extra
metadata.**

*Orchestrator finding.*

`01-06-PLAN.md:361-362`: "Stamp key-value metadata with the config hash, the sorted list of input
*table names*, the `producer_stage`, and `CONTRACT_VERSION` — **and nothing else**." The signature at
`:355-356` has no metadata parameter.

`01-10-PLAN.md:254-256` nonetheless instructs the executor to write `feature_grid` "through
`write_table` … **stamping the config hash and `FEATURE_SET_VERSION`**". `FEATURE_SET_VERSION` is a
real, load-bearing constant in that plan — a sha256 over the resolved feature set
(`01-10-PLAN.md:161`), exported at `:41`, tested for stability at `:178`, and printed by the CLI at
`:291`. There is no route for it into the table's metadata through the declared API.

Rated MEDIUM rather than HIGH because no acceptance criterion asserts the stamp lands in the file —
a grep of `01-10-PLAN.md` for `FEATURE_SET_VERSION` returns `:41`, `:123`, `:161`, `:178`, `:256`,
`:291`, `:432` and `:490`, none of which is a metadata assertion. So an executor can proceed without
a red test, which is exactly why it will be silently dropped.

*Smallest fix:* either add an optional `extra_metadata: Mapping[str, str] | None = None` parameter to
`write_table` in `01-06` (and state that it is merged into, never overrides, the closed set), or
delete the `FEATURE_SET_VERSION` stamping clause from `01-10-PLAN.md:255-256` and record the version
in the lineage row instead. Whichever is chosen, add the criterion that asserts it.

---

**LOW-5 (NEW) — the phase's `justfile` recipe inventory is stated in three places and no two agree.**

*Orchestrator finding. Same family as cycle-2's LOW-4, which was only half-closed.*

Counting the recipes each plan declares: `default`, `setup`, `fmt`, `lint`, `test`, `reproduce`
(01-01, `01-01-PLAN.md:293`), `ci` (01-04, `01-04-PLAN.md:348`), `simulate` and `budget` (01-08,
`01-08-PLAN.md:464-465`), `ingest` (01-09, `:479`), `features` (01-10, `:290`), `lineage` and
`clean` (01-11, `:202`) — **thirteen**.

- `01-11-PLAN.md:247` enumerates twelve of them and calls the total "twelve recipes", omitting
  `default`. `just --list` does list `default`, since `01-01-PLAN.md:194` declares it as a public
  first recipe.
- `01-04-PLAN.md:137-138` still says "plans 01-08, 01-09 and 01-10 each append **one** stage recipe".
  01-08 appends two — `budget` is the recipe cycle-2's LOW-4 added.

Non-blocking: `01-11-PLAN.md:247` says "lists", not "lists exactly", so an extra recipe fails
nothing. Recorded because 01-11 is the phase's inventory of record and this is the second cycle in
which it has been wrong.

*Smallest fix:* add `default` to `01-11-PLAN.md:247` and change "twelve" to "thirteen"; change "each
append one stage recipe" to "01-08 appends two (`simulate` and `budget`), 01-09 and 01-10 one each"
at `01-04-PLAN.md:137-138`.

---

**LOW-6 (NEW) — two call-site descriptions name an argument the declared signature does not take,
and one derivation the storage layer must perform is never stated.**

*Orchestrator finding.*

- `01-06-PLAN.md:355` declares the parameter `resolved_config`. `01-09-PLAN.md:260` instructs the
  executor to pass "**the resolved config hash**", and `01-10-PLAN.md:255` says "stamping the config
  hash". A literal reading passes a `str` where a `ResolvedConfig` is expected. Low because
  `read_first` in both plans (`01-09-PLAN.md:175-178`, `01-10-PLAN.md:196-198`) directs the executor
  to the recorded signature, which wins — but the drift is the same species that produced two HIGHs.
- `write_table` receives `input_paths: Sequence[Path]` (`01-06-PLAN.md:356`) and must stamp "the
  sorted list of input **table names**" (`:361-362`) and populate `LineageRecordDraft.input_tables:
  list[str]` (`:523`). No plan states how a table name is derived from a path. The obvious answer is
  the filename stem, but it is unstated, and `01-06-PLAN.md:598` pins `record_lineage`'s parameter
  tuple exactly, so an executor cannot resolve it by adding a parameter.

*Smallest fix:* change "the resolved config hash" to "the `ResolvedConfig`" at `01-09-PLAN.md:260`
and `01-10-PLAN.md:255`; add one clause at `01-06-PLAN.md:362` stating that the input table name is
the destination filename stem.

---

### Cycle-2 finding disposition

| Cycle-2 finding | Verdict | Grounding (current line numbers) |
|---|---|---|
| **HIGH-5** flush destination `data/_staging/` unreachable | **FULLY RESOLVED** | Sibling staging root, not a sixth `Zone` (`01-06:268-285`); `resolve_staging_path` with the same containment discipline (`:271-276`); `write_part_file` with no `zone` and no `record_lineage` parameter (`:399-413`); `list_part_files` (`:415-419`), `clear_staging` (`:421-424`). Criteria `:453` (Zone still five members), `:460-464`. Consumers call it: `01-08:397-398`, `01-09:244-246`. `.dvcignore` covers it (`01-06:579-582`), and `01-11:172` forbids adding it to any stage. |
| **HIGH-6** `out_root` declared, never plumbed | **FULLY RESOLVED** | `root` on all eight disk-touching functions, asserted by an `inspect.signature` sweep over all eight (`01-06:465`); forwarded to `resolve_table_path`, `resolve_staging_path` and `record_lineage` (`:345-353`); `DATA_ROOT` anchored to `Path(__file__)` with the two-experiments reason stated (`:251-258`) and pinned by a two-working-directory subprocess test (`:468`). Producers forward it (`01-08:383-390`, `01-09:229-233`, `01-10:266-271`), all three CLIs expose `--out` (`01-08:454-459`, `01-09:470-478`, `01-10:288-291`), and `01-11:283-290` drives the two-root test through those CLIs rather than through `dvc repro`, with the reason stated. |
| **HIGH-7** DVC non-overlap criterion failed on its own `dvc.yaml` | **FULLY RESOLVED** | Four separate rules at `01-11:233`, verified by hand against the stage graph at `:160-167`: outs-vs-outs disjoint ✓, no stage deps on its own outs ✓, no lineage path in any deps ✓, two producer→consumer edges present ✓. The `must_haves` truth at `:29` was rewritten to match, and `:169-183` explains why the over-generalization was wrong. |
| **HIGH-8** sort-key uniqueness violated by 3 of 9 tables | **FULLY RESOLVED** | Precondition is now on the tuple (`01-06:293-297`), with the three composite-key tables enumerated and shown unique (`:300-308`). The two previously key-less ground-truth tables declare keys (`01-08:429-431`) and a criterion names them (`01-08:539`). Positive and negative criteria both present (`01-06:458-459`); golden tests write both composite fixtures (`:717`). |
| **HIGH-9** 01-09 claimed streaming, did not apply it | **PARTIALLY RESOLVED** | The Python-object half is genuinely fixed and is not a paper fix: per-batch `write_part_file` (`01-09:244-246`), the pre-existing canonical table prepended as an input part rather than read into memory (`:256-258`), `dedupe_on="event_id"` moving the reduction into the storage layer (`:259-269`), a streaming criterion that is now satisfiable and says why (`:337`), a "the tool is actually used" grep criterion (`:338`), and a new budget suite (`:298-322`). What remains open is that the materialization was **relocated, not removed** — into `write_table_from_parts`'s Arrow concat, which no test measures (**HIGH-10**) — and that the whole-dataframe Pandera half of the original concern was never addressed (**HIGH-11**). Filed separately; **not double-counted here**. |
| **MEDIUM-3** uplift cadence a code literal | **FULLY RESOLVED** | `uplift_snapshot_every_ticks` added to `SimulatorConfig` and `config/simulator.yaml` (`01-08:362-373`), read from `ResolvedConfig` at `:436-437`, `FLUSH_EVERY_TICKS` deliberately left as a constant with the converse reasoning stated (`:412-417`). `01-08:14-15` declares the two 01-03-owned files in `files_modified`, and 01-03 has no exhaustive-field criterion that this breaks. |
| **MEDIUM-4** cadence never reaches the reviewer-facing doc | **FULLY RESOLVED** | `01-11:426-434` requires the cadence, its default, the ~7.2 M row count, the 219 M per-tick alternative and the "function remains callable" honesty clause under `## Known Limitations`; `:465` asserts it by grepping that section for `uplift_snapshot_every_ticks`; and `:463-464` records that the config-key floor check now reaches it structurally, which is the mechanism MEDIUM-4 said was missing. |
| **MEDIUM-5** append-only invariant vacuous under `dvc repro` | **FULLY RESOLVED** | Both semantics stated in the plan (`01-09:278-288`), in the `must_haves` truth (`:29`), in the flagged assumption (`:77`) and required in the module docstring with a grep criterion (`:342`); `01-11:185-192` states the non-persistent-out reasoning and `:242` adds the `dvc repro --force` digest criterion that tests the property in the mode that ships, plus `:243` asserting no `persist` flag exists. |
| **MEDIUM-6** `pyarrow.Table` annotation breaches the import contract | **FULLY RESOLVED** | Public `Table` alias declared and re-exported (`01-06:329-337`), criterion `01-06:469` proves `Table is pyarrow.Table`; `01-10:238-246` annotates against it and forecloses the `TYPE_CHECKING` route explicitly, with criteria at `:310` and `:312` (the latter asserting the annotation resolves, so it is not a dangling name); `01-04` decides the open SIM-02 edge, adds a `must_haves` truth forbidding any ignore rule or `TYPE_CHECKING` allowance, and updates the flagged assumption to record which half is now closed. |
| **LOW-3** "ten" vs eleven packages | **FULLY RESOLVED** | `01-01:36`, `:231`, `:235` all say eleven, and `:235` adds "trust the list rather than any summary word". The remaining "ten" at `:78` and `:106` refers to the ten dependency packages in the Legitimacy Audit — checked, correct in context. |
| **LOW-4** `budget` recipe missing from the 01-11 inventory | **PARTIALLY RESOLVED** | `budget` is now listed at `01-11:247`. The inventory as a whole is still wrong: it counts twelve where the justfile has thirteen (`default` omitted), and `01-04:137-138` still says 01-08 appends one recipe when it appends two. Filed as **LOW-5**. |

### Divergent Views

No second reviewer identity was obtained this cycle, so there is no reviewer-versus-orchestrator
divergence to record. The one divergence worth carrying forward is **between cycles**: Gemini's
cycle-1 and cycle-2 passes both rated this phase LOW risk and called the architecture close to
flawless. That reading remains defensible about the *architecture* — the storage design, the lineage
anti-forgery contract, the DVC ownership model and the import boundary are all genuinely strong, and
this cycle's amendment strengthened them further. The orchestrator's MEDIUM rating is a verdict on
*execution-readiness*: four HIGHs remain, three of them (HIGH-10, HIGH-11, HIGH-13) would surface
only when an executor runs a criterion or a full-scale profile and finds it cannot go green, and one
(HIGH-12) is a correctness defect that no criterion in the phase would catch. A reader comparing
cycles should not read the two ratings as contradictory.

---

## Verification coverage

Every finding in this cycle carries **orchestrator verification only**. No external reviewer pass
was obtained: Codex remains account-quota-blocked until 2026-08-17, the `claude` CLI was skipped for
reviewer independence, and all four Gemini attempts were blocked by Google's free-tier quota (see
the availability note in the frontmatter and at the top of this file). This is a real reduction in
review strength relative to cycles 1 and 2, and it is recorded rather than papered over.

To compensate, every cited line was read directly in the current file rather than carried forward
from a prior cycle's text, and the following checks were scripted or performed exhaustively rather
than sampled:

| Check | Method | Result |
|---|---|---|
| Cycle-2 amendment scope | `git show --name-only ed7a5fc` | Exactly 01-01, 01-04, 01-06, 01-08, 01-09, 01-10, 01-11 — matches the changelog claim |
| Orphaning of untouched plans by the `root` signature change | grep for every storage symbol across 01-02, 01-03, 01-05, 01-07 | One hit total (`01-07:350`), a prose cross-reference depending on no signature. **Nothing orphaned** |
| All eight `root` parameters | Read `01-06:355-433` and `:465` against every call site in 01-08, 01-09, 01-10, 01-11 | Consistent; the only drift found is the `resolved_config` wording in LOW-6 |
| New staging API declared before use | `write_part_file`, `list_part_files`, `clear_staging`, `resolve_staging_path`, `dedupe_on` traced from 01-06 declaration to 01-08/01-09 use | All five declared in 01-06 first; signatures and uses agree |
| 01-06 export lists | `01-06:40`, `:47`, `:51` against the functions declared in the action blocks | Complete; every new name is exported |
| HIGH-7's four DVC rules | Applied by hand to the stage graph at `01-11:160-167` | All four pass |
| Sort-key tuple uniqueness | Every one of the nine tables checked against its declared key | All nine unique as tuples |
| `just` recipe inventory | Counted across all six plans that touch the justfile | Thirteen; 01-11 says twelve (LOW-5) |
| Every acceptance criterion in 01-06, 01-08, 01-09, 01-10, 01-11 | Read against the design in the same plan set | Four found unsatisfiable or unmeasurable: `01-08:535` (MEDIUM-8), `01-09:334` (MEDIUM-7), and the two heap criteria `01-08:531` / `01-09:340` which are satisfiable but cannot fail on the hazard they name (HIGH-10) |
