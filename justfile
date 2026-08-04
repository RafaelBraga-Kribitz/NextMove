default:
    just --list

# Create/sync the uv-managed virtual environment from uv.lock
setup:
    uv sync

# Auto-format the codebase
fmt:
    uv run ruff format .

# Lint + format-check (CI-equivalent gate)
lint:
    uv run ruff check .
    uv run ruff format --check .

# Run the test suite
test:
    uv run pytest -x -q

# Full deterministic pipeline: simulate -> ingest -> features -> ... -> report
# NOT YET WIRED — plan 01-11 replaces this body with the real DVC pipeline invocation.
reproduce:
    @echo "reproduce: not yet wired (plan 01-11 replaces this body with the DVC pipeline)"
    @exit 1
