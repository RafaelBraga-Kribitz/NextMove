# Runbook

How to run, check and troubleshoot the NextMove pipeline on a laptop. Everything is local:
no cloud services, no credentials.

## Setup

```bash
uv sync                  # Python 3.12 environment from uv.lock
just --list              # every recipe with a one-line description
```

Windows note: if `pyarrow`/`pandas` fail to load with "Application Control policy has blocked
this file", pin `pyarrow` 24.0.0 locally; do not change security settings.

## The pipeline (DVC DAG)

```text
simulate -> ingest -> features -> experiment -> train -> evaluate -> mart
```

| Stage | Command | Writes | Typical time (`demo`) |
|---|---|---|---|
| simulate | `python -m nextmove.simulator` | `data/raw`, `data/ground_truth` | ~2 min |
| ingest | `python -m nextmove.ingest` | `data/canonical` (+ quarantine) | ~1 min |
| features | `python -m nextmove.features` | `data/features` | ~4 min |
| experiment | `python -m nextmove.evaluate experiment` | `data/experiment` | ~2 min |
| train | `python -m nextmove.models` | `data/models` (models, metrics, segments) | ~2.5 min |
| evaluate | `python -m nextmove.evaluate evaluate` | `data/evaluation`, `reports/<profile>/evaluation` | ~8 min |
| mart | `python -m nextmove.mart` | `data/mart`, `reports/<profile>/mart` | < 1 min |

`just reproduce` runs the whole DAG for the `demo` profile (published results);
`just reproduce profile="ci"` runs the miniature profile CI uses (about a minute). DVC skips
stages whose inputs did not change.

## Checks

| Command | What it proves |
|---|---|
| `just ci` | lint, format, import contracts, full test suite (same as CI) |
| `just coverage` | AC-12 coverage gates |
| `just verify-published` | after `just reproduce`: published tables equal the committed ones (AC-11) |
| `just lineage <table>` | content-hash lineage chain of any table |

## Serving

`just serve` starts the API and the demo on `http://127.0.0.1:8000` (`/demo`, `/docs`).
It reads `data/` from the last `just reproduce`. Overrides entered in the demo are appended to
`data/overrides/overrides.jsonl` (never touched by DVC) and priced live on `/demo/evaluation`.

## Gates that stop the pipeline

| Gate | Where | Fix |
|---|---|---|
| Reject rate above `data_quality.max_reject_rate` | ingest | inspect `data/canonical/rejects.parquet` (reason per row) |
| Calibration (ECE) above `models.calibration.max_ece` (AC-5) | train | inspect `reports/<profile>/evaluation/reliability.csv`; do not loosen the bound to pass |
| A SQL test returns rows | mart | the failing test and sample rows are printed; see `sql/tests/` |
| Contract validation error | anywhere a `Decision` is built | a code change broke the contract: fix the code or bump `CONTRACT_VERSION` with a migration note |

## Common problems

- **`no feature row for customer`** — the customer had no activity before the requested
  `as_of`; pick a later date or another customer.
- **Out of disk** — `just clean` removes `data/` (DVC cache stays); rerun `just reproduce`.
- **MLflow** — runs are logged to `mlruns.db` (SQLite) next to `data/`; browse with
  `uv run mlflow ui --backend-store-uri sqlite:///mlruns.db`.
