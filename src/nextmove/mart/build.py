"""Build, test and export the DuckDB mart (E2).

Order: bind sources (`src_*` / `raw_*` views over pipeline Parquet tables, plus two small
frames from config), run `sql/mart/*.sql` in file order, run every `sql/tests/*.sql` (a test
passes when it returns zero rows), then export each mart table to
`reports/<profile>/mart/` (Parquet for all tables, CSV for dimensions and report tables) and
persist `data/mart/nextmove.duckdb` for ad-hoc SQL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from nextmove.config.loader import ResolvedConfig
from nextmove.decisions.actions import CatalogActionProvider
from nextmove.storage import Zone, connect, resolve_artifact_path, resolve_table_path

__all__ = ["MART_TABLES", "SQL_DIR", "MartTestFailure", "build_mart"]

REPO_ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = REPO_ROOT / "sql"

MART_TABLES = (
    "dim_date",
    "dim_action",
    "dim_policy",
    "dim_customer",
    "fct_decisions",
    "fct_outcomes",
    "rpt_policy_kpis",
    "rpt_retention_cohorts",
    "rpt_data_quality",
)
_CSV_TABLES = tuple(t for t in MART_TABLES if not t.startswith("fct_"))


class MartTestFailure(AssertionError):
    pass


def _q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _params(resolved: ResolvedConfig) -> pd.DataFrame:
    config = resolved.config
    train_end, validation_end, horizon = config.evaluation.windows(config.simulator.horizon_days)
    ceiling = next(
        (
            r.params.get("max_discount_bps")
            for r in config.constraints.rules
            if r.kind == "discount_ceiling" and r.mode == "hard"
        ),
        10_000,
    )
    return pd.DataFrame(
        {
            "start_date": [pd.Timestamp(config.simulator.start_date)],
            "horizon_days": [horizon],
            "train_end_day": [train_end],
            "validation_end_day": [validation_end],
            "test_start_day": [validation_end],
            "max_reject_rate": [config.data_quality.max_reject_rate],
            "max_discount_bps": [int(ceiling)],
        }
    )


def _actions(resolved: ResolvedConfig) -> pd.DataFrame:
    actions = resolved.config.actions
    descriptions = {a.name: a.description for a in actions.catalog}
    rows = [
        {
            "catalog_order": index,
            "candidate_id": c.id,
            "archetype": c.archetype,
            "description": descriptions[c.archetype],
            "is_contact": c.contact,
            "cost_cents": c.cost_cents,
            "discount_bps": c.discount_bps,
        }
        for index, c in enumerate(CatalogActionProvider(actions)._candidates)
    ]
    return pd.DataFrame(rows)


def build_mart(
    resolved: ResolvedConfig, root: Path | None = None, out_dir: Path | None = None
) -> dict:
    out_dir = out_dir or (REPO_ROOT / "reports" / resolved.profile / "mart")
    out_dir.mkdir(parents=True, exist_ok=True)
    con = connect(root=root)
    try:
        params = _params(resolved)
        params["start_date"] = params["start_date"].dt.date
        con.register("params_frame", params)
        con.execute("CREATE TABLE src_params AS SELECT * FROM params_frame")
        con.register("actions_frame", _actions(resolved))
        con.execute("CREATE TABLE src_actions AS SELECT * FROM actions_frame")
        sources = {
            "raw_events": resolve_table_path("events", Zone.CANONICAL, root),
            "raw_catalog": resolve_table_path("catalog", Zone.RAW, root),
            "src_rejects": resolve_table_path("rejects", Zone.CANONICAL, root),
            "src_replay_decisions": resolve_table_path("replay_decisions", Zone.EVALUATION, root),
            "src_policy_summary": resolve_table_path("policy_summary", Zone.EVALUATION, root),
            "src_overrides": resolve_table_path("override_outcomes", Zone.EVALUATION, root),
            "src_segments": resolve_table_path("segments", Zone.MODELS, root),
        }
        for name, path in sources.items():
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet({_q(str(path))})")
        for script in sorted((SQL_DIR / "mart").glob("*.sql")):
            con.execute(script.read_text(encoding="utf-8"))

        results = {}
        failures = []
        for test in sorted((SQL_DIR / "tests").glob("*.sql")):
            rows = con.execute(test.read_text(encoding="utf-8")).fetchall()
            results[test.stem] = len(rows)
            if rows:
                failures.append(f"{test.stem}: {len(rows)} violating row(s), e.g. {rows[:3]}")
        if failures:
            raise MartTestFailure("SQL tests failed: " + "; ".join(failures))

        counts = {}
        for table in MART_TABLES:
            counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            con.execute(
                f"COPY (SELECT * FROM {table}) TO {_q(str(out_dir / (table + '.parquet')))} "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            if table in _CSV_TABLES:
                con.execute(
                    f"COPY (SELECT * FROM {table}) TO {_q(str(out_dir / (table + '.csv')))} "
                    "(HEADER, DELIMITER ',')"
                )
        quality = con.execute("SELECT * FROM rpt_data_quality ORDER BY check_name").fetchdf()

        db_path = resolve_artifact_path("nextmove.duckdb", Zone.MART, root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        con.execute(f"ATTACH {_q(str(db_path))} AS mart_file")
        for table in MART_TABLES:
            con.execute(f"CREATE TABLE mart_file.{table} AS SELECT * FROM {table}")
        con.execute("DETACH mart_file")
    finally:
        con.close()

    manifest = {"profile": resolved.profile, "row_counts": counts, "sql_tests": results}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _quality_report(out_dir / "data_quality.md", quality, results, counts)
    return manifest


def _quality_report(path: Path, quality: pd.DataFrame, tests: dict, counts: dict) -> None:
    lines = [
        "# Data-quality report",
        "",
        "> **Simulated data only.** Built from the ingest gates and the mart's SQL tests "
        "(ADR-004).",
        "",
        "## Ingest gates (contract validation, semantic gates, reject-rate threshold)",
        "",
        "| Check | Stage | Failing rows | Checked rows | Failing share | Threshold | Passed |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for _, r in quality.iterrows():
        threshold = "" if pd.isna(r["threshold"]) else f"{r['threshold']:.4%}"
        passed = "" if pd.isna(r["passed"]) else ("yes" if r["passed"] else "**no**")
        lines.append(
            f"| {r['check_name']} | {r['stage']} | {int(r['failing_rows']):,} | "
            f"{int(r['checked_rows']):,} | {r['failing_share']:.4%} | {threshold} | {passed} |"
        )
    lines += [
        "",
        "Rejected rows are quarantined with their reason (`data/canonical/rejects.parquet`), "
        "never silently dropped.",
        "",
        "## Mart SQL tests (`sql/tests/`)",
        "",
        "| Test | Violating rows |",
        "|---|---:|",
        *[f"| {name} | {n} |" for name, n in sorted(tests.items())],
        "",
        "## Mart row counts",
        "",
        "| Table | Rows |",
        "|---|---:|",
        *[f"| {name} | {n:,} |" for name, n in counts.items()],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
