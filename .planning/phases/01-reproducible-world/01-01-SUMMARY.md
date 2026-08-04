---
phase: 01-reproducible-world
plan: 01
subsystem: infra
tags: [uv, python312, ruff, pytest, just, make, hatchling, modular-monolith, dvc, mlflow, import-linter]

# Dependency graph
requires: []
provides:
  - "uv-managed Python 3.12 project (pyproject.toml, .python-version, uv.lock) installing offline from a hash-pinned lockfile"
  - "src-layout src/nextmove/ with the eleven ENG-01 package boundaries plus config/ and storage/ infrastructure packages, all real importable modules"
  - "justfile operational interface (default, setup, fmt, lint, test, reproduce) with a 3-line Makefile forward for make reproduce"
  - "pytest harness (tests/{unit,integration,property,golden,leakage}/) with conftest.py fixtures (tiny_profile_name, repo_root) and the package-inventory test"
  - "Ratified package-legitimacy verdict for the ten core dependencies, with the dvc org discrepancy explicitly corrected"
affects: [01-02, 01-03, 01-04, 01-06, 01-11]

# Tech tracking
tech-stack:
  added: [uv 0.11.29, just (rust-just 1.58.0), ruff 0.16.1, pytest 9.1.1, pydantic 2.13.4, pyarrow 25.0.0, duckdb 1.5.5, pandera 0.32.1, dvc 3.67.1, mlflow 3.15.1, import-linter 2.13, hypothesis 6.165.0]
  patterns:
    - "src/ layout package discovery via hatchling ([tool.hatch.build.targets.wheel] packages = [\"src/nextmove\"])"
    - "Every package boundary (even stubs) ships a real __init__.py with a docstring + __all__: list[str] = [] so import-linter registers it as a real module (RESEARCH Pitfall 4)"
    - "config/ and storage/ are cross-cutting infrastructure, explicitly not counted among the eleven ENG-01 packages"
    - "justfile is the operational interface; Makefile is a pure 3-line forward (D-14)"

key-files:
  created:
    - pyproject.toml
    - .python-version
    - .gitignore
    - uv.lock
    - justfile
    - Makefile
    - src/nextmove/__init__.py
    - src/nextmove/{simulator,ingest,features,segmentation,models,rules,decisions,policies,explain,evaluate,api,config,storage}/__init__.py
    - tests/conftest.py
    - tests/unit/test_package_layout.py
  modified: []

key-decisions:
  - "Package legitimacy checkpoint (Task 1) approved by the human developer: dvc's canonical repo confirmed as github.com/iterative/dvc (the legitimacy seam had returned github.com/treeverse/dvc, which is wrong — treeverse owns lakeFS, an unrelated product); the remaining nine core packages (pydantic, pyarrow, duckdb, import-linter, mlflow, pandera, ruff, numpy, pandas) confirmed to resolve to their canonical GitHub orgs on PyPI"
  - "Excluded .planning/, docs/, and *.md from ruff's format scope (extend-exclude) after discovering ruff format --check . reformats fenced Python code blocks inside Markdown by default, which reached into 01-RESEARCH.md's code examples and broke just lint"

patterns-established:
  - "Rule 1 auto-fix: ruff extend-exclude scopes lint/format to actual source, keeping planning docs untouched by tooling"

requirements-completed: [ENG-01, ENG-08]

coverage:
  - id: D1
    description: "uv sync on a clean clone creates a Python 3.12 virtualenv and a hash-pinned uv.lock offline, no cloud/container required"
    requirement: "ENG-08"
    verification:
      - kind: other
        ref: "uv sync && uv run python -c \"import sys; assert sys.version_info[:2]==(3,12)\""
        status: pass
      - kind: other
        ref: "test -f uv.lock && git ls-files uv.lock"
        status: pass
    human_judgment: false
  - id: D2
    description: "src/nextmove/ contains exactly the eleven ENG-01 packages plus config/storage infrastructure (13 total), each with a real importable __init__.py"
    requirement: "ENG-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_package_layout.py#test_package_inventory_is_exactly_thirteen"
        status: pass
      - kind: unit
        ref: "tests/unit/test_package_layout.py#test_every_package_is_importable"
        status: pass
      - kind: unit
        ref: "tests/unit/test_package_layout.py#test_every_eng01_package_has_a_docstring"
        status: pass
    human_judgment: false
  - id: D3
    description: "just lint and just test both exit 0; make reproduce forwards to just reproduce through a 3-line Makefile"
    requirement: "ENG-08"
    verification:
      - kind: other
        ref: "just lint (exit 0)"
        status: pass
      - kind: other
        ref: "just test (exit 0)"
        status: pass
      - kind: other
        ref: "make reproduce (invokes just reproduce; exits non-zero as intended until plan 01-11 wires the DVC pipeline)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Package legitimacy of all ten core dependencies ratified by human before any install, including the dvc org correction"
    verification: []
    human_judgment: true
    rationale: "Task 1 is a checkpoint:human-verify with gate=\"blocking-human\" per the plan's threat register (T-01-SC) — package legitimacy for a supply-chain-sensitive install cannot be auto-verified or waved through by a machine; it required and received explicit human confirmation before Task 2's first uv add/uv sync."

duration: ~30min
completed: 2026-08-04
status: complete
---

# Phase 01 Plan 01: Reproducible World — Repository Floor Summary

**uv-managed Python 3.12 project with hash-pinned lockfile, the eleven-package `src/nextmove/`
modular-monolith layout, a `just`/`make` operational interface, and a green pytest harness — all
gated by an explicitly-approved package-legitimacy checkpoint before the first install.**

## Performance

- **Duration:** ~30 min (across a checkpoint pause for human verification)
- **Started:** 2026-08-04T15:26:00Z
- **Completed:** 2026-08-04T15:56:00Z
- **Tasks:** 3 (1 checkpoint + 2 auto)
- **Files modified:** 22

## Accomplishments
- `pyproject.toml` defines a `uv` project (`nextmove` 0.1.0, Python 3.12 pin, src-layout via
  hatchling) with runtime deps (`pydantic`, `pyarrow`, `duckdb`, `pandera`, `pyyaml`, `numpy`,
  `pandas`) and a dev dependency group (`dvc`, `mlflow`, `import-linter`, `ruff`, `pytest`,
  `pytest-cov`, `hypothesis`); `uv sync` resolves and installs 172 packages offline from
  `uv.lock`, all matching RESEARCH.md's verified version snapshot (with minor patch drift noted
  below).
- All thirteen `src/nextmove/` package boundaries exist as real, importable, docstring-carrying
  modules: the eleven ENG-01 packages (`simulator`, `ingest`, `features`, `segmentation`,
  `models`, `rules`, `decisions`, `policies`, `explain`, `evaluate`, `api`) plus the `config` and
  `storage` cross-cutting infrastructure packages — guarding against RESEARCH Pitfall 4
  (import-linter registering stub directories vacuously).
- `justfile` (`default`, `setup`, `fmt`, `lint`, `test`, `reproduce`) is the operational
  interface; `Makefile` is exactly 3 non-blank lines forwarding `make reproduce` → `just
  reproduce` (D-14).
- pytest harness is green: `tests/conftest.py` exposes `tiny_profile_name` and `repo_root`
  fixtures; `tests/unit/test_package_layout.py` asserts the package set with `==` (not a subset
  check) so both additions and removals fail the test.
- The package-legitimacy checkpoint (Task 1) was presented and explicitly approved by the human
  developer before any `uv add`/`uv sync` ran — see Decisions Made below for the verdict.

## Task Commits

1. **Task 1: Ratify package legitimacy before any dependency install** — checkpoint only, no
   files changed; verdict recorded below and in this SUMMARY per the plan's acceptance criteria.
2. **Task 2: Create the uv project, dependency set, and operational interface** — `ea3e8fa` (feat)
3. **Task 3: Scaffold the eleven package boundaries and the pytest harness** — `f19bc8c` (feat)
4. **Deviation fix: ruff Markdown-formatting scope** — `77a7d7e` (fix)

**Plan metadata:** commit to follow (docs: complete plan)

## Files Created/Modified
- `pyproject.toml` — uv project definition, Python 3.12 pin, ruff/pytest/coverage config,
  `extend-exclude` for planning docs
- `.python-version` — pins `3.12` (machine also has 3.14 installed)
- `.gitignore` — venv/cache/build artifacts, `data/` (DVC-tracked, never git-tracked)
- `uv.lock` — hash-pinned resolution of 172 packages
- `justfile` — operational interface recipes
- `Makefile` — 3-line forward to `just reproduce`
- `src/nextmove/__init__.py` — `__version__ = "0.1.0"`
- `src/nextmove/{simulator,ingest,features,segmentation,models,rules,decisions,policies,explain,evaluate,api}/__init__.py`
  — the eleven ENG-01 package boundaries, each with a responsibility + populating-phase docstring
- `src/nextmove/{config,storage}/__init__.py` — cross-cutting infrastructure boundaries
- `tests/conftest.py` — `tiny_profile_name`, `repo_root` fixtures
- `tests/unit/test_package_layout.py` — package-inventory + importability + docstring assertions
- `tests/{unit,integration,property,golden,leakage}/` — empty test-tree directories for later plans

## Decisions Made

- **Task 1 checkpoint verdict (recorded verbatim per plan requirement):** The human developer
  verified `pypi.org/project/dvc/` and confirmed the Source/Homepage links resolve to
  `github.com/iterative/dvc`, **not** `github.com/treeverse/...` (treeverse owns lakeFS, an
  unrelated product — the package-legitimacy seam's `repoUrl` lookup for `dvc` was factually
  wrong). The developer also confirmed the remaining nine packages (`pydantic`, `pyarrow`,
  `duckdb`, `import-linter`, `mlflow`, `pandera`, `ruff`, `numpy`, `pandas`) resolve to their
  canonical GitHub organizations. Coordinator relayed: "The user verified the package legitimacy
  checkpoint and approved... `dvc` → confirmed canonical repo is `github.com/iterative/dvc`...
  the remaining nine packages resolve to their expected canonical orgs." No `uv add`/`uv sync`
  ran before this approval. **Resolution: approved.**
- Resolved dependency versions from `uv.lock` (drift from RESEARCH.md's 2026-07-25 snapshot noted
  where present): `pydantic==2.13.4` (match), `pyarrow==25.0.0` (match), `duckdb==1.5.5`
  (RESEARCH cited 1.5.4 — one patch newer, within the `>=1.5,<2` bound), `dvc==3.67.1` (match),
  `mlflow==3.15.1` (RESEARCH cited 3.14.0 — newer minor, within the `>=3.14` bound),
  `import-linter==2.13` (match), `ruff==0.16.1` (RESEARCH cited 0.16.0 — one patch newer, within
  the `>=0.16` bound), `numpy==2.5.1` (match), `pandas==2.3.3` (match), `pandera==0.32.1`
  (match). All drift is forward-compatible patch/minor movement within the plan's declared
  version bounds — no action needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff format reformats fenced Python code blocks inside planning Markdown docs**
- **Found during:** Task 3 verification (`just lint`)
- **Issue:** `ruff format --check .` by default discovers and would reformat fenced Python code
  examples embedded in `.planning/phases/01-reproducible-world/01-RESEARCH.md`, causing `just
  lint` to fail with unrelated diffs against a documentation file that isn't part of this
  project's source.
- **Fix:** Added `extend-exclude = [".planning", "docs", "*.md"]` under `[tool.ruff]` in
  `pyproject.toml` so ruff's lint/format scope stays limited to actual source (`src/`, `tests/`).
- **Files modified:** `pyproject.toml`
- **Verification:** `just lint` and `just test` both exit 0 after the fix; `uv run ruff format
  --check .` reports "16 files already formatted" with no Markdown files touched.
- **Committed in:** `77a7d7e`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for `just lint` to pass per the plan's own verification criterion
("Running `just lint` and `just test` concurrently produces the same pass/fail verdicts... and
neither writes into `src/nextmove/`"). No scope creep — the fix only scopes an existing tool
config, adds no new files, and touches no `src/nextmove/` code.

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None — no external service configuration required. `just` was installed locally via
`uv tool install rust-just` as part of Task 2 (per RESEARCH §Environment Availability, which
recorded `just` as absent on this machine).

## Next Phase Readiness

- The repository floor is in place: `uv sync`, `just lint`, `just test` all pass; `make
  reproduce` correctly forwards to `just reproduce` and exits non-zero until plan 01-11 wires the
  real DVC pipeline.
- All thirteen `src/nextmove/` packages are real, importable modules — plan 01-04 (import-linter
  contract) has real targets to enforce against rather than vacuous stub directories.
- `config/` and `storage/` package boundaries exist and are ready for plans 01-03 and 01-06 to
  populate.
- `pyproject.toml` deliberately omits `[tool.importlinter]` — plan 01-04 owns that section.
- No blockers for plan 01-02.

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*
