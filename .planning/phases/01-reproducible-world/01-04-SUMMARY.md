---
phase: 01-reproducible-world
plan: 04
subsystem: infra
tags: [import-linter, ci, github-actions, uv, ruff, pytest, ast]

# Dependency graph
requires:
  - phase: 01-reproducible-world (plan 01-01)
    provides: uv-managed pyproject.toml, justfile with default/setup/fmt/lint/test/reproduce recipes, thirteen src/nextmove/ packages each with a real __init__.py, tests/conftest.py repo_root fixture, slow marker registration
provides:
  - "[tool.importlinter] section in pyproject.toml: root_packages=[\"nextmove\"], include_external_packages=true"
  - "Contract one (simulator isolation, SIM-02): forbidden, source=[nextmove.models, nextmove.decisions, nextmove.policies, nextmove.features], forbidden=[nextmove.simulator]"
  - "Contract two (storage repository boundary, ENG-01): forbidden, source=all twelve non-storage packages, forbidden=[pyarrow, duckdb]"
  - "tests/fixtures/contract_probe/ permanent known-violating fixture package proving contract one's shape can go red"
  - "tests/unit/test_import_contract.py: three tests machine-proving non-vacuity and the storage boundary"
  - ".github/workflows/ci.yml: ubuntu-latest-only job running ruff check/format, lint-imports, pytest as separate named steps with no failure suppression"
  - "just lint extended with lint-imports; new just ci recipe mirroring the CI steps locally"
affects: [phase-2-onwards, "any plan adding a new src/nextmove/ package or a pyarrow/duckdb import"]

# Tech tracking
tech-stack:
  added: [import-linter (already a dev dependency from plan 01-01, now configured), astral-sh/setup-uv GitHub Action, extractions/setup-just GitHub Action]
  patterns:
    - "Forbidden import-linter contracts as the mechanical enforcement of architectural boundaries (SIM-02, ENG-01), verified non-vacuous via a permanent known-violating fixture package under tests/fixtures/, never under src/nextmove/"
    - "CI comment blocks as the recorded location for deferred-decision rationale (mypy/ENG-02 deferral), so the reasoning is visible in the artifact a future contributor actually reads"
    - "Consumers needing an Arrow type annotation import nextmove.storage's public Table alias rather than pyarrow directly, keeping the storage boundary contract unrelaxed"

key-files:
  created:
    - .github/workflows/ci.yml
    - tests/unit/test_import_contract.py
    - tests/fixtures/contract_probe/setup.cfg
    - tests/fixtures/contract_probe/probepkg/__init__.py
    - tests/fixtures/contract_probe/probepkg/simulator/__init__.py
    - tests/fixtures/contract_probe/probepkg/models/__init__.py
  modified:
    - pyproject.toml
    - justfile

key-decisions:
  - "Static type checking (mypy) deferred to Phase 2 / ENG-02, recorded as a comment inside .github/workflows/ci.yml itself rather than only in planning docs (review LOW-2)"
  - "No ignore/exemption or TYPE_CHECKING allowance on either import-linter contract; a consumer needing an Arrow type annotation must import nextmove.storage's public Table alias instead (review cycle 2 MEDIUM-6)"
  - "Contract acceptance-criteria grep gate ('no ignore_imports/unmatched_ignore') caught the pyproject.toml comment's own explanatory wording during Task 1 verification; comment was reworded to describe the sanctioned route without using either literal config-key string, and the gate now passes at 0 matches"

patterns-established:
  - "Pattern 1: import-linter forbidden contracts, declared once in pyproject.toml, run identically via `just lint`/`just ci` locally and `.github/workflows/ci.yml` in CI — no drift between local and CI enforcement"
  - "Pattern 2: non-vacuity of an architectural boundary contract is proven with a permanent fixture package (tests/fixtures/contract_probe/) that mirrors the production contract's exact shape, plus an assertion that the production report names every forbidden source package rather than only checking exit code"

requirements-completed: [SIM-02, ENG-01]

coverage:
  - id: D1
    description: "Import-linter contract one (SIM-02) forbids models/decisions/policies/features from importing nextmove.simulator, declared in pyproject.toml and passing on the clean tree"
    requirement: SIM-02
    verification:
      - kind: unit
        ref: "tests/unit/test_import_contract.py#test_production_contract_is_non_vacuous"
        status: pass
    human_judgment: false
  - id: D2
    description: "The SIM-02 contract is proven non-vacuous: a permanent known-violating fixture (probepkg.models importing probepkg.simulator) drives lint-imports to a non-zero exit naming both fixture modules"
    requirement: SIM-02
    verification:
      - kind: unit
        ref: "tests/unit/test_import_contract.py#test_probe_contract_goes_red_on_a_known_violation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Import-linter contract two (ENG-01) confines pyarrow/duckdb imports to nextmove.storage across all twelve other packages, backed by an AST file+line proof"
    requirement: ENG-01
    verification:
      - kind: unit
        ref: "tests/unit/test_import_contract.py#test_no_forbidden_source_package_imports_pyarrow_or_duckdb"
        status: pass
      - kind: unit
        ref: "tests/unit/test_import_contract.py#test_production_contract_is_non_vacuous"
        status: pass
    human_judgment: false
  - id: D4
    description: ".github/workflows/ci.yml runs a single ubuntu-latest job (D-16) — checkout, uv sync --frozen, ruff check, ruff format --check, lint-imports, pytest as separate named steps with no continue-on-error/`|| true`/Windows matrix leg — reproducible locally via `just ci`"
    requirement: null
    verification:
      - kind: other
        ref: "just ci (local reproduction, exit 0) plus grep-based structural checks: continue-on-error=0, '|| true'=0, windows(ci)=0"
        status: pass
    human_judgment: false
  - id: D5
    description: "Deferred static-type-checking decision (mypy/ENG-02, review LOW-2) recorded as a comment inside .github/workflows/ci.yml, naming the tool, Phase 2, ENG-02, and the one-line reason, with no type-checker step actually invoked"
    verification:
      - kind: other
        ref: "grep -c mypy .github/workflows/ci.yml >=1; grep -c ENG-02 .github/workflows/ci.yml >=1; no mypy invocation step present"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-04
status: complete
---

# Phase 1 Plan 04: Import-Boundary CI Enforcement Summary

**Import-linter forbidden contracts making SIM-02 (simulator isolation) and ENG-01 (storage repository boundary) mechanically true, wired into a Linux-only GitHub Actions workflow with a permanent known-violating fixture proving the contracts are non-vacuous.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-04T16:24:33Z (approx, per STATE.md session start)
- **Completed:** 2026-08-04T16:33:05Z
- **Tasks:** 3 completed
- **Files modified:** 8 (2 modified: pyproject.toml, justfile; 6 created: ci.yml, test_import_contract.py, and the 4 contract_probe fixture files)

## Accomplishments

- `[tool.importlinter]` declared in `pyproject.toml` with two `forbidden` contracts: simulator isolation (SIM-02 — `nextmove.models`, `nextmove.decisions`, `nextmove.policies`, `nextmove.features` forbidden from importing `nextmove.simulator`) and storage repository boundary (ENG-01 — all twelve non-storage packages forbidden from importing `pyarrow` or `duckdb`). `uv run lint-imports --verbose` names all four SIM-02 source packages, proving the contract resolved real modules rather than an empty set.
- A permanent, self-contained known-violating fixture package (`tests/fixtures/contract_probe/probepkg/`, living outside `src/nextmove/`) mirrors contract one's exact shape and machine-proves a forbidden contract of this shape can actually go red: `lint-imports --config tests/fixtures/contract_probe/setup.cfg` exits 1 and names both `probepkg.models` and `probepkg.simulator` in its report.
- `tests/unit/test_import_contract.py` adds three tests: non-vacuous fail-first proof against the fixture, non-vacuity assertion on the production contract's verbose output (not just exit code), and an AST-based file+line walk of `src/nextmove/` (excluding `storage/`) asserting no forbidden-source package imports `pyarrow` or `duckdb`.
- `.github/workflows/ci.yml` runs a single `checks` job on `ubuntu-latest` only (no Windows matrix leg, per D-16), with checkout, `astral-sh/setup-uv`, `extractions/setup-just`, `uv sync --frozen`, then `ruff check`, `ruff format --check`, `lint-imports`, and `pytest -q` as four separate named steps, none carrying `continue-on-error` or a `|| true` fallback. A trailing comment names plan 01-11 as the owner of the end-to-end/golden-comparison steps and records the deferred mypy/ENG-02 static-type-checking decision (review LOW-2) with its one-line reason, directly in the file a future reader would consult.
- `justfile`'s existing `lint` recipe now also runs `lint-imports`; a new `ci` recipe reproduces the four CI steps locally in the same order (`just ci` exits 0).

## Task Commits

Each task was committed atomically:

1. **Task 1: Declare the import-linter contracts** - `443913d` (feat)
2. **Task 2: Prove the contract has teeth with a known-violating fixture** - `cf4f627` (test)
3. **Task 3: Wire the Linux-only CI workflow** - `71378d3` (feat)

**Plan metadata:** commit pending (docs: complete plan)

## Files Created/Modified

- `pyproject.toml` - Added `[tool.importlinter]` with `root_packages`, `include_external_packages`, and two `forbidden` contracts (simulator isolation, storage boundary); comment beside contract two names the sanctioned `Table` alias route
- `justfile` - Extended `lint` recipe with `lint-imports`; added new `ci` recipe
- `.github/workflows/ci.yml` - New single-job (`checks`), `ubuntu-latest`-only CI workflow
- `tests/unit/test_import_contract.py` - Three tests machine-proving contract non-vacuity and the storage boundary
- `tests/fixtures/contract_probe/setup.cfg` - INI-form import-linter config mirroring production contract one
- `tests/fixtures/contract_probe/probepkg/__init__.py` - Probe root package (docstring only)
- `tests/fixtures/contract_probe/probepkg/simulator/__init__.py` - Probe simulator stand-in (trivial function)
- `tests/fixtures/contract_probe/probepkg/models/__init__.py` - Probe models stand-in with the deliberate violating import

## Decisions Made

- **Static type checking deferred to Phase 2 / ENG-02** (review LOW-2): recorded as a comment inside `.github/workflows/ci.yml` itself — names `mypy`, Phase 2, `ENG-02`, and the reason (the typed plugin registries a checker would protect don't exist until Phase 2, and D-16 forbids a non-blocking step, so an earlier introduction would be a hard gate failing for reasons unrelated to this phase). No `mypy` step is invoked. **Accepted cost, carried forward explicitly here per this plan's `<output>` instruction:** Phase 1 ships without a static type gate, so a type error that neither Pydantic's `extra="forbid"` validation nor a test exercises can reach `main`. The obligation to close this belongs to Phase 2 alongside ENG-02.
- **No carve-out on either import-linter contract** (review cycle 2, MEDIUM-6): neither contract declares an exemption or a `TYPE_CHECKING` allowance. A consumer package that must name an Arrow type in an annotation imports the public `Table` alias `nextmove.storage` re-exports (plan 01-06) instead of importing `pyarrow` directly; plan 01-10's `compute_as_of` is the Phase 1 caller of this pattern.
- **Flagged SIM-02 assumption restated for phase verification** (per this plan's frontmatter and `<output>` instruction): the original edge probe returned SIM-02 as unclassified, unable to auto-derive a predicate. This plan closes the "vacuous enforcement" half of that risk (known-violating fixture + forbidden-source-package naming assertion) and the "TYPE_CHECKING-guarded import" half (MEDIUM-6 decision, no carve-out, above). **One edge remains explicitly open and unaddressed by this plan:** a transitive re-export chain that could carry a simulator symbol into a forbidden source package without a direct import from that package. `include_external_packages = true` and import-linter's own transitive-chain detection (per RESEARCH's "Don't Hand-Roll" table) are believed to cover this, but no dedicated test in this plan constructs a re-export-chain fixture to prove it the way Task 2 proves a direct import. This should be raised explicitly before phase verification closes SIM-02.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded pyproject.toml comment to avoid tripping its own acceptance-criteria grep gate**
- **Found during:** Task 1 verification
- **Issue:** The acceptance criterion `grep -ci 'ignore_imports\|unmatched_ignore' pyproject.toml` outputs `0` is meant to assert neither import-linter config key is used, but the explanatory comment required by a separate acceptance criterion (naming the sanctioned `Table`-alias route) initially used the literal phrase "no ignore_imports / TYPE_CHECKING allowance," which the grep gate treats as a match regardless of context.
- **Fix:** Reworded the comment to "no exemption or TYPE_CHECKING allowance is configured on this contract," preserving the required meaning (names the sanctioned route, states no carve-out exists) without using either literal config-key string.
- **Files modified:** `pyproject.toml`
- **Verification:** `grep -c 'ignore_imports\|unmatched_ignore' pyproject.toml` now outputs `0`; `uv run lint-imports` still exits 0 and both contracts still report `KEPT`.
- **Committed in:** `443913d` (Task 1 commit — fixed before commit, not a separate commit)

**2. [Rule 3 - Blocking] `python -m importlinter` has no `__main__` entry point; resolved the `lint-imports` console script directly**
- **Found during:** Task 2, writing the subprocess-based tests
- **Issue:** The plan's action text describes running `lint-imports` as a subprocess but the natural first implementation (`python -m importlinter`) fails with "No module named importlinter.__main__; 'importlinter' is a package and cannot be directly executed" — there is no `__main__.py` in the installed package.
- **Fix:** Added a `_lint_imports_executable()` helper that locates the `lint-imports` console script via `shutil.which` (works because the `uv run pytest` invocation puts the venv's `Scripts`/`bin` directory on `PATH`), falling back to a path built from `sys.executable`'s directory for interpreters invoked without that PATH entry.
- **Files modified:** `tests/unit/test_import_contract.py`
- **Verification:** Both subprocess-based tests (`test_probe_contract_goes_red_on_a_known_violation`, `test_production_contract_is_non_vacuous`) pass on Windows.
- **Committed in:** `cf4f627` (Task 2 commit)

**3. [Rule 1 - Bug] Line-length lint errors in the new test file, fixed with `ruff format` plus one manual split**
- **Found during:** Task 2, pre-commit `just lint` check
- **Issue:** Three f-strings in `test_no_forbidden_source_package_imports_pyarrow_or_duckdb` exceeded the 100-character line limit configured in `[tool.ruff]`.
- **Fix:** Ran `uv run ruff format` to auto-wrap two of the three; manually extracted a `location` local variable to shorten the third line under the limit. Also removed an unused `_iter_imported_root_names` helper left over from an earlier draft of the same test, since the final test inlines its own AST walk for a more precise file+line failure message.
- **Files modified:** `tests/unit/test_import_contract.py`
- **Verification:** `uv run ruff check .` and `uv run ruff format --check .` both pass; full test suite (`uv run pytest -q`, 73 tests) green.
- **Committed in:** `cf4f627` (Task 2 commit — fixed before commit, not a separate commit)

---

**Total deviations:** 3 auto-fixed (1 bug — gate-tripping comment wording, 1 blocking — no `python -m importlinter` entry point, 1 bug — line-length/dead-code cleanup)
**Impact on plan:** All three were pre-commit corrections within the scope of the task being executed; no scope creep, no architectural change, no deviation from the contracts' declared shape or the CI workflow's declared steps.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required. Note: `.github/workflows/ci.yml` will not run anywhere yet since this repository has no configured git remote; this is expected per the execution environment notes and does not block the plan's completion.

## Next Phase Readiness

- SIM-02 and ENG-01 are now mechanically enforced locally (`just lint`, `just ci`) and would be enforced in CI once a remote exists.
- Plan 01-11 has a clearly marked append point in `.github/workflows/ci.yml` for the end-to-end and golden-comparison steps, and must not rewrite the file.
- Plan 01-06 (storage's public `Table` alias) and plan 01-10 (`compute_as_of` as its Phase 1 caller) are now load-bearing for contract two staying carve-out-free — any plan that needs an Arrow-typed annotation outside `nextmove.storage` must use that alias rather than importing `pyarrow` directly, or the contract will fail CI.
- **Open item for phase verification:** the transitive re-export edge for SIM-02 (see Decisions Made above) has no dedicated fixture-based proof in this plan and should be explicitly checked or accepted before phase verification closes SIM-02.
- Phase 2 owns adding a `mypy` step to `.github/workflows/ci.yml` alongside ENG-02's typed plugin registries.

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*

## Self-Check: PASSED

All 6 created files verified present on disk. All 3 task commits (`443913d`, `cf4f627`, `71378d3`) verified present in git log.
