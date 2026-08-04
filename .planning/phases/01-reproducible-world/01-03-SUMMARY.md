---
phase: 01-reproducible-world
plan: 03
subsystem: infra
tags: [pydantic, pyyaml, config, hashing, determinism]

# Dependency graph
requires:
  - phase: 01-reproducible-world (plan 01-01)
    provides: uv-managed Python 3.12 project, src/nextmove/ package boundaries, empty
      src/nextmove/config/__init__.py stub, tests/conftest.py fixtures
provides:
  - Pydantic v2 config schema (Config + 18 domain/leaf models) with extra="forbid" on every
    model, forcing unknown/typo'd keys to fail loudly
  - Layered config loader: deep_merge, load_config, config_hash, ResolvedConfig
  - A stable sha256 hash over the resolved merged config, immune to YAML key order and
    dict insertion order
  - The full config/ tree: eight per-domain base YAML files plus four thin profile
    overlays (default, demo, ci, tiny)
affects: [01-04, 01-05, 01-06, 01-07, 01-08, 01-09, 01-10, 01-11]

# Tech tracking
tech-stack:
  added: []  # pydantic and pyyaml were already project dependencies from plan 01-01
  patterns:
    - "StrictModel base (extra=forbid, frozen=True, validate_default=True) inherited by
      every config model — the single load-bearing setting that makes a typo'd config key
      a loud ValidationError instead of a silent no-op"
    - "Layered config resolution: N base domain files merged in a fixed declared order,
      then one thin profile overlay merged on top, then Pydantic validates the merged
      result as a whole (never per-file)"
    - "Canonical hash = sha256(json.dumps(model.model_dump(mode='json'), sort_keys=True,
      separators=(',', ':'))) — the only hash-safe serialization of a resolved config"

key-files:
  created:
    - src/nextmove/config/models.py
    - src/nextmove/config/loader.py
    - config/simulator.yaml
    - config/features.yaml
    - config/data_quality.yaml
    - config/constraints.yaml
    - config/actions.yaml
    - config/mcda.yaml
    - config/experiments.yaml
    - config/autonomy.yaml
    - config/profiles/default.yaml
    - config/profiles/demo.yaml
    - config/profiles/ci.yaml
    - config/profiles/tiny.yaml
    - tests/unit/test_config_merge_hash.py
    - tests/unit/test_config_validates.py
  modified:
    - src/nextmove/config/__init__.py

key-decisions:
  - "Added config/data_quality.yaml as an eighth per-domain base file (flagged planner
    extension to D-23's seven-file enumeration) — D-21's reject-rate threshold needs a
    YAML home and none of D-23's seven named domains is an ingest/data-quality domain"
  - "Added config/profiles/tiny.yaml as a fourth profile (flagged planner extension to
    D-23's three-profile list) — ~100 customers / ~30 day horizon for unit tests that
    must not pay the ci profile's cost; RESEARCH.md Wave 0 Gaps called for this"
  - "The resolved profile field participates in the config hash (it is a real field on
    Config, set by the loader before validation) — two different profiles never hash
    identically even with otherwise-identical content, which is the correct behavior per
    D-24 ('the hash captures exactly what it ran with')"
  - "Latent trait distribution families chosen: price_sensitivity=beta(2.0,5.0),
    loyalty=beta(2.5,4.0), fatigue=lognormal(mu=-1.2,sigma=0.6),
    category_affinity=normal(mu=0.0,sigma=1.0) — recorded here verbatim per SIM-03 for
    plan 01-11's docs/SIMULATOR_ASSUMPTIONS.md to reproduce"

patterns-established:
  - "Pattern: minimal Phase-2/3/4 placeholder domains (ConstraintsConfig, ActionsConfig,
    McdaConfig, ExperimentsConfig) are empty StrictModel subclasses with default_factory
    on the Config root, so their YAML files can be comment-only today and still forbid
    extra keys the moment a later phase adds real fields"

requirements-completed: [ENG-03, ENG-04]

coverage:
  - id: D1
    description: "Pydantic config schema for every domain, extra keys forbidden, models
      immutable once validated"
    requirement: "ENG-03"
    verification:
      - kind: unit
        ref: "tests/unit/test_config_merge_hash.py#test_overlay_undeclared_key_raises_validation_error_naming_it"
        status: pass
      - kind: other
        ref: "uv run python -c \"from nextmove.config import Config; print(Config.model_config['extra'], Config.model_config['frozen'])\" -> forbid True"
        status: pass
    human_judgment: false
  - id: D2
    description: "Layered loader (deep merge + profile overlay) validates the merged
      result through Pydantic and computes a stable, key-order-immune sha256 config hash"
    requirement: "ENG-04"
    verification:
      - kind: unit
        ref: "tests/unit/test_config_merge_hash.py (11 tests: deep_merge purity, empty
          overlay == base hash, YAML key-order and dict-insertion-order hash stability,
          64-char hex hash, traversal rejection, unknown-profile error message)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full config/ tree (eight domain files, four profile overlays) loads,
      validates, and hashes distinctly and stably against the real repository tree"
    requirement: "ENG-03"
    verification:
      - kind: unit
        ref: "tests/unit/test_config_validates.py (15 tests: all four profiles load,
          distinct hashes, repeat-load stability, autonomy tier disjointness, <15
          non-blank-line overlays)"
        status: pass
    human_judgment: false

duration: 30min
completed: 2026-08-04
status: complete
---

# Phase 1 Plan 3: Configuration Substrate Summary

**Layered per-domain YAML config (D-23) validated end-to-end by a Pydantic v2 model tree
with `extra="forbid"`, hashed via sort-keys canonical JSON + sha256 (D-24), with seeds as
hashed config values (D-25) — four profiles (default/demo/ci/tiny) all load and hash
distinctly against the real repo config tree.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-08-04T16:08:34Z (STATE.md session start)
- **Completed:** 2026-08-04T16:22:54Z
- **Tasks:** 3
- **Files modified:** 16 (1 modified, 15 created)

## Accomplishments

- Full Pydantic v2 schema (`src/nextmove/config/models.py`): 18 domain/leaf models plus the
  `Config` root, every one forbidding unknown keys and frozen once validated
- `src/nextmove/config/loader.py`: hand-written `deep_merge` (never a dependency, per
  RESEARCH's "Don't Hand-Roll" guidance), `load_config` reading eight base domain files in
  a fixed order plus a profile overlay, `config_hash` over the canonicalized resolved merge
- The real `config/` tree: `simulator.yaml` (fashion-core + one contrast category, 50k/18mo
  default scale, four latent traits, December seasonality peak, D-04's loophole toggle,
  D-25 seeds), `features.yaml` (12 FEAT-01 feature specs), `data_quality.yaml` (D-21
  threshold + DATA-03's three semantic gates), `autonomy.yaml` (D-12's three
  pairwise-disjoint tiers), four minimal Phase-2/3/4 placeholder files, and four thin
  profile overlays (each under 15 non-blank lines)
- 26 new unit tests (11 in `test_config_merge_hash.py` against `tmp_path` fixtures, 15 in
  `test_config_validates.py` against the real repo config tree) — full suite now at 70
  tests, all passing; `just lint` and `just test` both exit 0

## Task Commits

Each task was committed atomically:

1. **Task 1: Define the Pydantic config models for every domain** - `6086ce8` (feat)
2. **Task 2: Implement the layered loader, deep merge, and canonical config hash** - `188ef97` (feat)
3. **Task 3: Author the config tree — eight domain files and four profile overlays** - `666e216` (feat)

**Plan metadata:** _(pending — see final commit below)_

## Files Created/Modified

- `src/nextmove/config/models.py` - `StrictModel` base plus 18 domain/leaf models and the
  `Config` root (simulator, features, data_quality, constraints, actions, mcda,
  experiments, autonomy, profile)
- `src/nextmove/config/__init__.py` - re-exports `Config` and every domain model
- `src/nextmove/config/loader.py` - `deep_merge`, `ResolvedConfig`, `config_hash`,
  `load_config`, `BASE_DOMAIN_FILES`
- `config/simulator.yaml`, `config/features.yaml`, `config/data_quality.yaml`,
  `config/constraints.yaml`, `config/actions.yaml`, `config/mcda.yaml`,
  `config/experiments.yaml`, `config/autonomy.yaml` - the eight per-domain base files
- `config/profiles/default.yaml`, `config/profiles/demo.yaml`, `config/profiles/ci.yaml`,
  `config/profiles/tiny.yaml` - the four thin profile overlays
- `tests/unit/test_config_merge_hash.py` - merge/hash unit tests against `tmp_path` only
- `tests/unit/test_config_validates.py` - validates the real repo `config/` tree

## Decisions Made

- **`config/data_quality.yaml` added as an eighth base domain file** (flagged planner
  extension to D-23's seven-file enumeration, per the plan's own `<planner_notes>`): D-21
  requires the reject-rate threshold in YAML per ENG-03, and none of D-23's seven named
  domains (`simulator`, `features`, `constraints`, `actions`, `mcda`, `experiments`,
  `autonomy`) is an ingest/data-quality domain. `BASE_DOMAIN_FILES` in `loader.py` now
  lists eight entries, not seven.
- **`config/profiles/tiny.yaml` added as a fourth profile** (flagged planner extension to
  D-23's three-profile list, per the plan's `<planner_notes>`): RESEARCH.md's Wave 0 Gaps
  called for a ~50-100 customer profile for unit-level tests that must not pay the `ci`
  profile's cost. `tests/conftest.py`'s pre-existing `tiny_profile_name` fixture (from plan
  01-01) now resolves against a real profile file.
- **Latent trait distribution families and parameters** (must be reproduced verbatim in
  `docs/SIMULATOR_ASSUMPTIONS.md` by plan 01-11 per SIM-03):
  - `price_sensitivity`: beta(alpha=2.0, beta=5.0)
  - `loyalty`: beta(alpha=2.5, beta=4.0)
  - `fatigue`: lognormal(mu=-1.2, sigma=0.6)
  - `category_affinity`: normal(mu=0.0, sigma=1.0)
- **Profile name is part of the hashed surface.** `load_config` sets `profile` on the
  merged dict before validation, and `profile: str` is a real field on `Config` — so
  `config_hash` differs across profiles even when every other value is identical. This
  matches D-24's stated intent ("a run's hash captures exactly what it ran with") and is
  exercised by `test_all_four_profiles_produce_distinct_hashes`.
- **Domain placeholder models are empty, not stubbed with speculative fields.**
  `ConstraintsConfig`, `ActionsConfig`, `McdaConfig`, `ExperimentsConfig` declare zero
  fields today; their YAML files are comment-only. Because they still inherit
  `StrictModel` (`extra="forbid"`), the moment Phase 2/3/4 adds a real field, any
  unrecognized sibling key in the YAML fails validation immediately.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ruff format` reformatted the new loader/test files**
- **Found during:** Task 3, running `just lint`
- **Issue:** `just lint` runs both `ruff check` and `ruff format --check`; two files
  (`test_config_merge_hash.py`, `test_config_validates.py`) had lines the formatter wanted
  wrapped differently than initially written
- **Fix:** Ran `uv run ruff format src/nextmove tests`; no logic changed
- **Files modified:** `tests/unit/test_config_merge_hash.py`, `tests/unit/test_config_validates.py`
- **Verification:** `just lint` now exits 0 (both `ruff check` and `ruff format --check`)
- **Committed in:** `666e216` (part of Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking/formatting)
**Impact on plan:** Cosmetic only. No scope creep.

## Known Limitations (not deviations — pre-existing plan defect)

**Task 3's acceptance criterion `grep -rn 'n_customers' src/nextmove | wc -l` outputs `0`
is not satisfiable as literally stated, and was not force-fixed.** Task 1's own action
block explicitly requires `SimulatorConfig` to declare a Python field named `n_customers:
int` — the schema cannot validate `n_customers` from YAML without a field of that name
existing somewhere in `src/nextmove/config/models.py`. The criterion's stated intent ("the
population size is config, never a code literal") is satisfied: `n_customers` has no
default value in the model (it is a required field with no numeric literal attached), so
no *population number* is hardcoded anywhere in `src/nextmove/`. The grep, however, also
matches the field-name identifier itself (`grep -rn 'n_customers' src/nextmove` currently
returns 1 real match, in `models.py`'s field declaration, plus one bytecode-cache false
positive). Renaming the field to dodge this grep would contradict Task 1's explicit
instruction and Task 3's own instruction that `config/simulator.yaml` use the YAML key
`n_customers`. Left as-is; flagging here rather than silently claiming the criterion
passed.

## Issues Encountered

None beyond the formatting deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Every later Phase 1 plan can now call `nextmove.config.loader.load_config(profile)` to
  get a validated `Config` plus a stable `config_hash` — no plan after this one should ever
  introduce a bare numeric/string business literal into `src/nextmove/`.
- `tests/conftest.py`'s `tiny_profile_name` fixture (added in plan 01-01) is now backed by
  a real `config/profiles/tiny.yaml`; downstream unit tests can depend on it directly.
- No blockers. `just lint` and `just test` both exit 0 (70 tests, up from 44 at the end of
  plan 01-02).

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*

## Self-Check: PASSED

All 16 created/modified files verified present on disk; all 3 task commits (`6086ce8`,
`188ef97`, `666e216`) verified present in git log.
