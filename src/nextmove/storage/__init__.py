"""Cross-cutting storage infrastructure: the thin repository layer over DuckDB/Parquet
that every package reads and writes canonical or feature tables through.

Infrastructure, not one of the eleven ENG-01 packages -- sits below all of them in the
import graph so nothing creates a cycle. Together with `_parquet.py` and `lineage.py`, this
is the only package permitted to import `pyarrow` or `duckdb`
(`pyproject.toml`'s second import-linter contract).

Re-exports only the public repository, lineage, and path-resolution surface. Nothing from
the private `_parquet` module is re-exported: `PARQUET_ROW_GROUP_SIZE` and
`write_parquet_stream` stay private to `_parquet.py`, because a consumer able to reach the
writer directly could bypass the sort, the containment check and the lineage stamp in one
call.
"""

from nextmove.storage.lineage import (
    LineageRecord,
    LineageRecordDraft,
    content_hash,
    print_lineage_chain,
    read_lineage,
    record_lineage,
)
from nextmove.storage.paths import (
    DATA_ROOT,
    STAGING_DIRNAME,
    Stage,
    Zone,
    resolve_staging_path,
    resolve_table_path,
    staging_root,
)
from nextmove.storage.repository import (
    STORAGE_MEMORY_LIMIT_MB,
    Table,
    clear_staging,
    connect,
    list_part_files,
    query,
    read_table,
    table_exists,
    write_part_file,
    write_query_to_part,
    write_table,
    write_table_from_parts,
)

__all__ = [
    "DATA_ROOT",
    "STAGING_DIRNAME",
    "STORAGE_MEMORY_LIMIT_MB",
    "LineageRecord",
    "LineageRecordDraft",
    "Stage",
    "Table",
    "Zone",
    "clear_staging",
    "connect",
    "content_hash",
    "list_part_files",
    "print_lineage_chain",
    "query",
    "read_lineage",
    "read_table",
    "record_lineage",
    "resolve_staging_path",
    "resolve_table_path",
    "staging_root",
    "table_exists",
    "write_part_file",
    "write_query_to_part",
    "write_table",
    "write_table_from_parts",
]
