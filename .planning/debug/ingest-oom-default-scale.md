---
status: diagnosed
trigger: |
  UAT Test 1 (.planning/phases/01-reproducible-world/01-UAT.md): full-scale byte-identical
  reproduction at the `default` profile (50,000 customers, 548-day horizon). simulator
  succeeded on data/repro_a; ingest against that root died at ~79% progress (~54 min in)
  with a DuckDB out-of-memory error while merging/sorting canonical output. Second root
  (repro_b) never started. goal: find_root_cause_only.
created: 2026-08-05T00:00:00Z
updated: 2026-08-05T00:35:00Z
---

## Current Focus

hypothesis: write_table_from_parts() builds a single SQL statement that stacks TWO
sequential full-dataset blocking operators -- a window operator
(QUALIFY row_number() OVER (PARTITION BY dedupe_on ORDER BY sort_key)) followed by an
outer ORDER BY on the same sort_key -- and DuckDB's buffer manager does not bound their
combined peak memory to STORAGE_MEMORY_LIMIT_MB the way a single blocking operator would,
per DuckDB's own documented guidance against stacking multiple blocking operators in one
query. This only manifests at real row counts (24.7M), not at tiny (100 cust/30d) or ci
(500 cust/60d) scale.
test: Synthetic repro script (scratchpad/repro_double_blocking.py) generates parquet parts
matching the real schema/keys and runs the exact two SQL shapes -- (A) single ORDER BY only,
(B) QUALIFY window + outer ORDER BY, identical to write_table_from_parts' generated SQL --
against a DuckDB connection with the same PRAGMA threads=1 / memory_limit / temp_directory
configuration as repository.connect(), at a memory_limit low enough to force spilling for
both queries in seconds rather than the ~54 min real failure took.
expecting: If the hypothesis is correct, query (A) succeeds (spills cleanly to
temp_directory) while query (B) OOMs at the same memory_limit over the same data -- isolating
the double-blocking-operator stack as the amplifying factor, not "sorting this many rows in
general."
next_action: Run scratchpad/repro_double_blocking.py with an escalating N / mem_limit_mb
grid until the discriminating result (A succeeds, B fails) is observed or ruled out.

## Symptoms

expected: |
  Run `just reproduce` (or `make reproduce`) with the committed default `dvc.yaml` profile
  (50,000 customers, 548-day horizon) to completion at least once, then a second time into an
  independent `--out` root, and diff the sha256 of all twelve produced tables. Both roots must
  be byte-identical.
actual: |
  simulator succeeded on data/repro_a (81.8 min, 548 daily ticks, 24,698,721 events,
  events_raw ~745MB). ingest was then run against that same root and died at ~79% progress
  (~54 min into the ingest stage) with an out-of-memory error while merging/sorting canonical
  output. The second independent root (repro_b) was never started because the first root's
  ingest never completed. This is NOT a byte-mismatch -- the pipeline is simply unrunnable at
  default scale under the current implementation.
errors: |
  OSError: Out of Memory Error: failed to pin block of size 256.0 KiB
  (488.0 MiB/488.2 MiB used)
  Stack (as reported by the human running it): ingest_events -> write_table_from_parts ->
  write_parquet_stream <- DuckDB ORDER BY / dedupe reader
reproduction: |
  Test 1 in .planning/phases/01-reproducible-world/01-UAT.md. To reproduce:
    uv run python -m nextmove.simulator --profile default --out <root>
    uv run python -m nextmove.ingest    --profile default --out <root>
  (default profile = config/simulator.yaml: n_customers=50000, horizon_days=548). The ingest
  stage enforces STORAGE_MEMORY_LIMIT_MB=512 as an intentional ceiling.
started: "Always broken at this scale -- no plan among 01-06/01-08/01-09/01-10/01-11 has ever
  actually run ingest to completion at the default profile; only tiny/ci/demo scales have been
  exercised."

## Eliminated

## Evidence

- timestamp: 2026-08-05T00:05:00Z
  checked: src/nextmove/storage/repository.py connect() (lines 248-268) and
    write_table_from_parts() (lines 323-409)
  found: connect() sets PRAGMA threads=1, PRAGMA memory_limit='512MB', PRAGMA
    temp_directory=<staging root>. write_table_from_parts builds one SQL statement --
    "SELECT * FROM read_parquet([...]) QUALIFY row_number() OVER (PARTITION BY <dedupe_on>
    ORDER BY <sort_key>) = 1 ORDER BY <sort_key>" -- when dedupe_on is given, then executes
    it via con.execute(sql).to_arrow_reader(PARQUET_ROW_GROUP_SIZE) and streams the reader
    into write_parquet_stream. The docstring (lines 340-348) asserts peak allocation is
    "the memory limit plus one row group at any table size," attributing safety solely to
    DuckDB's spill-on-exceed behavior.
  implication: The claimed O(memory_limit) bound assumes DuckDB treats this as a single
    spillable stage. In fact the QUALIFY clause's window operator and the outer ORDER BY
    are two independent full-dataset blocking operators chained in one query.

- timestamp: 2026-08-05T00:07:00Z
  checked: src/nextmove/ingest/pipeline.py ingest_events() (lines 277-334) and
    src/nextmove/ingest/contracts.py (CANONICAL_SORT_KEY, line 246)
  found: The failing call is the "events" merge (line 281): write_table_from_parts(...,
    sort_key=CANONICAL_SORT_KEY, dedupe_on="event_id", ...). CANONICAL_SORT_KEY =
    ("customer_id", "ts", "event_id") -- NOT the same column as dedupe_on ("event_id"
    alone). So the window operator's PARTITION BY key (event_id, ~unique per row at this
    scale) differs from its own ORDER BY key and from the final outer ORDER BY key, meaning
    the window operator's output is grouped by event_id, not globally ordered by
    (customer_id, ts, event_id) -- DuckDB cannot reuse the window operator's internal sort
    for the final ORDER BY and must perform a second, independent full sort over the same
    ~24.7M rows.
  implication: This is a genuine two-full-sort query, not an accidental redundancy DuckDB's
    optimizer could collapse away -- both sorts are semantically required for correctness as
    written.

- timestamp: 2026-08-05T00:12:00Z
  checked: Web search -- DuckDB official troubleshooting guide
    (duckdb.org/docs/lts/guides/troubleshooting/oom_errors) and DuckDB's window-function
    out-of-core history (GitHub issue duckdb/duckdb#3954, "Out of Core Window Operator";
    0.10.0 release notes)
  found: DuckDB's own troubleshooting documentation explicitly warns against this exact
    pattern -- "If multiple blocking operators appear in the same query, DuckDB may still
    throw an out-of-memory exception due to the complex interplay of these operators,"
    with the stated remediation "Don't stack multiple blocking operators in one monster
    query if you can avoid it. Break it into stages and materialize." Window functions did
    gain out-of-core / spillable sort support (as of DuckDB 0.10.0, well before this
    project's pinned duckdb>=1.5,<2), so a single window operator or a single ORDER BY is
    each individually spill-capable -- the documented hazard is specifically the *chaining*
    of two blocking operators in one query, which is exactly this SQL's shape.
  implication: This is not a NextMove-specific implementation bug in isolation -- it is a
    known, documented DuckDB memory-accounting hazard that the write_table_from_parts
    query shape triggers whenever dedupe_on is supplied with a sort_key that is not a
    strict prefix/superset of dedupe_on (i.e., whenever the dedupe partition key and the
    final sort key genuinely differ, which is the ingest events case).

- timestamp: 2026-08-05T00:20:00Z
  checked: src/nextmove/features/compute.py write_table_from_parts calls (lines 291-315) as
    a control -- do any other write_table_from_parts call sites share this same
    dedupe_on != sort_key shape?
  found: features/compute.py's two write_table_from_parts calls never pass dedupe_on (stays
    at its default None), so no QUALIFY window clause is ever built there -- only a single
    ORDER BY. The rejects merge in ingest/pipeline.py (line 312) passes dedupe_on="reject_id"
    with sort_key=("reject_id",) -- dedupe_on IS the sort_key there, so window
    PARTITION BY reject_id ORDER BY reject_id and the outer ORDER BY reject_id are the same
    key (a much cheaper, likely-collapsible case). Only the events merge (dedupe_on=
    "event_id", sort_key=("customer_id","ts","event_id")) has dedupe_on strictly different
    from sort_key -- and it is the events table (24.7M rows) that failed, not rejects.
  implication: This narrows the defect to write_table_from_parts's QUALIFY-building logic
    specifically when dedupe_on's columns are not identical to sort_key -- the exact and
    only site in the current codebase where that combination occurs is the ingest events
    merge, matching the reported failure exactly.

- timestamp: 2026-08-05T00:30:00Z
  checked: Synthetic reproduction (scratchpad/repro_double_blocking.py) -- generates
    parquet parts with the identical column shape/keys used by write_table_from_parts
    (event_id, customer_id, ts, payload padding), opens a DuckDB connection configured
    exactly like repository.connect() (PRAGMA threads=1, memory_limit, temp_directory), and
    runs (A) "SELECT * FROM read_parquet([...]) ORDER BY customer_id,ts,event_id" vs.
    (B) the real write_table_from_parts-generated SQL: "SELECT * FROM read_parquet([...])
    QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY customer_id,ts,event_id) = 1
    ORDER BY customer_id,ts,event_id", both consumed the same way (to_arrow_reader,
    iterated fully) at matched memory_limit and matched data.
  found: |
    N=3,000,000 rows / memory_limit=100MB: (A) SUCCESS in 2.7s, 0 spill files. (B) FAILED
    in 6.2s: "OutOfMemoryException: Out of Memory Error: failed to pin block of size 256.0
    KiB (95.3 MiB/95.3 MiB used)".
    N=6,000,000 rows / memory_limit=100MB (repeat at 2x scale): (A) SUCCESS in 6.6s. (B)
    FAILED in 12.6s with the byte-identical error message: "failed to pin block of size
    256.0 KiB (95.3 MiB/95.3 MiB used)".
    The failure signature ("failed to pin block of size 256.0 KiB (X.X MiB/X.X MiB used)")
    exactly matches the production error: "failed to pin block of size 256.0 KiB (488.0
    MiB/488.2 MiB used)".
  implication: Confirmed, reproducibly, at two different scales: a single ORDER BY sort
    over this data comfortably fits the memory budget (and did not even need to spill in
    these runs), while adding the QUALIFY window operator ahead of the identical outer
    ORDER BY reliably exhausts the same budget with the identical DuckDB error signature
    seen in production. This isolates the *stacking* of the window operator and the outer
    sort -- not "sorting 24.7M rows in general" -- as the mechanism, consistent with
    DuckDB's own documented multiple-blocking-operator memory hazard (found above).

## Resolution

root_cause: |
  write_table_from_parts() (src/nextmove/storage/repository.py, lines 369-393) builds a
  single SQL statement combining a QUALIFY row_number() window operator (when dedupe_on is
  given) with an outer ORDER BY, and executes it as one DuckDB query:

    SELECT * FROM read_parquet([...])
    QUALIFY row_number() OVER (PARTITION BY <dedupe_on> ORDER BY <sort_key>) = 1
    ORDER BY <sort_key>

  For the ingest "events" merge (src/nextmove/ingest/pipeline.py line 281), dedupe_on=
  "event_id" while sort_key=CANONICAL_SORT_KEY=("customer_id","ts","event_id") -- two
  genuinely different keys, so DuckDB cannot reuse the window operator's internal sort for
  the final ORDER BY and must run two independent full-dataset external sorts back to back
  in one query plan. DuckDB's own troubleshooting documentation names this exact pattern
  ("stacking multiple blocking operators in one query") as a documented case where its
  memory accounting can still exceed a configured memory_limit even though each operator is
  individually spill-capable. STORAGE_MEMORY_LIMIT_MB=512's connection-level PRAGMA
  memory_limit/temp_directory setup (repository.connect(), lines 248-268) does not prevent
  this because the hazard is not "spilling doesn't work" -- it's that two chained blocking
  operators' combined working-set is not bounded by the single memory_limit the way the
  module's own docstring (lines 340-348) assumes ("peak allocation is the memory limit plus
  one row group at any table size"). That assumption is false whenever dedupe_on's columns
  differ from sort_key, which is exactly the ingest events case -- the only
  write_table_from_parts call site in the codebase with that shape, and the one table
  (24.7M rows) large enough to hit it. It reliably reproduces at any scale: confirmed
  synthetically at 3M and 6M rows against a matched memory_limit, with the identical
  "failed to pin block of size 256.0 KiB (X.X MiB/X.X MiB used)" DuckDB error signature
  seen in the real 24.7M-row production failure. It never manifested at tiny (100
  customers/30 days) or ci (500 customers/60 days) scale simply because those runs never
  produced enough rows to exhaust even a naive single-pass double-sort within 512MB.
fix: ""
verification: ""
files_changed: []
</content>
