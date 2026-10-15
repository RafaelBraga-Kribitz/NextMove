"""SQL-first analytics layer (ADR-011): a documented DuckDB star schema built from pipeline
outputs by the checked-in SQL under `sql/mart/`, tested by the SQL under `sql/tests/`, and
exported for Power BI. This package only orchestrates; every transformation is SQL.

Must never import nextmove.simulator; reaches DuckDB only through nextmove.storage.
"""

__all__: list[str] = []
