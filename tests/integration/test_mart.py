"""E2: the DuckDB star-schema mart, its SQL tests and the data-quality report."""

import json
from pathlib import Path

import pandas as pd
import pytest

from nextmove.config.loader import load_config
from nextmove.mart.build import MART_TABLES, SQL_DIR, MartTestFailure, build_mart


def test_mart_built_tested_and_exported(tiny_pipeline: Path) -> None:
    mart = tiny_pipeline / "reports" / "mart"
    manifest = json.loads((mart / "manifest.json").read_text())
    assert set(manifest["row_counts"]) == set(MART_TABLES)
    assert all(v == 0 for v in manifest["sql_tests"].values())
    assert len(manifest["sql_tests"]) == len(list((SQL_DIR / "tests").glob("*.sql")))
    for table in MART_TABLES:
        assert (mart / f"{table}.parquet").is_file()
    decisions = pd.read_parquet(mart / "fct_decisions.parquet")
    replay = pd.read_parquet(tiny_pipeline / "evaluation" / "replay_decisions.parquet")
    assert len(decisions) == len(replay)
    assert (tiny_pipeline / "mart" / "nextmove.duckdb").is_file()
    assert "Ingest gates" in (mart / "data_quality.md").read_text()


def test_kpis_reconcile_with_python_evaluation(tiny_pipeline: Path) -> None:
    kpis = pd.read_csv(tiny_pipeline / "reports" / "mart" / "rpt_policy_kpis.csv")
    summary = pd.read_csv(tiny_pipeline / "reports" / "policy_comparison.csv")
    merged = kpis.merge(summary, on="policy", suffixes=("_sql", "_py"))
    assert len(merged) == len(summary)
    assert (merged["profit_eur_sql"] - merged["profit_eur_py"]).abs().max() < 0.05
    assert (merged["contact_rate_sql"] - merged["contact_rate_py"]).abs().max() < 1e-6


def test_sql_files_use_explicit_columns() -> None:
    for script in (SQL_DIR / "mart").glob("*.sql"):
        text = script.read_text()
        assert "SELECT *" not in text.upper(), script.name


def test_failing_sql_test_fails_the_build(tiny_pipeline: Path, tmp_path: Path, monkeypatch) -> None:
    import shutil

    import nextmove.mart.build as build

    sql = tmp_path / "sql"
    shutil.copytree(SQL_DIR, sql)
    (sql / "tests" / "test_always_fails.sql").write_text("SELECT 'boom' AS check_name;")
    monkeypatch.setattr(build, "SQL_DIR", sql)
    with pytest.raises(MartTestFailure, match="test_always_fails"):
        build_mart(load_config("tiny"), tiny_pipeline, tmp_path / "export")
