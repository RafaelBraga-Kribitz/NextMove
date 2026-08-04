---
phase: 01-reproducible-world
plan: 06
subsystem: database
tags: [pyarrow, duckdb, parquet, dvc, pydantic, lineage]

requires:
  - phase: 01-01
    provides: uv-managed project skeleton, src/nextmove/storage/ package boundary stub
  - phase: 01-02
    provides: "ADR-007: DVC + MLflow ratified as the artifact-versioning mechanism (closes OD-7)"
  - phase: 01-03
    provides: nextmove.config.loader.load_config / ResolvedConfig / config_hash
  - phase: 01-04
    provides: import-linter contract confining pyarrow/duckdb to nextmove.storage
provides:
  - "write_table / write_table_from_parts / write_part_file / write_query_to_part / read_table / table_exists / query / connect, all root-addressable"
  - "content-hash lineage: record_lineage / read_lineage / print_lineage_chain, anti-forgery by construction"
  - "DVC initialized (no remote, no telemetry), .dvcignore covering the staging root"
  - "nextmove.storage.Table alias for pyarrow-free Arrow annotations"
affects: [01-08, 01-09, 01-10, 01-11]

tech-stack:
  added: []
  patterns:
    - "single streaming Parquet writer (write_parquet_stream) as the one site Parquet bytes are produced"
    - "out-of-core DuckDB merge (read_parquet + ORDER BY + optional QUALIFY) instead of Arrow concatenation"
    - "content hashes computed by the recorder from disk bytes, never accepted from the producer"

key-files:
  created:
    - src/nextmove/storage/paths.py
    - src/nextmove/storage/_parquet.py
    - src/nextmove/storage/repository.py
    - src/nextmove/storage/lineage.py
    - tests/golden/test_deterministic_write.py
    - tests/integration/test_lineage.py
    - .dvcignore
    - .dvc/config
  modified:
    - src/nextmove/storage/__init__.py

key-decisions:
  - "rows-to-Arrow schema is derived from the Pydantic model class (type(rows[0])), never from data values, and every field is declared nullable so write_table and write_table_from_parts agree byte-for-byte with DuckDB's own read_parquet->Arrow output"
  - "empty-row write_table calls require an explicit row_model= kwarg, since Python gives no way to recover element type from an empty list -- an addition to the plan's pinned signature, not a substitution for it"
  - "query/write_query_to_part table_bindings are name -> Path (a resolved Parquet path the caller already has), not table-name strings requiring further zone resolution"
  - "dvc init run without --no-scm-checks (that flag does not exist in dvc 3.67; --no-scm is the closest real flag and is not needed since this repo already has git)"

patterns-established:
  - "Pattern: transient staging root is a sibling of the five Zone directories, never a Zone member, resolved through a parallel containment-checked resolver"
  - "Pattern: one lineage fragment file per producing Stage, never a shared lineage table"

requirements-completed: [DATA-04, ENG-01, ENG-04, ENG-09]

coverage:
  - id: D1
    description: "write_table / write_table_from_parts / write_part_file / write_query_to_part / read_table / table_exists / query, all root-addressable, sorted, atomic, and free of wall-clock metadata"
    requirement: "ENG-04"
    verification:
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "write_table_from_parts merges out-of-core through DuckDB (never pyarrow.concat_tables) with peak allocation bounded by STORAGE_MEMORY_LIMIT_MB plus one row group"
    requirement: "ENG-01"
    verification:
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py::test_merge_read_parquet_file_never_called_for_parts"
        status: pass
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py::test_merge_spill_invariance"
        status: pass
      - kind: unit
        ref: "tests/golden/test_deterministic_write.py::test_merge_peak_rss_stays_under_budget"
        status: unknown
    human_judgment: true
    rationale: "The peak-RSS budget test (ENG-08's actual memory-bounded proof) skips on this Windows dev machine -- the `resource` module it depends on is POSIX-only. It has never executed successfully on any machine in this session. It runs in CI (Linux, via `just ci`) per plan 01-04's workflow, but that has not been observed by this executor. A human/CI run must confirm status before ENG-08 is treated as proven for this plan; see Known Limitations below."
  - id: D3
    description: "content-hash lineage: record_lineage computes content_hash and input_hashes from disk bytes at call time, never accepts them from the caller; fragments are per-Stage and upsert by table_name"
    requirement: "DATA-04"
    verification:
      - kind: unit
        ref: "tests/integration/test_lineage.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "DVC initialized with no remote and no telemetry; .dvcignore covers the staging root"
    requirement: "ENG-09"
    verification:
      - kind: unit
        ref: "test -d .dvc && test -f .dvcignore && uv run dvc config core.analytics"
        status: pass
    human_judgment: false

duration: 2026-08-04 (interrupted once by a session usage limit; resumed same day)
completed: 2026-08-04
status: complete
---

# Phase 01 Plan 06: Storage Repository Layer and Content-Hash Lineage Summary

**`nextmove.storage` repository layer (write_table / write_table_from_parts / write_part_file /
write_query_to_part / read_table / query), content-hash lineage with anti-forgery-by-construction,
and DVC initialized with no remote -- all built on one private streaming Parquet writer so every
byte in the project is produced at a single, auditable site.**

## Performance

- **Tasks:** 3/3 completed
- **Files created:** 8 (paths.py, _parquet.py, repository.py, lineage.py, two test suites,
  .dvcignore, .dvc/config)
- **Files modified:** 1 (storage/__init__.py)
- **Tests added:** 48 (28 golden + 20 lineage; one golden test skips on this platform, see below)
- **Full suite:** 164 passed, 1 skipped (was 116 before this plan; no regressions)

## Accomplishments

- One private Parquet writer (`_parquet.write_parquet_stream`) is the single site Parquet bytes
  are produced in the project, consuming a `RecordBatchReader` and emitting fixed
  `PARQUET_ROW_GROUP_SIZE`-row groups; `write_parquet_atomic` sorts an in-memory table and
  delegates to it, so the two paths cannot drift.
- `write_table_from_parts` merges part files out-of-core through DuckDB (`read_parquet` +
  explicit `ORDER BY ... NULLS LAST` + optional `QUALIFY row_number() ... = 1` for `dedupe_on`)
  and streams the result straight into the writer -- it never calls `read_parquet_file` on a part
  and never calls an Arrow whole-table concatenation.
- Sort-key **tuple** uniqueness (not final-column uniqueness) is enforced on adjacent rows of the
  already-sorted stream, in constant memory, so `(tick, sku)` and `(customer_id, as_of_ts)` write
  successfully while a repeated whole tuple raises.
- Content-hash lineage: `record_lineage` computes `content_hash` (the described table) and every
  `input_hashes` entry from bytes on disk at call time; `LineageRecordDraft` has no
  `content_hash`/`input_hashes` field at all, so a producer cannot supply a hash it did not earn.
  One fragment file per `Stage` (`data/lineage/{simulate,ingest,features}.parquet`), upserted by
  `table_name`.
- `write_table`/`write_table_from_parts` refuse `Zone.LINEAGE` outright; lineage is persisted only
  through the private primitive, so recording lineage cannot re-enter the table-writing path.
- Every disk-touching function (`write_table`, `write_table_from_parts`, `write_part_file`,
  `write_query_to_part`, `list_part_files`, `clear_staging`, `read_table`, `table_exists`, `query`,
  plus `connect`) accepts `root: Path | None = None`.
- `nextmove.storage.Table` (`= pyarrow.Table`) is importable from the package root and is the
  sanctioned way for a package forbidden from importing `pyarrow` to annotate an Arrow return
  value.
- DVC initialized (`dvc init`), `core.autostage=true`, `core.analytics=false`, no remote
  configured, `.dvcignore` covers `data/_staging/`, `.venv/`, `__pycache__/`, `tests/`.

## Task Commits

1. **Task 1: Build the deterministic storage repository layer** - `817ce35` (feat)
2. **Task 2: Build content-hash lineage and initialize DVC** - `712454a` (feat)
3. **Task 3: Author the lineage and byte-identical-write test suites** - `fd6cab5` (test, plus Rule
   1 bug fixes in `repository.py` found while getting the suites green -- see Deviations)

**Plan metadata:** commit created alongside this SUMMARY.

## Files Created/Modified

- `src/nextmove/storage/paths.py` - `DATA_ROOT` (anchored to this module's file location, never
  cwd), `Zone` (5 members), `Stage` (3 members), `resolve_table_path`, `staging_root`,
  `resolve_staging_path`
- `src/nextmove/storage/_parquet.py` - `PARQUET_ROW_GROUP_SIZE` (65536, pinned), `CONTRACT_VERSION`
  ("1.0.0"), `write_parquet_stream`, `write_parquet_atomic`, `read_parquet_file`
- `src/nextmove/storage/repository.py` - `Table` alias, `STORAGE_MEMORY_LIMIT_MB` (512), `connect`,
  `write_table`, `write_table_from_parts`, `write_part_file`, `write_query_to_part`,
  `list_part_files`, `clear_staging`, `read_table`, `table_exists`, `query`
- `src/nextmove/storage/lineage.py` - `content_hash`, `LineageRecordDraft`, `LineageRecord`,
  `record_lineage`, `read_lineage`, `print_lineage_chain`
- `src/nextmove/storage/__init__.py` - re-exports the public repository/lineage/paths surface only
- `tests/golden/test_deterministic_write.py` - 28 tests, ~50-row synthetic fixtures, no simulator
  dependency
- `tests/integration/test_lineage.py` - 20 tests covering every Task 2 behavior plus
  cycle-1-through-3 review-finding regressions
- `.dvcignore`, `.dvc/config` - DVC initialization artifacts

## Exact Call Surface (for plans 01-08, 01-09, 01-10, 01-11)

```python
write_table(
    rows: Iterable[BaseModel | Mapping[str, object]],
    table_name: str, zone: Zone, sort_key: tuple[str, ...],
    resolved_config: ResolvedConfig, producer_stage: Stage,
    input_paths: Sequence[Path] = (), record_lineage: bool = True,
    extra_metadata: Mapping[str, str] | None = None, root: Path | None = None,
    row_model: type[BaseModel] | None = None,   # see Interpretations below
) -> Path

write_table_from_parts(
    part_paths: Sequence[Path],
    table_name: str, zone: Zone, sort_key: tuple[str, ...],
    resolved_config: ResolvedConfig, producer_stage: Stage,
    input_paths: Sequence[Path] = (), record_lineage: bool = True,
    dedupe_on: str | tuple[str, ...] | None = None,
    extra_metadata: Mapping[str, str] | None = None, root: Path | None = None,
) -> Path

write_part_file(
    rows: Iterable[BaseModel | Mapping[str, object]],
    part_dir: str, part_index: int, sort_key: tuple[str, ...],
    root: Path | None = None, row_model: type[BaseModel] | None = None,
) -> Path

write_query_to_part(
    sql: str, part_dir: str, part_index: int, sort_key: tuple[str, ...],
    root: Path | None = None, **table_bindings: Path,
) -> Path

record_lineage(
    path: Path, draft: LineageRecordDraft,
    input_paths: Sequence[Path] = (), root: Path | None = None,
) -> LineageRecord
```

`LineageRecordDraft` fields: `table_name: str, zone: str, input_tables: list[str],
config_hash: str, contract_version: str, producer_stage: Stage, row_count: int`. No
`content_hash`, no `input_hashes` -- the only field whose name contains `hash` is `config_hash`.

`LineageRecord` fields: every `LineageRecordDraft` field plus `content_hash: str,
input_hashes: list[str]`. No field name contains `time`, `date`, or `at`.

**`root` is accepted by:** `write_table`, `write_table_from_parts`, `write_part_file`,
`write_query_to_part`, `list_part_files`, `clear_staging`, `read_table`, `table_exists`, `query`,
`connect`, `resolve_table_path`, `resolve_staging_path`, `staging_root`, `record_lineage`,
`read_lineage`, `print_lineage_chain`. `DATA_ROOT` resolves to `<repo_root>/data`, computed from
`Path(__file__).resolve().parents[3]` in `paths.py` -- never from `Path.cwd()`. Verified equal
across two subprocesses launched from two different working directories
(`test_data_root_invariant_across_working_directories`, marked `slow`).

**`sort_key` precondition (as implemented):** the tuple must be unique across written rows, not
its trailing column. `write_parquet_stream` raises `ValueError` with message
`"Duplicate value for sort key {sort_key!r}: {row_key!r} is not unique across the supplied
rows"` on the first adjacent-row duplicate in the sorted stream. `(tick, sku)` and
`(customer_id, as_of_ts)` both write successfully with a repeating trailing column;
`write_table_from_parts` with an empty `part_paths` raises `ValueError` with message
`"write_table_from_parts({table_name!r}): a zero-part merge has no schema source to write
from; call write_table with an empty row set instead"` -- and that is exactly the fallback:
`write_table([], ..., row_model=SomeModel)` for the empty-table case.

**Resolved constants:** `PARQUET_ROW_GROUP_SIZE = 65536` (private to `_parquet.py`, appears in no
function signature, not read from config -- `grep -c PARQUET_ROW_GROUP_SIZE
src/nextmove/config/models.py` is 0). `STORAGE_MEMORY_LIMIT_MB = 512` (module constant in
`repository.py`, outside the hashed config surface for the same reason plan 01-08 excludes
`flush_every_ticks`).

**`Table` alias:** `nextmove.storage.Table is pyarrow.Table` is `True`, verified by test and by
direct import (`from nextmove.storage import Table`).

**`Stage` members and lineage fragment paths (verbatim, for plan 01-11's `dvc.yaml`):**
`Stage.SIMULATE = "simulate"` -> `data/lineage/simulate.parquet`,
`Stage.INGEST = "ingest"` -> `data/lineage/ingest.parquet`,
`Stage.FEATURES = "features"` -> `data/lineage/features.parquet`.

## Decisions Made

- **Interpretation (executor-level, no `schema` parameter in the plan's pinned call surface).**
  `write_table`/`write_part_file` derive the Arrow schema deterministically from
  `type(rows[0])`'s Pydantic field annotations -- never from which values happen to be null, and
  never from a plain `mapping`'s runtime shape. Because a zero-row call has no instance to
  introspect and Python gives no way to recover an emptied sequence's element type, both functions
  gained an additional keyword-only `row_model: type[BaseModel] | None = None`, required only when
  `rows` is empty; calling with empty `rows` and no `row_model` raises `ValueError` naming the
  omission. This does not change the documented call shape for the common (non-empty) case. This
  was a genuine gap in the plan text -- the zero-row behavior is a pinned acceptance criterion but
  the plan specifies no mechanism for deriving a schema with zero data present -- and I judged
  adding one optional, clearly-named parameter to be the smallest change that keeps the contract
  achievable, rather than stopping for a Rule 4 architectural checkpoint on an internal
  implementation detail with no external call-surface consequence for the non-empty path.
- **Schema nullability (Rule 1 bug fix, found via the golden byte-equality test).** Every
  model-derived Arrow field is declared `nullable=True` regardless of the Pydantic field's own
  optionality. `write_table_from_parts` merges through DuckDB's `read_parquet`, and DuckDB's own
  Parquet -> Arrow conversion always reports `nullable=True` on its output columns as an
  engine-level default, not a data-driven inference. A schema that declared required fields
  non-nullable made `write_table` and `write_table_from_parts` of byte-identical rows diverge in
  their Arrow schema -- and therefore in their Parquet bytes -- purely from this mismatch, which
  `test_staging_part_files_roundtrip_and_isolation` caught immediately. Pydantic's own field
  validation is what actually enforces non-nullability before a row ever reaches this function;
  Arrow schema nullability is never used as a data-integrity signal here.
- **`table_bindings` semantics for `query`/`write_query_to_part` (interpretation).** The plan's
  prose ("registers each bound table by name from its Parquet path") is read as `name -> Path`:
  the caller resolves a table's Parquet path themselves (via `resolve_table_path` or
  `resolve_staging_path`) and hands `query`/`write_query_to_part` the resolved `Path` under a
  chosen binding name, which becomes a DuckDB view. This was the only reading under which the
  function's stated behavior composes with the rest of the API (there is no zone parameter per
  binding, so a `name -> table-name-string` reading would be unable to resolve a zone).
- **`root` reservation for `query`/`write_query_to_part` is structurally guaranteed, not solely a
  runtime check.** Because `root` is a named keyword parameter on both functions, Python's own
  argument binding means a keyword literally named `root` always fills that parameter and can
  never land in `**table_bindings` -- the explicit `"root" in table_bindings` check in
  `write_query_to_part`/`query` is therefore unreachable dead code for the `root` name itself
  (kept as documentation/defense-in-depth) but fully reachable and tested for `sort_key` column
  names, which are not named parameters.
- **`dvc init --no-scm-checks` does not exist in dvc 3.67** (Rule 3 auto-fix): the closest real
  flag is `--no-scm`, which is unneeded since this repository already has git. Ran plain
  `dvc init`.
- **Row count for lineage on a merged table is read from the Parquet footer
  (`pq.ParquetFile(dest).metadata.num_rows`), not from re-reading the merged file's data.**
  Re-reading the full merged table just to count rows would silently reintroduce the
  whole-table-materialization hazard ENG-08 exists to close, specifically on the lineage-recording
  path after a horizon-scale merge.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Arrow schema nullability mismatch between write_table and write_table_from_parts**
- **Found during:** Task 3 (golden byte-equality test)
- **Issue:** Model-derived schema fields were declared non-nullable when the Pydantic field was
  required, but DuckDB's `read_parquet` always emits nullable Arrow fields; the merge path and the
  direct-write path therefore produced different Parquet bytes for identical rows.
- **Fix:** `_schema_from_model` now always declares fields `nullable=True`; documented the
  reasoning in the function's docstring.
- **Files modified:** `src/nextmove/storage/repository.py`
- **Verification:** `test_staging_part_files_roundtrip_and_isolation`,
  `test_row_group_boundary_stability`, `test_dedupe_on_merge_matches_single_deduplicated_write`
  all assert byte-equal digests and now pass.
- **Committed in:** `fd6cab5` (Task 3 commit)

**2. [Rule 1 - Bug] Deprecated `fetch_arrow_table()` call**
- **Found during:** Task 3 (test run surfaced a DeprecationWarning)
- **Issue:** `query()` used duckdb's deprecated `.fetch_arrow_table()`.
- **Fix:** Switched to `.to_arrow_table()`.
- **Files modified:** `src/nextmove/storage/repository.py`
- **Committed in:** `fd6cab5`

**3. [Rule 1 - Bug] Docstring text collided with a grep acceptance guard**
- **Found during:** Task 3 (self-check against the plan's acceptance criteria)
- **Issue:** A `write_table_from_parts` docstring literally contained the string
  `pyarrow.concat_tables`, which the plan's own acceptance criterion
  (`grep -Ec 'concat_tables|concat_arrays' src/nextmove/storage/repository.py` outputs `0`) checks
  file-wide including comments/docstrings, not just code.
- **Fix:** Reworded the docstring to describe the same prohibition without the literal token.
- **Files modified:** `src/nextmove/storage/repository.py`
- **Committed in:** `fd6cab5`

**4. [Rule 3 - Blocking] `dvc init --no-scm-checks` flag does not exist**
- **Found during:** Task 2
- **Issue:** The plan's action text names a `--no-scm-checks` flag; `dvc init --help` on the
  installed dvc 3.67 shows no such flag (the real flag is `--no-scm`, for repos with no git at
  all).
- **Fix:** Ran plain `dvc init` (this repo already has git, so no scm-bypass flag is needed).
- **Files modified:** none (tooling invocation only)
- **Committed in:** `712454a` (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (3 Rule 1 bug fixes, 1 Rule 3 blocking-issue fix). Two further
items are documented above under "Decisions Made" as interpretations of underspecified mechanism
(the `row_model` zero-row schema fallback, and `table_bindings` semantics) rather than as
auto-fixed defects, because they fill a genuine gap in the plan text rather than correct a wrong
behavior.
**Impact on plan:** All auto-fixes were necessary for the plan's own pinned byte-equality
acceptance criteria to hold. No scope creep; no producer-facing call surface changed from what the
plan specifies, except the one additive, clearly-flagged `row_model` parameter.

## Issues Encountered

- **Session interruption.** Execution was cut off mid-Task-1 by a session usage limit after
  `dedupe_on`/`write_query_to_part` had already been manually smoke-tested and confirmed working,
  but before anything was committed. On resume, the working tree's uncommitted files were
  re-verified (imports, ruff, lint-imports, full test suite) rather than discarded, since they were
  further along and in better shape than a stale interruption note (`.continue-here.md`, written
  from an earlier and less-complete interruption of this same plan) suggested. That note is now
  obsolete and should be treated as superseded by this SUMMARY.

## Known Limitations (be explicit, per ENG-08's review history)

ENG-08 (memory-bounded streaming) failed cross-AI review in all three convergence cycles for this
phase, each time in a new disguise. This plan closes it *mechanically* -- there is structurally one
streaming writer, the merge is out-of-core through DuckDB, and the sort-key uniqueness check
operates on adjacent stream rows rather than a held table -- and that mechanism is checked by three
tests: `test_merge_read_parquet_file_never_called_for_parts` (the merge never reads a part into
Arrow -- **passes**), `test_merge_spill_invariance` (spilling and non-spilling merges produce equal
digests -- **passes**), and `test_merge_peak_rss_stays_under_budget` (the actual peak-RSS proof).

**The peak-RSS test has never run to completion on this machine.** This is a Windows dev
environment; the test depends on the POSIX-only `resource` module and self-skips with a stated
reason (`"resource module unavailable on this platform (no RSS reading)"`) rather than failing or
silently passing. It is designed to run in CI (Linux, via `just ci`, per plan 01-04's workflow),
but **this executor has not observed a CI run and cannot confirm the budget actually holds under
Linux.** `MERGE_PEAK_RSS_BUDGET_MB` is set to `2 * STORAGE_MEMORY_LIMIT_MB + 256 = 1280`MB in the
test file. This is the single most important item for whoever next has Linux CI access to verify:
run `uv run pytest tests/golden/test_deterministic_write.py::test_merge_peak_rss_stays_under_budget
-v -m slow` on Linux and confirm it passes rather than errors or silently reports a number that
happens to be under budget for the wrong reason (e.g. the subprocess crashing before completing
the merge). I did not fabricate a "measured child-process peak RSS" figure for this SUMMARY because
none was actually measured in this session -- the plan's `<output>` instruction asks for that
number and I am declining to invent it.

Two more residual, accepted gaps stated in the plan's own threat model and repeated here for
visibility: `read_table` and `query` return fully materialized Arrow tables by design (not a bug --
an interactive `SELECT` should return a table), and `config_hash` is caller-supplied because it
describes configuration rather than any file on disk.

## User Setup Required

None - no external service configuration required. No DVC remote is configured (by design, per
ENG-08's no-cloud-dependency requirement); DVC's local cache is sufficient for the laptop-only
guarantee.

## Next Phase Readiness

- The storage API plans 01-08 (simulator), 01-09 (ingest), and 01-10 (features) all call into is
  now real and tested. All three should conform to the call surface recorded above rather than
  inventing their own dialect, per the plan's stated intent.
- Plan 01-11 can declare `dvc.yaml` stages against the three `Stage` fragment paths recorded above.
- **Before treating ENG-08 as fully proven for this plan, get a Linux CI run of
  `test_merge_peak_rss_stays_under_budget` and confirm it passes** -- see Known Limitations.
- `.planning/phases/01-reproducible-world/.continue-here.md` is now stale (written during an
  earlier, less-complete interruption of this same plan) and should be deleted or ignored by the
  next agent; the state it describes is superseded by this SUMMARY and the three commits above.

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*

## Self-Check: PASSED

All 9 created files confirmed present on disk (paths.py, _parquet.py, repository.py, lineage.py,
both test suites, .dvcignore, .dvc/config, this SUMMARY). All 4 commit hashes (817ce35, 712454a,
fd6cab5, 8741698) confirmed present in `git log --oneline --all`. Full suite re-verified: 164
passed, 1 skipped (POSIX-only RSS test, self-skipping with a stated reason on this Windows
machine). `just lint`-equivalent (ruff check, ruff format --check, lint-imports) all clean;
import-linter contracts 2 kept / 0 broken.
