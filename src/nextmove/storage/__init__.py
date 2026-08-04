"""Cross-cutting storage infrastructure: the thin repository layer over DuckDB/Parquet
that every package reads and writes canonical or feature tables through.

Infrastructure, not one of the eleven ENG-01 packages — sits below all of them in the
import graph so nothing creates a cycle. Populated by plan 01-06.
"""

__all__: list[str] = []
