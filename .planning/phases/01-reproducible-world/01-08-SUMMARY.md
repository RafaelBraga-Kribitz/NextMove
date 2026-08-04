---
phase: 01-reproducible-world
plan: 08
subsystem: simulator
tags: [pydantic, pyarrow, duckdb, numpy, discrete-event-simulation, memory-budget]

requires:
  - phase: 01-reproducible-world (plan 01-05)
    provides: canonical Event/EventType/payload contracts, derive_event_id, sort_events, CANONICAL_SORT_KEY
  - phase: 01-reproducible-world (plan 01-06)
    provides: write_table/write_part_file/write_table_from_parts/list_part_files/clear_staging, Zone/Stage, lineage
  - phase: 01-reproducible-world (plan 01-07)
    provides: SimClock, stream_rng/entity_rng/SeedDomain, LatentTraits, World/Catalog/InventoryState/Campaign
provides:
  - "D-03 documented action-response functions (response_multiplier, ground_truth_uplift, base_conversion_probability) with a per-archetype config-driven combining formula"
  - "D-04 fatigue-penalty reward-hacking loophole, toggleable via config and documented as deliberate"
  - "D-07 three-stage daily tick (advance_tick) driving an empty ActionQueue in Phase 1, reusable unchanged by Phase 3's policy replay"
  - "SIM-04 micro-conversion events (scroll, filter_apply, dwell-class) emitted alongside every macro event"
  - "run_simulation: full-horizon run with row-capped flush-and-merge writes for the three horizon-scaled tables, single-call writes for the three count-bounded tables, one clear_staging after every merge"
  - "python -m nextmove.simulator CLI (--profile, --out, no --seed)"
  - "D-05 UC1/UC2 occurrence proven by query against a real demo-profile run"
  - "ENG-08 memory/wall-clock budget suite: flush invariance, bounded Python accumulation, peak-RSS (Windows-skipped, Linux-enforced by plan 01-11), scale-invariant growth, on-demand default-profile check via just budget"
affects: [01-09-ingest, 01-10-features, 01-11-reproduce-pipeline]

tech-stack:
  added: []
  patterns:
    - "Row-capped, tick-interval-capped _FlushBuffer: the one mechanism behind every horizon-scaled table's flush-and-merge write path"
    - "EventRow: a flat row shape serializing Event.payload to JSON so the storage layer's single-type-per-column schema deriver can handle it"
    - "Popularity-weighted (power-law) sku selection via a cached pure function of category size, replacing uniform selection"
    - "TickState: cross-tick mutable state (fatigue counters, campaign exposure history) threaded by the caller across the whole horizon"

key-files:
  created:
    - src/nextmove/simulator/response.py
    - src/nextmove/simulator/queue.py
    - src/nextmove/simulator/tick.py
    - src/nextmove/simulator/run.py
    - src/nextmove/simulator/__main__.py
    - tests/unit/test_response_functions.py
    - tests/unit/test_tick_loop.py
    - tests/integration/conftest.py
    - tests/integration/test_uc_scenarios_occur.py
    - tests/integration/test_simulation_budget.py
  modified:
    - src/nextmove/config/models.py
    - config/simulator.yaml
    - config/profiles/tiny.yaml
    - src/nextmove/simulator/__init__.py
    - justfile
    - pyproject.toml
    - tests/unit/test_config_merge_hash.py

key-decisions:
  - "Added ResponseConfig.archetype_base_multiplier and SimulatorConfig.engagement (Rule 2): the plan's response_multiplier and organic-session mechanics need config fields plan 01-03's shipped schema did not have, and ENG-03 forbids a business number as a code literal"
  - "EventRow flattens Event.payload to a JSON string before any storage-layer write (Rule 3): the generic Pydantic-to-Arrow schema deriver cannot handle Event.payload's 13-member discriminated union"
  - "pyproject.toml's storage import-linter contract gained ignore_imports entries for storage's own pyarrow/duckdb edges (Rule 3): the contract's transitive forbidden-import check previously blocked every consumer package from importing nextmove.storage at all, contradicting repository.py's own documented design"
  - "advance_tick takes an explicit TickState fifth argument beyond the plan's sketched signature (executor interpretation): fatigue penalties and campaigns.frequency_cap_per_week are accumulate-over-time mechanics with nowhere else to live"
  - "Lowered inventory.restock_probability_per_day 0.08->0.01, raised engagement.add_to_cart_given_view_rate 0.18->0.33, and switched sku selection from uniform to a cached power-law popularity weighting (exponent 3.0) (Rule 1): proven empirically, across six full demo-profile runs, that the shipped values made D-05's UC1 scarcity scenario structurally unreachable regardless of demand concentration alone"
  - "justfile's simulate/budget recipes unwrap a literal profile=X positional argument via trim_start_match, since just has no name=value CLI calling convention and this phase's plans document `just simulate profile=\"tiny\"` throughout"

requirements-completed: [SIM-01, SIM-04]

coverage:
  - id: D1
    description: "response_multiplier/ground_truth_uplift/fatigue_penalty/apply_discount_cents: D-03's documented, config-driven action-response functions with the D-04 loophole"
    requirement: SIM-01
    verification:
      - kind: unit
        ref: "tests/unit/test_response_functions.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "advance_tick: D-07's three-stage daily tick with D-08 same-tick closed loop, deterministic across shuffled iteration order"
    requirement: SIM-01
    verification:
      - kind: unit
        ref: "tests/unit/test_tick_loop.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "SIM-04 micro-conversion events (scroll, filter_apply, dwell-class) emitted alongside every macro event, no attached weight"
    requirement: SIM-04
    verification:
      - kind: unit
        ref: "tests/unit/test_tick_loop.py::TestMicroEvents"
        status: pass
    human_judgment: false
  - id: D4
    description: "run_simulation: full-horizon run persisting six tables through the storage layer inside a row-capped memory bound"
    requirement: SIM-01
    verification:
      - kind: integration
        ref: "tests/integration/test_simulation_budget.py::TestArtifactsAndLineage"
        status: pass
      - kind: integration
        ref: "tests/integration/test_simulation_budget.py::TestBoundedAccumulation"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-05: UC1 (winter-jacket cart abandoner, scarce stock, low price sensitivity, pre-Christmas) and UC2 (recently purchased, high-fatigue) genuinely occur in the generated demo-scale population, found by query"
    verification:
      - kind: integration
        ref: "tests/integration/test_uc_scenarios_occur.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "ENG-08 memory/wall-clock budget: flush invariance, bounded accumulation, scale-invariant growth, zero-event fallback; peak-RSS assertion present but unexecuted on this Windows dev machine"
    verification:
      - kind: integration
        ref: "tests/integration/test_simulation_budget.py"
        status: pass
    human_judgment: true
    rationale: "The peak-RSS assertion (the one that can observe Arrow/DuckDB memory, not just tracemalloc's Python-object view) self-skips on this Windows dev machine because Python's resource module is POSIX-only. It has never executed to completion on any machine used for this plan. A human/CI reviewer must confirm it passes on Linux before ENG-08's Arrow/DuckDB half is treated as proven for this plan (plan 01-11's CI step is designed to enforce this)."

duration: ~5h (includes extensive empirical calibration against real demo-profile runs, each ~3-4 minutes)
completed: 2026-08-04
status: complete
---

# Phase 1 Plan 8: Daily Tick, Response Functions, Micro-Events, UC1/UC2 Summary

**Latent-trait-driven action-response functions with a documented D-04 fatigue loophole, a three-stage daily tick emitting SIM-04 micro-events, and a full-horizon run flushed through row-capped buffers into six storage-layer tables, with UC1/UC2 proven to occur by query against a real demo-profile run.**

## Performance

- **Duration:** ~5h (dominated by six full `demo`-profile calibration runs, each 3-4 minutes, needed to make D-05's UC1 scarcity scenario genuinely reachable)
- **Tasks:** 3
- **Files created:** 10
- **Files modified:** 7

## Accomplishments

- `src/nextmove/simulator/response.py`: `ActionType` (DEC-03's eight archetypes), `apply_discount_cents` (the project's single monetary rounding site, `ROUND_HALF_EVEN`), `fatigue_penalty` (D-04's documented loophole), `response_multiplier` (the documented combining formula), `base_conversion_probability`, `ground_truth_uplift` — computable for any `(customer, action)` pair without running the simulation, per ADR-006/MODEL-06.
- `src/nextmove/simulator/queue.py`: `ScheduledAction`, `ActionQueue` (D-07 stage 1; empty in Phase 1).
- `src/nextmove/simulator/tick.py`: `advance_tick`, `TickResult`, `TickState`. Three ordered stages (drain → apply response → generate organic behaviour) proven to interact same-tick (D-08). Organic generation emits `session_start`/`product_view`/`scroll`/`filter_apply`/`dwell`/`add_to_cart`/`order_placed`-or-`cart_abandon`/`session_end` plus `campaign_exposure`, all canonical `Event`s with deterministic per-`(customer_id, tick)` `seq`-derived ids.
- `src/nextmove/simulator/run.py`: `run_simulation`, `FLUSH_EVERY_TICKS`/`FLUSH_MAX_BUFFERED_ROWS`, `_FlushBuffer`. Six tables written through the storage layer: `events_raw`, `inventory_snapshots`, `ground_truth_uplift` flushed and merged (`write_part_file` → `write_table_from_parts`); `catalog`, `campaigns`, `customer_traits` written in one `write_table` call. One `clear_staging` after every merge.
- `src/nextmove/simulator/__main__.py`: `python -m nextmove.simulator --profile <name> [--out <dir>]` CLI, no `--seed` flag.
- `justfile`: `simulate`/`budget` recipes.
- `tests/integration/{conftest,test_uc_scenarios_occur,test_simulation_budget}.py`: shared session-scoped `demo`-profile fixtures; D-05's UC1/UC2 occurrence proven by DuckDB query; the full ENG-08 budget suite.

## Task Commits

1. **Task 1: Action-response functions, ground-truth uplift, fatigue loophole** - `ccc7023` (feat)
2. **Task 2: Three-stage daily tick and organic event generation** - `4c2f1bb` (feat)
3. **Task 3: Full-horizon run, memory budget, UC1/UC2 acceptance** - `38ae58b` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `src/nextmove/simulator/response.py` - D-03 action-response functions, D-04 loophole
- `src/nextmove/simulator/queue.py` - D-07 stage-1 action queue
- `src/nextmove/simulator/tick.py` - D-07 three-stage daily tick, organic generation, micro-events
- `src/nextmove/simulator/run.py` - full-horizon run, flush-and-merge writes, six tables
- `src/nextmove/simulator/__main__.py` - CLI entry point
- `src/nextmove/simulator/__init__.py` - re-exports for the three new modules
- `src/nextmove/config/models.py` - `ResponseConfig.archetype_base_multiplier`, `EngagementConfig`, `SimulatorConfig.uplift_snapshot_every_ticks`
- `config/simulator.yaml` - archetype coefficients, engagement block, uplift cadence, Rule 1 restock/engagement calibration
- `config/profiles/tiny.yaml` - `uplift_snapshot_every_ticks: 1` override
- `justfile` - `simulate`, `budget` recipes
- `pyproject.toml` - import-linter `ignore_imports` fix for the storage contract
- `tests/unit/test_response_functions.py`, `tests/unit/test_tick_loop.py` - Task 1/2 test suites
- `tests/unit/test_config_merge_hash.py` - fixture updated for the two new config fields
- `tests/integration/conftest.py`, `tests/integration/test_uc_scenarios_occur.py`, `tests/integration/test_simulation_budget.py` - Task 3 test suites

## Decisions Made

- **`ResponseConfig.archetype_base_multiplier` and `SimulatorConfig.engagement` added (Rule 2).** The plan's `response_multiplier` action text calls for "a per-archetype base coefficient from `ResponseConfig`" and organic session generation needs a session-occurrence probability; neither field existed in plan 01-03's shipped schema, and ENG-03 forbids a business number as a code literal. `config/simulator.yaml` gained `response.archetype_base_multiplier` (one coefficient per non-`none` archetype) and a new `engagement:` block (`base_session_probability`, `min/max_views_per_session`, `add_to_cart_given_view_rate`).
- **`EventRow` flattens `Event` before any storage write (Rule 3, blocking).** `nextmove.storage`'s generic Pydantic-to-Arrow schema deriver raises `TypeError` on any field whose annotation is a union of more than one non-`None` type; `Event.payload` is `EventPayload`, a 13-member discriminated union. `EventRow` (in `run.py`) is a flat row shape with `payload` serialized via `payload.model_dump_json()` (a lossless round-trip), which the schema deriver's single-type-per-column contract can handle. `nextmove.storage.repository` was out of this task's file list, so reworking its schema deriver to special-case a wide union was a larger structural change than one flat row model.
- **`pyproject.toml`'s storage import-linter contract gained `ignore_imports` entries (Rule 3, blocking).** The "only `nextmove.storage` may touch the parquet/duckdb i/o surface" contract is a `forbidden`-type contract, which import-linter checks *transitively*. Before this fix, `nextmove.simulator` (or any other listed source package) importing `nextmove.storage` at all was flagged as forbidden, because `nextmove.storage.repository`/`lineage`/`_parquet` import `pyarrow`/`duckdb` directly — even though `nextmove.storage`'s own module docstring explicitly documents that other packages calling into it is the sanctioned route. Adding `ignore_imports` entries naming storage's own internal edges to `pyarrow`/`duckdb` breaks the transitive chain at storage's boundary for every *other* source module, while a direct `import pyarrow` from `nextmove.simulator` itself is still caught (verified by a scratch-file test during implementation).
- **Executor interpretation: `advance_tick` takes an explicit `TickState` fifth argument.** The plan sketches `advance_tick(world, tick, queue, config)`. Fatigue penalties (`response.fatigue_penalty`) and `campaigns.frequency_cap_per_week` are both accumulate-over-time mechanics; `World` (plan 01-07) has no field for either, and this task's file list did not touch `world.py`. `TickState` (bounded by population and campaign count, never by the horizon) is the minimal container, threaded tick-to-tick by the caller (`run_simulation` in Phase 1; Phase 3's replay loop would reuse the identical object).
- **Rule 1 calibration: `inventory.restock_probability_per_day` 0.08→0.01, `engagement.add_to_cart_given_view_rate` 0.18→0.33, uniform sku selection → cached power-law popularity weighting (`_zipf_weights`, exponent 3.0).** Proven empirically across six full `demo`-profile runs (~3-4 minutes each) that the originally shipped values made D-05's UC1 scarcity scenario ("winter-jacket cart abandoner with **low stock**...") structurally unreachable: even a sku receiving 40%+ of its category's total order volume across the full 548-day horizon never dropped below roughly 100 of its 250-unit initial stock, because a restock trigger that always topped a sku back to full stock erased days of accumulated demand in one step, and uniform sku selection diluted demand across hundreds of skus per category regardless. The calibrated values (documented in-code with the empirical numbers that motivated each step) reliably deplete the single most popular sku per category to zero within the December peak-season window, which is where UC1's query actually finds it.
- **The fatigue counter is a simplified monotonic running total, not a decayed rolling window.** `TickState.fatigue_counters[customer_id]` counts total contacts (action deliveries plus campaign exposures) since signup. `response.fatigue_penalty` only needs "more contact strictly reduces response," which this satisfies; a true decay/rolling-window mechanic is deferred until a requirement actually needs it.
- **`justfile`'s `simulate`/`budget` recipes use `trim_start_match`.** `just` has no native `name=value` CLI calling convention — `just simulate profile="tiny"` (the invocation form this phase's plans document throughout, 01-08 through 01-11) arrives as the single literal positional string `profile=tiny`. `trim_start_match(profile, "profile=")` unwraps that form while leaving plain `just simulate tiny` unaffected; both are asserted by test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `ResponseConfig.archetype_base_multiplier` and `SimulatorConfig.engagement`**
- **Found during:** Task 1 (response functions) and Task 2 (organic tick generation)
- **Issue:** The plan's action text requires a per-archetype base coefficient and an organic session-occurrence probability, neither of which existed in the shipped `SimulatorConfig` schema (plan 01-03)
- **Fix:** Added `archetype_base_multiplier: dict[str, float]` to `ResponseConfig` (with a coverage validator against the seven non-`none` archetype names) and a new `EngagementConfig` group
- **Files modified:** `src/nextmove/config/models.py`, `config/simulator.yaml`, `tests/unit/test_config_merge_hash.py`
- **Verification:** `tests/unit/test_response_functions.py`, `tests/unit/test_tick_loop.py`, `tests/unit/test_config_merge_hash.py` all pass
- **Committed in:** `ccc7023` (Task 1), `4c2f1bb` (Task 2)

**2. [Rule 3 - Blocking] `EventRow` flattening for the storage layer's schema deriver**
- **Found during:** Task 3 (first `write_part_file` call for `events_raw`)
- **Issue:** `nextmove.storage`'s generic Pydantic-to-Arrow schema deriver raises `TypeError` on `Event.payload`'s 13-member discriminated union
- **Fix:** `EventRow` (flat shape, `payload` as a JSON string) plus `_event_to_row`
- **Files modified:** `src/nextmove/simulator/run.py`
- **Verification:** `tests/integration/test_simulation_budget.py::TestArtifactsAndLineage`, manual inspection of written Parquet schema/rows
- **Committed in:** `38ae58b` (Task 3)

**3. [Rule 3 - Blocking] Import-linter contract fix for `nextmove.storage` consumers**
- **Found during:** Task 3 (`run.py`'s first `from nextmove.storage import ...`)
- **Issue:** The storage import-linter contract's transitive forbidden-import check flagged *any* package importing `nextmove.storage` at all, since storage's own modules import `pyarrow`/`duckdb` directly — contradicting `repository.py`'s own documented design ("a consumer package... imports the public `Table` alias... instead of importing pyarrow itself")
- **Fix:** Added `ignore_imports` entries naming storage's own internal edges to `pyarrow`/`duckdb`, breaking the transitive chain at storage's boundary for other packages while still catching a direct `import pyarrow` from `nextmove.simulator`
- **Files modified:** `pyproject.toml`
- **Verification:** `uv run lint-imports` passes; manually verified a scratch `import pyarrow` inside `nextmove.simulator` still trips the contract, then removed the scratch file
- **Committed in:** `38ae58b` (Task 3)

**4. [Rule 1 - Bug] Restock, engagement rate, and sku-selection calibration for D-05's UC1**
- **Found during:** Task 3, while writing `tests/integration/test_uc_scenarios_occur.py`
- **Issue:** With the originally shipped `restock_probability_per_day: 0.08` (always topping a sku back to full stock), `add_to_cart_given_view_rate: 0.18`, and uniform sku selection, D-05's UC1 scarcity scenario never occurred at any tested value of demand concentration — proven across six full `demo`-profile runs
- **Fix:** Lowered `restock_probability_per_day` to `0.01`, raised `add_to_cart_given_view_rate` to `0.33`, switched sku selection from uniform to a cached power-law popularity weighting (`_zipf_weights`, exponent `3.0`), and changed restock to replenish a small batch (`_RESTOCK_BATCH_FRACTION = 0.01` of `initial_stock_per_sku`) rather than topping up to full
- **Files modified:** `config/simulator.yaml`, `src/nextmove/simulator/tick.py`
- **Verification:** `tests/integration/test_uc_scenarios_occur.py` passes (UC1 count 44, UC2 count 15 on the calibration run); `tests/unit/test_tick_loop.py` and `tests/unit/test_response_functions.py` still pass unchanged
- **Committed in:** `38ae58b` (Task 3)

---

**Total deviations:** 4 auto-fixed (2 missing-critical-config, 2 blocking)
**Impact on plan:** All four were necessary for the plan's own explicit acceptance criteria (D-05's UC1/UC2 occurrence, and the storage-layer write path existing at all) to be achievable. No scope creep beyond what those criteria required.

## Issues Encountered

- **Demo-profile wall-clock cost.** A full `demo`-profile run (2000 customers, the base config's full 548-day horizon — `demo.yaml` overrides only `n_customers`) takes roughly 3-4 minutes. Calibrating D-05's UC1 scarcity scenario required six such runs. `tests/integration/conftest.py`'s session-scoped `demo_run_result`/`demo_subprocess_rss` fixtures share one in-process run and one subprocess run across `test_uc_scenarios_occur.py` and `test_simulation_budget.py` so the test suite itself pays for this cost only once per session, not once per test file.
- **Peak-RSS assertion unexecuted on this platform.** Per the plan's risk note, `python`'s `resource` module is POSIX-only; the peak-RSS test (the one instrument that can observe Arrow/DuckDB memory, not just `tracemalloc`'s Python-object view) self-skips on this Windows dev machine with an explicit skip reason, exactly as designed. It has never run to completion on any machine used for this plan or plan 01-06's earlier peak-RSS test. This is stated plainly, not papered over: **ENG-08's Arrow/DuckDB-memory claim is unproven on this platform** and requires a Linux CI run to confirm (plan 01-11's CI step is designed to assert the skip does not occur there).
- **Default-profile budget check not executed.** `just budget profile="default"` runs a 50 000-customer, 548-day simulation — at the per-customer cost observed for `demo` (2000 customers, ~3-4 minutes), a `default`-scale run would plausibly take on the order of an hour. It was not run in this session; the test (`test_default_profile_completes_within_its_stated_budget`) is correctly gated behind `NEXTMOVE_RUN_DEFAULT_BUDGET=1` and was verified to work correctly at `tiny` scale (via `NEXTMOVE_BUDGET_PROFILE=tiny`), which exercises the identical code path.

## Measured Numbers

Full test suite (`uv run pytest -q`, this plan's final state): **255 passed, 4 skipped, 0 failed** (baseline before this plan: 207 passed, 1 skipped — the 1 pre-existing skip is `test_deterministic_write.py`'s POSIX-only peak-RSS test from plan 01-06; the 3 new skips are this plan's peak-RSS test, its scale-invariant peak-RSS-ratio test, and the env-gated default-profile budget test).

- **`tiny` profile** (100 customers, 30-day horizon): `just budget profile="tiny"` (using the on-demand check at `tiny` scale) measured wall clock **14.0s** (budget 30s) and peak traced Python heap **62.9MB** (budget 128MB).
- **`demo` profile** (2000 customers, the base config's full 548-day horizon): six full uninstrumented calibration runs measured wall clock in the **181-220s** range (well under the stated 600s budget). One dedicated `tracemalloc`-instrumented measurement run recorded peak traced Python heap **206.1MB** (budget 512MB) at wall clock **784.3s** — `tracemalloc`'s per-allocation tracing overhead, not the production runtime; the uninstrumented figure (181-220s) is the one that reflects `just simulate profile="demo"`'s actual cost. Row counts from that same measurement run: `events_raw` 986 723, `inventory_snapshots` 876 800 (exactly `548 ticks x 1600 skus`), `ground_truth_uplift` 266 000, `catalog` 1600, `campaigns` 4, `customer_traits` 2000.
- **`ground_truth_uplift` cadence:** `simulator.uplift_snapshot_every_ticks` resolves to `30` for `default`/`demo`/`ci` profiles (from `config/simulator.yaml`) and `1` for `tiny` (profile override in `config/profiles/tiny.yaml`). At `tiny` scale (cadence 1, 100 customers, 7 non-`none` archetypes, 30 ticks) this produces 21 000 rows; at `demo` scale (cadence 30, 2000 customers, 19 snapshot ticks across the 548-day horizon) this measured exactly 266 000 rows.
- **UC1/UC2 occurrence** (final calibration run, `demo` profile): UC1 count **44**, UC2 count **15** — both comfortably greater than zero.

## Flagged Assumptions Restated (for phase verification)

Both carried forward verbatim from this plan's frontmatter `flagged_assumptions`, unresolved and requiring human/reviewer sign-off before phase verification closes SIM-04/SIM-01:

1. **SIM-04 micro-event fidelity.** No source artifact states what event-emission resolution is "enough" for Phase 4 to derive micro-conversion weights empirically. This plan emits `dwell` as a three-level class (`short`/`medium`/`long`, boundaries `dwell_short_seconds_max: 8.0`/`dwell_medium_seconds_max: 45.0`) plus `scroll` depth percentage and facet-level `filter_apply` events — the planner's and researcher's judgment of sufficient. If a reviewer believes a different fidelity (e.g. continuous dwell milliseconds, or per-facet dwell) is required, that is unplanned and must be raised before phase verification.
2. **`ground_truth_uplift` snapshot cadence.** Materializing every `(customer, action, tick)` triple at default scale (~219M rows) contradicts ENG-08. The monthly cadence (`uplift_snapshot_every_ticks: 30`, ~7.2M rows at default scale) is the planner's decision, now a schema-validated `SimulatorConfig` field rather than a code literal so a cadence change legitimately changes the config hash. If Phase 4 requires per-tick uplift ground truth, that is unplanned at this cadence and must be raised before phase verification.

## Next Phase Readiness

- `data/raw/{events_raw,catalog,inventory_snapshots,campaigns}.parquet` and `data/ground_truth/{customer_traits,ground_truth_uplift}.parquet` are all real, storage-layer-written, lineage-tracked tables — plan 01-09 (ingest) and plan 01-10 (features) can build directly on `events_raw`.
- **Blocker for phase verification, not for the next plan:** the peak-RSS assertion (ENG-08's Arrow/DuckDB half) has never executed to completion anywhere in this plan's history. Plan 01-11's CI step is designed to close this by asserting the skip does not occur on Linux; until that runs, ENG-08 is asserted-but-unproven for this plan, consistent with plan 01-06's identical open item.
- The `default`-profile budget (`just budget profile="default"`) has never been run to completion in this session; it is correctly wired and gated, and its first real run should happen before the phase's laptop-reproducibility claim is treated as fully proven at default scale.

## Self-Check: PASSED

All 10 created files confirmed present on disk; all 3 task commit hashes (`ccc7023`, `4c2f1bb`, `38ae58b`) confirmed present in `git log --oneline --all`.
