"""E3: the Power BI kit only references tables and columns the mart actually exports."""

import json
import re
from pathlib import Path

import pandas as pd

KIT = Path(__file__).resolve().parents[2] / "reporting" / "powerbi"
REFERENCE = re.compile(r"\b([a-z_]+)\[([a-z_0-9]+)\]")


def _columns(tiny_pipeline: Path) -> dict[str, set[str]]:
    mart = tiny_pipeline / "reports" / "mart"
    tables = {p.stem: set(pd.read_parquet(p).columns) for p in mart.glob("*.parquet")}
    tables["model_metrics"] = set(
        pd.read_csv(tiny_pipeline / "reports" / "model_metrics.csv").columns
    )
    return tables


def test_every_dax_and_layout_reference_exists(tiny_pipeline: Path) -> None:
    tables = _columns(tiny_pipeline)
    text = (KIT / "measures.dax").read_text() + (KIT / "layout.md").read_text()
    references = set(REFERENCE.findall(text))
    assert references, "expected table[column] references"
    missing = sorted(f"{t}[{c}]" for t, c in references if c not in tables.get(t, set()))
    assert missing == [], missing


def test_kit_files_present_and_theme_valid() -> None:
    for name in ("README.md", "model.md", "measures.dax", "theme.json", "layout.md"):
        assert (KIT / name).is_file()
    theme = json.loads((KIT / "theme.json").read_text())
    assert len(theme["dataColors"]) == 8
    assert "built by hand" in (KIT / "README.md").read_text()
