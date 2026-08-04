---
phase: 01-reproducible-world
plan: 07
subsystem: simulator
tags: [numpy, pydantic, rng, determinism, hypothesis]

# Dependency graph
requires:
  - phase: 01-reproducible-world (plan 01-01)
    provides: src/nextmove/simulator/ package boundary, import-isolation contract
  - phase: 01-reproducible-world (plan 01-03)
    provides: SimulatorConfig, SeedsConfig, LatentTraitsConfig, CategoryConfig, SeasonalityConfig,
      InventoryConfig, CampaignConfig and config/simulator.yaml
provides:
  - Per-entity deterministic RNG substrate (entity_rng, stream_rng, SeedDomain) proven
    order-independent and population-independent by direct test comparison
  - SimClock: config-driven, tz-aware-UTC virtual clock, never reads the host clock
  - LatentTraits + sample_latent_traits: config-driven latent-trait sampling with a documented,
    provably-bounded support for every distribution family (including the mathematically
    unbounded normal/lognormal)
  - World.initialize: fully config-driven Customer/Sku/Catalog/InventoryState/Campaign/World
    construction, with a measurable D-01 seasonality contrast between the high- and
    low-seasonality category classes
affects: [01-08, 01-11]

# Tech tracking
tech-stack:
  added: [hypothesis (property-based testing, already a declared dependency)]
  patterns:
    - "Per-entity RNG via numpy.random.default_rng([entity_id, seed, domain_ordinal, ...tick])"
    - "Purpose-scoped sub-streams via stream_rng + large fixed tick sentinels (>= 1_000_000_001)
       for non-tick-indexed draws (signup timing, SKU prices, campaign discounts), disjoint from
       both real ticks and each other"
    - "Truncate mathematically-unbounded distribution families (normal, lognormal) to a
       documented 6-sigma window via np.clip so 'value outside configured support is impossible
       by construction' is provably true rather than vacuous"
    - "Softmax normalization (not literal sum-normalization) for category_affinity, avoiding
       divide-by-near-zero/negative-sum blowups when the underlying family can produce negative
       raw values"

key-files:
  created:
    - src/nextmove/simulator/rng.py
    - src/nextmove/simulator/clock.py
    - src/nextmove/simulator/traits.py
    - src/nextmove/simulator/world.py
    - tests/unit/test_rng_determinism.py
    - tests/unit/test_simulator_world.py
  modified:
    - src/nextmove/simulator/__init__.py
    - src/nextmove/config/models.py
    - config/simulator.yaml
    - tests/unit/test_config_merge_hash.py

key-decisions:
  - "Truncated normal/lognormal trait draws to a symmetric 6-sigma window (documented, not a
     locked recommendation) so every family has a concrete, finite, testable support"
  - "category_affinity uses a softmax transform, not literal sum-to-1 normalization, because
     the configured family (mean-zero normal) can produce a negative or near-zero raw sum"
  - "Added SeasonalityConfig.low_class_amplitude_factor and CampaignConfig.discount_bps_min/max
     to the config schema (Rule 2) — both were required by this task's world-building logic and
     were missing from plan 01-03's schema; values supplied in config/simulator.yaml, never
     hardcoded in world.py"
  - "Purpose-scoped sub-streams (signup tick, SKU price, campaign discount) use stream_rng with
     large positive tick sentinels (>= 1_000_000_001), not entity_rng directly, to avoid
     accidentally reusing a customer's trait stream for an unrelated draw"

patterns-established:
  - "trait_support(dist) -> (min, max) plus draw_trait_value(dist, rng) is the one place every
     distribution family's sampling + bounding logic lives; plan 01-08's response functions
     should reuse these rather than re-deriving distribution behavior"

requirements-completed: [SIM-01]

coverage:
  - id: D1
    description: "Per-entity RNG (entity_rng/stream_rng) is order-independent and
      population-independent, proven by direct sequence comparison, not by inspection"
    requirement: "SIM-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_rng_determinism.py::TestEntityRngDeterminism::test_order_independence_ascending_descending_shuffled"
        status: pass
      - kind: unit
        ref: "tests/unit/test_rng_determinism.py::TestEntityRngDeterminism::test_population_independence_small_and_large_world"
        status: pass
    human_judgment: false
  - id: D2
    description: "SimClock produces tz-aware UTC timestamps from config start_date + tick index,
      never the host clock, with a correctly half-open tick range"
    requirement: "SIM-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_rng_determinism.py::TestSimClock"
        status: pass
    human_judgment: false
  - id: D3
    description: "Latent traits are sampled deterministically from config, every trait lies
      within its configured (and for unbounded families, truncated) support inclusive of both
      endpoints, and a config parameter change changes the sampled traits"
    requirement: "SIM-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_simulator_world.py::TestBoundarySupport"
        status: pass
      - kind: unit
        ref: "tests/unit/test_simulator_world.py::TestSampleLatentTraits::test_changing_one_distribution_parameter_changes_sampled_traits"
        status: pass
    human_judgment: false
  - id: D4
    description: "World.initialize builds a fully config-driven world (customers, catalog,
      inventory, campaign calendar) with no business literal in world.py, and the
      low-seasonality category is measurably flatter than the high-seasonality category"
    requirement: "SIM-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_simulator_world.py::TestWorldInitialize"
        status: pass
      - kind: unit
        ref: "tests/unit/test_simulator_world.py::TestSeasonalityContrast::test_low_class_peak_to_trough_ratio_is_smaller_than_high_class"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-08-04
status: complete
---

# Phase 1 Plan 07: Deterministic RNG Substrate and World Structure Summary

**Per-entity NumPy RNG substrate (`entity_rng`/`stream_rng`) plus a config-driven `World` —
latent-trait customers, seasonal catalog with a measurably-flatter contrast category,
inventory, and a campaign calendar — all proven deterministic by direct test comparison rather
than asserted.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-08-04T20:20:33+02:00 (first task commit)
- **Completed:** 2026-08-04T20:33:54+02:00 (last task commit)
- **Tasks:** 3
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments

- `entity_rng`/`stream_rng` derive independent NumPy `Generator`s from
  `[entity_id, seed, domain_ordinal, ...tick]` entropy; proven order-independent (ascending,
  descending, shuffled visit order) and population-independent (100 vs. 50,000 customers) by
  direct sequence comparison, and mechanically proven free of legacy `np.random.*` /
  stdlib `random` usage.
- `SimClock` maps ticks to tz-aware UTC timestamps from `start_date` + tick index only, with a
  correctly half-open `[0, horizon_days)` range and never reads the host clock.
- `sample_latent_traits` draws `price_sensitivity`, `loyalty`, `fatigue_propensity`, and a
  per-category `category_affinity` dict, each within a provably-bounded support — `beta`'s
  natural `[0,1]`, `uniform`'s own params, and a documented 6-sigma truncation window for the
  mathematically unbounded `normal`/`lognormal` families used by `fatigue` and
  `category_affinity` in the shipped config.
- `World.initialize` builds a fully config-driven world: contiguous customer ids, a catalog
  whose SKU count/prices/categories all come from `config.categories`, seeded inventory, and a
  campaign calendar. The low-seasonality category's peak-to-trough multiplier ratio is
  mechanically proven smaller than the high-seasonality category's.

## Task Commits

1. **Task 1: Build the deterministic RNG substrate and the simulated clock** - `f23e4e5` (feat)
2. **Task 2: Sample latent traits and build the world structure** - `286cc57` (feat)
3. **Task 3: Author the world-construction test suite** - `50d91e2` (test)
4. **Formatting fixup (post-task)** - `e752eb5` (style)

**Plan metadata:** _pending — this commit_

## Files Created/Modified

- `src/nextmove/simulator/rng.py` - `SeedDomain`, `entity_rng`, `stream_rng`
- `src/nextmove/simulator/clock.py` - `SimClock`
- `src/nextmove/simulator/traits.py` - `LatentTraits`, `sample_latent_traits`, `trait_support`,
  `draw_trait_value`
- `src/nextmove/simulator/world.py` - `Customer`, `Sku`, `Catalog`, `InventoryState`,
  `Campaign`, `World`
- `src/nextmove/simulator/__init__.py` - re-exports the public simulator API
- `src/nextmove/config/models.py` - added `SeasonalityConfig.low_class_amplitude_factor`,
  `CampaignConfig.discount_bps_min`/`discount_bps_max`
- `config/simulator.yaml` - supplied values for the two new config fields
- `tests/unit/test_config_merge_hash.py` - updated inline fixture to include the two new
  required fields
- `tests/unit/test_rng_determinism.py` - Task 1's test suite
- `tests/unit/test_simulator_world.py` - Task 2/3's test suite

## Decisions Made

- **6-sigma truncation for unbounded families:** `normal`/`lognormal` are mathematically
  unbounded, which conflicts with this plan's own "yields a finite response input" and
  "impossible by construction outside its support" requirements. Truncating to `mu ± 6*sigma`
  (log-space for lognormal) via `np.clip` after sampling gives every family a concrete, finite,
  testable support while almost never actually clipping a real draw (`P(|Z|>6) ≈ 2e-9`).
  Documented in `traits.py`'s module docstring for `docs/SIMULATOR_ASSUMPTIONS.md` (SIM-03).
- **Softmax, not literal sum-normalization, for category_affinity:** the shipped config draws
  category affinity from `normal(mu=0.0, sigma=1.0)`, shared across all categories. With only
  two categories, the sum of two mean-zero draws is negative or near-zero with non-trivial
  probability — a literal "divide by the sum" normalization would divide by (near) zero or
  flip every component's sign. Softmax (`exp(raw_i) / sum(exp(raw_j))`) has no such failure
  mode: the denominator is always a sum of strictly positive terms.
- **Added two config fields (Rule 2):** `SeasonalityConfig.low_class_amplitude_factor` (damps
  the low-seasonality category's curve toward 1.0, making D-01's contrast requirement
  mechanically true) and `CampaignConfig.discount_bps_min`/`discount_bps_max` (campaigns need a
  discount range and none existed). Both follow the existing `CategoryConfig` min/max pattern
  and are supplied in `config/simulator.yaml`, never hardcoded in `world.py` (ENG-03).
- **Purpose-scoped sub-streams via large positive tick sentinels:** signup tick, SKU price, and
  campaign discount draws each need their own independent stream, distinct from customer trait
  streams and from each other. `stream_rng` with sentinels `>= 1_000_000_001` (chosen because
  `SeedSequence` entropy must be non-negative, ruling out the more obvious negative-sentinel
  design) achieves this without adding new RNG primitives.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `SeasonalityConfig.low_class_amplitude_factor`**
- **Found during:** Task 2 (World structure — `seasonal_multiplier_for_class`)
- **Issue:** D-01 requires the low-seasonality category to be "genuinely flatter" than the
  high-seasonality category, but `SeasonalityConfig` had no field controlling how much flatter
  — implementing this without a config field would mean hardcoding a damping literal in
  `world.py`, violating ENG-03.
- **Fix:** Added `low_class_amplitude_factor: float` (`0 < x < 1`) to `SeasonalityConfig`,
  set to `0.15` in `config/simulator.yaml`. `World.seasonal_multiplier_for_class` uses it to
  damp the low-class curve toward 1.0.
- **Files modified:** `src/nextmove/config/models.py`, `config/simulator.yaml`,
  `tests/unit/test_config_merge_hash.py`
- **Verification:** `tests/unit/test_simulator_world.py::TestSeasonalityContrast` passes.
- **Committed in:** `286cc57` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added `CampaignConfig.discount_bps_min`/`discount_bps_max`**
- **Found during:** Task 2 (World structure — campaign calendar generation)
- **Issue:** The plan requires `Campaign.discount_bps`, but `CampaignConfig` had no discount
  range to draw from — generating a discount without one would mean a hardcoded literal.
- **Fix:** Added `discount_bps_min`/`discount_bps_max: int` (basis points, `0..10000`) to
  `CampaignConfig`, following the same min/max pattern `CategoryConfig` already uses for price
  bands. Set to `500`/`3000` in `config/simulator.yaml`.
- **Files modified:** `src/nextmove/config/models.py`, `config/simulator.yaml`,
  `tests/unit/test_config_merge_hash.py`
- **Verification:** `World.initialize` builds campaigns with in-range discounts; full test
  suite (207 passed, 1 skipped) still green after the schema change.
- **Committed in:** `286cc57` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed `np.random.Generator` type-annotation false positive**
- **Found during:** Task 1 (RNG substrate, acceptance-criteria grep check)
- **Issue:** `grep -rn 'np\.random\.' src/nextmove/simulator | grep -v 'default_rng'` was
  meant to catch legacy global-RNG calls, but also matched the legitimate return-type
  annotation `np.random.Generator`.
- **Fix:** Imported `Generator` directly from `numpy.random` and used the bare name in
  annotations instead of `np.random.Generator`.
- **Files modified:** `src/nextmove/simulator/rng.py`
- **Verification:** The grep now outputs `0`; `uv run pytest tests/unit/test_rng_determinism.py`
  still passes.
- **Committed in:** `f23e4e5` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 missing critical config fields, 1 grep false-positive fix)
**Impact on plan:** All three were necessary for correctness (D-01's contrast claim, campaign
discount generation) or for the plan's own acceptance criteria to mean what they say. No scope
creep — both new config fields follow patterns plan 01-03 already established.

## Issues Encountered

- Initial `stream_rng` sentinel design used negative tick values (`-1`, `-2`, `-3`) to mark
  non-tick-indexed purpose-scoped draws. `numpy.random.SeedSequence` requires non-negative
  entropy, so this raised `ValueError: expected non-negative integer` at runtime. Switched to
  large positive sentinels (`>= 1_000_000_001`), verified no realistic `horizon_days` value
  can reach that range.
- `just lint`'s `ruff format --check` flagged two lines in `rng.py`/`world.py` that exceeded
  the 100-column limit after refactoring; resolved with `ruff format .` (commit `e752eb5`).

## User Setup Required

None - no external service configuration required.

## Known Limitations

- `category_affinity`'s *final* per-category value (post-softmax) has no closed-form
  "configured support" of its own, since it is a joint function of every category's raw draw,
  not a scalar. The plan's boundary/degenerate-at-support-min/max guarantee is proven instead
  against the shared underlying mechanism (`trait_support`/`draw_trait_value`) that all four
  traits use; the hypothesis property test separately confirms every final `category_affinity`
  component always lies in `(0, 1)` (a fortiori within the required inclusive `[0, 1]`).
  Documented explicitly here per the risk_note rather than writing a test that would pass
  vacuously against an undefined "support."
- The reproducibility proofs in `test_rng_determinism.py` (order-independence,
  population-independence) run within a single process, as they must for a unit-test suite.
  The claim also covers cross-process reproducibility structurally (a fresh `Generator` is
  built from the same explicit entropy list every call, with no process-local state), but that
  specific cross-process case is not independently exercised by an automated test in this plan.

## Next Phase Readiness

- `World.initialize`, `sample_latent_traits`, `entity_rng`/`stream_rng`, and `SimClock` are
  all available for plan 01-08's action-response functions and organic-behavior generation.
- `trait_support`/`draw_trait_value` are the one place distribution-family sampling/bounding
  logic lives; plan 01-08 should reuse them rather than re-deriving family-specific logic.
- The module docstrings in `traits.py` (distribution families, transform choices) are written
  ready for plan 01-11 to lift verbatim into `docs/SIMULATOR_ASSUMPTIONS.md` (SIM-03).
- Baseline preserved: `just lint` clean (2 kept / 0 broken import-linter contracts), `just test`
  207 passed, 1 skipped (same pre-existing POSIX-only RSS skip from plan 01-06).

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*

## Self-Check: PASSED

All 6 created files verified present on disk; all 5 commit hashes (`f23e4e5`, `286cc57`,
`50d91e2`, `e752eb5`, plus this SUMMARY's own `c354cbf`) verified present in `git log --all`.
