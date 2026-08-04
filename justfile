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

# On-demand memory/wall-clock budget check (ENG-08) -- gated behind an env var so neither the
# default suite nor CI runs it. Currently runs only the simulator's budget suite; plan 01-11
# widens this recipe's *body* once the ingest and features budget suites exist in later waves,
# so one command covers the whole ENG-08 story rather than only the simulator's third of it.
# This plan creates the recipe and owns its name; 01-11 extends the body and nothing else.
budget profile="default":
    NEXTMOVE_RUN_DEFAULT_BUDGET=1 NEXTMOVE_BUDGET_PROFILE={{ trim_start_match(profile, "profile=") }} uv run pytest tests/integration/test_simulation_budget.py -m slow -q

# Full deterministic pipeline: simulate -> ingest -> features -> ... -> report
# NOT YET WIRED — plan 01-11 replaces this body with the real DVC pipeline invocation.
reproduce:
    @echo "reproduce: not yet wired (plan 01-11 replaces this body with the DVC pipeline)"
    @exit 1
