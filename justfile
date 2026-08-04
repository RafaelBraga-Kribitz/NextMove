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

# Full deterministic pipeline: simulate -> ingest -> features -> ... -> report
# NOT YET WIRED — plan 01-11 replaces this body with the real DVC pipeline invocation.
reproduce:
    @echo "reproduce: not yet wired (plan 01-11 replaces this body with the DVC pipeline)"
    @exit 1
