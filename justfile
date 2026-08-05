default:
    just --list

# Create/sync the uv-managed virtual environment from uv.lock
setup:
    uv sync

# Auto-format the codebase
fmt:
    uv run ruff format .

# Lint + format-check + import-boundary contracts (CI-equivalent gate)
lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run lint-imports

# Run the test suite
test:
    uv run pytest -x -q

# Reproduce the CI verdict locally (same steps, same order, as .github/workflows/ci.yml)
ci:
    uv run ruff check .
    uv run ruff format --check .
    uv run lint-imports
    uv run pytest -q

# Run the simulator for one profile, writing raw + ground-truth tables through the storage
# layer (SIM-01, D-07). `just simulate profile="tiny"` for the fast unit-test profile.
# `trim_start_match` accepts both `just simulate tiny` (plain positional) and the
# `just simulate profile="tiny"` form this phase's plans document throughout -- `just` has no
# built-in `name=value` CLI calling convention, so the latter arrives as the literal single
# positional string `profile=tiny` and is unwrapped here rather than left to fail on an
# unknown profile name.
simulate profile="default":
    uv run python -m nextmove.simulator --profile {{ trim_start_match(profile, "profile=") }}

# Run the ingest pipeline for one profile: contract validation with quarantine, the DATA-03
# semantic gates, the D-21 reject-rate threshold, and the D-22 one-line summary (DATA-02,
# DATA-03). Reads the `events_raw`/`catalog` tables plan 01-08's `just simulate` wrote, so
# run that first. `just ingest profile="tiny"` for the fast unit-test profile.
ingest profile="default":
    uv run python -m nextmove.ingest --profile {{ trim_start_match(profile, "profile=") }}

# Materialize the daily feature grid (D-19, FEAT-01, FEAT-02): DuckDB ASOF point-in-time
# computation over the canonical events table plan 01-09's `just ingest` wrote. Reads
# `data/canonical/events.parquet` and writes `data/features/feature_grid.parquet`.
# `just features profile="tiny"` for the fast unit-test profile.
features profile="default":
    uv run python -m nextmove.features --profile {{ trim_start_match(profile, "profile=") }}

# On-demand memory/wall-clock budget check (ENG-08) -- gated behind an env var so neither the
# default suite nor CI runs it. Widened by plan 01-11 to run all three stages' budget suites --
# simulator, ingest, features -- so one command covers the whole ENG-08 story rather than only
# the simulator's third of it. Plan 01-08 created this recipe and owns its name; 01-11 owns
# only the body.
budget profile="default":
    NEXTMOVE_RUN_DEFAULT_BUDGET=1 NEXTMOVE_BUDGET_PROFILE={{ trim_start_match(profile, "profile=") }} uv run pytest tests/integration/test_simulation_budget.py tests/integration/test_ingest_budget.py tests/integration/test_features_budget.py -m slow -q

# Full deterministic pipeline: simulate -> ingest -> features, via the declared DVC DAG
# (dvc.yaml). `just reproduce` for the `default` profile; `just reproduce profile="tiny"` (or
# "ci"/"demo") to run a smaller profile. This is the one command ENG-08/D-14 names: it runs
# entirely on a laptop with no cloud dependency, and `dvc repro` skips any stage whose deps and
# config hash are unchanged since the last run.
#
# `dvc repro` (this dvc version) has no CLI flag to override a `vars:` value at invocation
# time -- that override mechanism (`-S`/`--set-param`) exists only on `dvc exp run`, which
# creates a separate experiment ref rather than updating this repo's own `dvc.lock`. This
# recipe instead rewrites `dvc.yaml`'s `vars: - profile: <value>` line in place before calling
# `dvc repro`, which is the documented workaround for parameterizing a checked-in `dvc.yaml`
# pipeline without `dvc exp run`. `cmd` is part of what DVC hashes per stage, so switching
# profiles correctly invalidates the stage cache, and re-running with the same profile is a
# genuine no-op (dvc.yaml's only change is the resolved cmd text, which is identical run to
# run for a fixed profile).
reproduce profile="default":
    #!/usr/bin/env sh
    set -eu
    p="{{ trim_start_match(profile, "profile=") }}"
    sed -i "s/^  - profile: .*/  - profile: ${p}/" dvc.yaml
    uv run dvc repro simulate ingest features

# Inspect one table's full content-hash lineage chain (DATA-04): the config hash and content
# hash of the table itself, and of every input table it was derived from, walked transitively.
# `just lineage feature_grid` after a `just reproduce` run.
lineage table:
    uv run python -m nextmove.storage {{ table }}

# Remove all generated data tables (raw/canonical/features/ground_truth/lineage) without
# touching the DVC cache (`.dvc/cache`) -- a clean re-run of `just reproduce` starts from zero
# without losing DVC's content-addressable object store.
clean:
    rm -rf data
