"""The only module that opens a DuckDB connection (ENG-01).

Deterministic sorted atomic table write, staging part-file write, out-of-core part merge
with optional dedupe, streaming query-to-part write, read, and query -- every one of them
root-addressable (HIGH-6). Together with `_parquet.py` and `lineage.py` this package is the
only part of the project permitted to import `pyarrow` or `duckdb` -- `pyproject.toml`'s
second import-linter contract enforces that, and `nextmove.storage` is deliberately absent
from that contract's source list.

**Which write path to use** is the difference between a bounded producer and an unbounded
one: `write_table` materializes `rows` as one Arrow table, so it is correct only for tables
whose row count is bounded by a population, catalog or campaign count. Any table whose row
count scales with the horizon must be produced by flushing part files and merging them with
`write_table_from_parts`, or by streaming a query into parts with `write_query_to_part`.

**Row schema derivation (executor interpretation, no `schema` parameter in the plan's pinned
call surface).** `write_table` and `write_part_file` accept `rows` as an iterable of Pydantic
`BaseModel` instances (or, with an explicit `row_model`, plain mappings). The Arrow schema is
derived deterministically from the row *type* -- `type(rows[0])`'s field annotations -- never
from which values happen to be null, so an all-null column in a small run cannot infer a
different type than the same column in a large run. Because a zero-row call has no instance
to introspect, both functions accept an additional keyword-only `row_model: type[BaseModel]
| None = None`, required only when `rows` is empty; omitting it on an empty `rows` raises
`ValueError` telling the caller to supply it. This does not change the documented call shape
for the common (non-empty) case and is recorded in the plan's SUMMARY as an explicit
interpretation of an underspecified mechanism.
"""

import enum
import json
import shutil
import types
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Literal, Union, get_args, get_origin

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel

from nextmove.config.loader import ResolvedConfig
from nextmove.storage._parquet import (
    CONTRACT_VERSION,
    PARQUET_ROW_GROUP_SIZE,
    read_parquet_file,
    write_parquet_atomic,
    write_parquet_stream,
)
from nextmove.storage.lineage import LineageRecordDraft
from nextmove.storage.lineage import record_lineage as _record_lineage
from nextmove.storage.paths import (
    Stage,
    Zone,
    resolve_staging_path,
    resolve_table_path,
    staging_root,
)

# Public alias for the Arrow table type. Consumer packages forbidden from importing pyarrow
# directly (pyproject.toml's second import-linter contract) annotate against this instead:
# `from nextmove.storage import Table`. The contract is not relaxed and no linter carve-out
# is added (review MEDIUM-6).
Table = pa.Table

# The ceiling DuckDB is told to keep its own working set under; beyond it DuckDB spills its
# sort, join and window state to its configured temporary directory rather than growing
# without bound. Deliberately a module constant and not a config key: the spill threshold
# changes how much memory a merge uses, never which rows come out or in what order, so it
# must stay outside the hashed config surface or two byte-identical runs would carry
# different config hashes.
STORAGE_MEMORY_LIMIT_MB = 512

_CLOSED_METADATA_KEYS: frozenset[str] = frozenset(
    {"config_hash", "input_tables", "producer_stage", "contract_version"}
)

_UNION_ORIGINS = (Union, types.UnionType)


# ------------------------------------------------------------------------------------------
# Generic Pydantic-model -> Arrow schema derivation (private; used by write_table and
# write_part_file only). Deterministic from the model's *type*, never from the data.
# ------------------------------------------------------------------------------------------


def _arrow_type_for_annotation(annotation: object) -> tuple[pa.DataType, bool]:
    """Return `(arrow_type, nullable)` for a Pydantic field annotation."""
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        nullable = type(None) in args
        if len(non_none) != 1:
            raise TypeError(
                f"Unsupported union annotation for Arrow schema derivation: {annotation!r}"
            )
        inner_type, _ = _arrow_type_for_annotation(non_none[0])
        return inner_type, nullable
    if origin is Literal:
        (first, *_rest) = get_args(annotation)
        inner_type, _ = _arrow_type_for_annotation(type(first))
        return inner_type, False
    if origin in (list, tuple, Sequence):
        item_args = get_args(annotation)
        item_type = item_args[0] if item_args else str
        inner_type, _ = _arrow_type_for_annotation(item_type)
        return pa.list_(inner_type), False
    if origin in (dict, Mapping):
        key_type, value_type = get_args(annotation)
        key_arrow, _ = _arrow_type_for_annotation(key_type)
        value_arrow, _ = _arrow_type_for_annotation(value_type)
        return pa.map_(key_arrow, value_arrow), False
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return pa.string(), False
        if annotation is bool:
            return pa.bool_(), False
        if annotation is int:
            return pa.int64(), False
        if annotation is float:
            return pa.float64(), False
        if annotation is str:
            return pa.string(), False
        import datetime as _dt

        if annotation is _dt.datetime:
            return pa.timestamp("us", tz="UTC"), False
        if annotation is _dt.date:
            return pa.date32(), False
    raise TypeError(f"No Arrow type mapping for annotation {annotation!r}")


def _schema_from_model(model_cls: type[BaseModel]) -> pa.Schema:
    """Build a Pydantic model's Arrow schema explicitly from its field annotations --
    deterministic and independent of any actual row's values.

    Every field is declared nullable, regardless of the model's own optionality: DuckDB's
    `read_parquet` -> Arrow conversion always reports nullable=True on its output columns
    (an engine-level default, not a data-driven inference), and `write_table_from_parts`
    merges through that engine. A field declared non-nullable here would make an
    in-memory `write_table` and an out-of-core `write_table_from_parts` of the identical
    rows diverge in their Arrow schema -- and therefore in their Parquet bytes -- even
    though every value matches. Byte-equality between the two write paths is a pinned
    acceptance criterion, so nullability is never used as a data-integrity signal in this
    schema; `pydantic`'s own field validation is what actually enforces non-nullability
    before a row ever reaches this function.
    """
    fields = []
    for name, field_info in model_cls.model_fields.items():
        arrow_type, _nullable = _arrow_type_for_annotation(field_info.annotation)
        fields.append(pa.field(name, arrow_type, nullable=True))
    return pa.schema(fields)


def _extract_field_value(value: object) -> object:
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _rows_to_table(
    rows: Iterable[BaseModel | Mapping[str, object]],
    row_model: type[BaseModel] | None,
) -> pa.Table:
    """Convert `rows` to a `pyarrow.Table` with an explicitly constructed schema -- never
    inferred from the first record. Raises `ValueError` when `rows` is empty and no
    `row_model` was supplied, since there is then nothing to derive a schema from."""
    row_list = list(rows)
    model_cls = row_model
    if model_cls is None:
        if not row_list:
            raise ValueError(
                "Cannot derive an Arrow schema for zero rows without row_model; pass "
                "row_model= explicitly when writing an empty table"
            )
        first = row_list[0]
        if not isinstance(first, BaseModel):
            raise TypeError(
                f"Unsupported row type {type(first)!r}: rows must be Pydantic BaseModel "
                "instances, or row_model must be supplied explicitly, so the Arrow schema "
                "is derived deterministically from the model rather than inferred from data"
            )
        model_cls = type(first)

    schema = _schema_from_model(model_cls)
    columns: dict[str, list] = {name: [] for name in schema.names}
    for row in row_list:
        if isinstance(row, BaseModel):
            data = row.model_dump(mode="python")
        elif isinstance(row, Mapping):
            data = dict(row)
        else:
            raise TypeError(f"Unsupported row type {type(row)!r}; expected BaseModel or Mapping")
        for name in schema.names:
            columns[name].append(_extract_field_value(data.get(name)))
    arrays = [
        pa.array(columns[name], type=field.type)
        for name, field in zip(schema.names, schema, strict=True)
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


def _table_name_from_path(path: Path) -> str:
    return Path(path).stem


def _stamp_metadata(
    resolved_config: ResolvedConfig,
    producer_stage: Stage,
    input_paths: Sequence[Path],
    extra_metadata: Mapping[str, str] | None,
) -> tuple[dict[str, str], list[str]]:
    """Build the closed key-value metadata set plus the sorted, deduplicated input table
    names derived from `input_paths`' filename stems (LOW-6)."""
    input_tables = sorted({_table_name_from_path(p) for p in input_paths})
    metadata: dict[str, str] = {
        "config_hash": resolved_config.config_hash,
        "input_tables": json.dumps(input_tables),
        "producer_stage": producer_stage.value,
        "contract_version": CONTRACT_VERSION,
    }
    if extra_metadata:
        collision = set(extra_metadata) & _CLOSED_METADATA_KEYS
        if collision:
            raise ValueError(
                f"extra_metadata key(s) {sorted(collision)!r} collide with the closed "
                f"metadata set {sorted(_CLOSED_METADATA_KEYS)!r}; extra_metadata is merged "
                "into the closed set, never able to override a member of it"
            )
        metadata.update({k: str(v) for k, v in extra_metadata.items()})
    return metadata, input_tables


def _sql_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _order_by_clause(sort_key: tuple[str, ...]) -> str:
    return ", ".join(f'"{col}" NULLS LAST' for col in sort_key)


# ------------------------------------------------------------------------------------------
# DuckDB connection
# ------------------------------------------------------------------------------------------


def connect(read_only: bool = False, root: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Return a single-threaded, memory-limited DuckDB connection with its temp directory
    pointed inside the staging root.

    Single-threaded execution is not a performance choice: DuckDB documents that
    floating-point aggregates such as standard deviation and correlation can differ across
    runs under parallel execution, because the local-then-merge summation order is not
    guaranteed identical -- and any table whose bytes are compared in a golden test must not
    carry that variance. The memory limit converts an out-of-memory crash on a large merge
    into a spill, or -- when even the spill cannot satisfy a query -- into a diagnosable
    DuckDB error naming the limit. The temp directory is pointed inside the staging root so
    spill files are covered by the same `.dvcignore` entry and removed by the same
    `clear_staging` call as part files.
    """
    con = duckdb.connect(database=":memory:", read_only=read_only)
    con.execute("PRAGMA threads=1")
    con.execute(f"PRAGMA memory_limit='{STORAGE_MEMORY_LIMIT_MB}MB'")
    temp_dir = staging_root(root)
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory={_sql_quote(str(temp_dir))}")
    return con


# ------------------------------------------------------------------------------------------
# Table writes
# ------------------------------------------------------------------------------------------


def write_table(
    rows: Iterable[BaseModel | Mapping[str, object]],
    table_name: str,
    zone: Zone,
    sort_key: tuple[str, ...],
    resolved_config: ResolvedConfig,
    producer_stage: Stage,
    input_paths: Sequence[Path] = (),
    record_lineage: bool = True,
    extra_metadata: Mapping[str, str] | None = None,
    root: Path | None = None,
    row_model: type[BaseModel] | None = None,
) -> Path:
    """Convert `rows` to an Arrow table with an explicitly constructed schema, sort and
    write it atomically, and -- unless `record_lineage=False` -- record its lineage.

    Raises `ValueError` naming the zone when `zone` is `Zone.LINEAGE`: a lineage fragment is
    produced only by `record_lineage`, which writes through the private primitive directly.
    That refusal is the structural reason recording lineage cannot re-enter the write path
    (HIGH-1).
    """
    if zone is Zone.LINEAGE:
        raise ValueError(
            f"write_table refuses zone={zone.value!r}: a lineage fragment is produced only "
            "by record_lineage, never by write_table"
        )
    dest = resolve_table_path(table_name, zone, root)
    table = _rows_to_table(rows, row_model)
    metadata, input_tables = _stamp_metadata(
        resolved_config, producer_stage, input_paths, extra_metadata
    )
    write_parquet_atomic(table, dest, sort_key, metadata)

    if record_lineage:
        draft = LineageRecordDraft(
            table_name=table_name,
            zone=zone.value,
            input_tables=input_tables,
            config_hash=resolved_config.config_hash,
            contract_version=CONTRACT_VERSION,
            producer_stage=producer_stage,
            row_count=table.num_rows,
        )
        _record_lineage(dest, draft, input_paths, root)
    return dest


def write_table_from_parts(
    part_paths: Sequence[Path],
    table_name: str,
    zone: Zone,
    sort_key: tuple[str, ...],
    resolved_config: ResolvedConfig,
    producer_stage: Stage,
    input_paths: Sequence[Path] = (),
    record_lineage: bool = True,
    dedupe_on: str | tuple[str, ...] | None = None,
    extra_metadata: Mapping[str, str] | None = None,
    root: Path | None = None,
) -> Path:
    """Merge `part_paths` into one sorted table **out of core** through DuckDB and stream the
    result into `write_parquet_stream` -- never concatenating parts into one Arrow table.

    DuckDB's sort (and, when `dedupe_on` is given, its window operator) spills to the
    connection's configured temporary directory once it exceeds `STORAGE_MEMORY_LIMIT_MB`,
    so the merge's peak allocation is the memory limit plus one row group **at any table
    size** (HIGH-10). This replaces a design that read every part through
    `read_parquet_file` and concatenated them into one Arrow table before sorting -- that
    design bounded the producer's *Python* heap while leaving the merge's Arrow footprint
    equal to the whole table, which is the entire hazard ENG-08 names and which no
    `tracemalloc`-based test can observe. Do not reach for a whole-table Arrow
    concatenation helper here -- that is the exact regression this module's tests guard
    against.

    Raises `ValueError` naming the table when `part_paths` is empty: a zero-part merge has
    no schema source to write from. A producer that must write its table even when no rows
    were produced calls `write_table` with an empty row set instead.
    """
    if zone is Zone.LINEAGE:
        raise ValueError(
            f"write_table_from_parts refuses zone={zone.value!r}: a lineage fragment is "
            "produced only by record_lineage, never by write_table_from_parts"
        )
    if not part_paths:
        raise ValueError(
            f"write_table_from_parts({table_name!r}): a zero-part merge has no schema "
            "source to write from; call write_table with an empty row set instead"
        )
    dest = resolve_table_path(table_name, zone, root)
    metadata, input_tables = _stamp_metadata(
        resolved_config, producer_stage, input_paths, extra_metadata
    )

    dedupe_cols: tuple[str, ...] | None
    if dedupe_on is None:
        dedupe_cols = None
    elif isinstance(dedupe_on, str):
        dedupe_cols = (dedupe_on,)
    else:
        dedupe_cols = tuple(dedupe_on)

    part_list_sql = "[" + ", ".join(_sql_quote(str(Path(p))) for p in part_paths) + "]"
    order_by = _order_by_clause(sort_key)
    qualify_clause = ""
    if dedupe_cols:
        partition_by = ", ".join(f'"{col}"' for col in dedupe_cols)
        qualify_clause = (
            f"QUALIFY row_number() OVER (PARTITION BY {partition_by} ORDER BY {order_by}) = 1"
        )
    sql = f"SELECT * FROM read_parquet({part_list_sql}) {qualify_clause} ORDER BY {order_by}"

    con = connect(root=root)
    try:
        result = con.execute(sql)
        reader = result.to_arrow_reader(PARQUET_ROW_GROUP_SIZE)
        write_parquet_stream(reader, dest, sort_key, metadata)
    finally:
        con.close()

    if record_lineage:
        # Row count is read from the Parquet footer metadata, not the data itself, so
        # recording lineage for a horizon-scale merged table never re-materializes it.
        row_count = pq.ParquetFile(dest).metadata.num_rows
        draft = LineageRecordDraft(
            table_name=table_name,
            zone=zone.value,
            input_tables=input_tables,
            config_hash=resolved_config.config_hash,
            contract_version=CONTRACT_VERSION,
            producer_stage=producer_stage,
            row_count=row_count,
        )
        _record_lineage(dest, draft, input_paths, root)
    return dest


def write_part_file(
    rows: Iterable[BaseModel | Mapping[str, object]],
    part_dir: str,
    part_index: int,
    sort_key: tuple[str, ...],
    root: Path | None = None,
    row_model: type[BaseModel] | None = None,
) -> Path:
    """The staging counterpart of `write_table`, and the only sanctioned way to persist a
    transient part file.

    Takes no `zone`, so it cannot be pointed at a data zone, and no `record_lineage`
    parameter, so a part file cannot acquire a lineage row by accident -- it never calls the
    lineage module at all.
    """
    dest = resolve_staging_path(part_dir, part_index, root)
    table = _rows_to_table(rows, row_model)
    write_parquet_atomic(table, dest, sort_key, {"contract_version": CONTRACT_VERSION})
    return dest


def write_query_to_part(
    sql: str,
    part_dir: str,
    part_index: int,
    sort_key: tuple[str, ...],
    root: Path | None = None,
    **table_bindings: Path,
) -> Path:
    """Stream a query result to a staging part file without ever materializing it as one
    Arrow table (HIGH-13).

    `root` and every element of `sort_key` are reserved names and cannot double as bound
    table names.
    """
    reserved = {"root", *sort_key}
    collision = reserved & set(table_bindings)
    if collision:
        raise ValueError(
            f"table binding name(s) {sorted(collision)!r} collide with reserved names "
            f"{sorted(reserved)!r}"
        )
    dest = resolve_staging_path(part_dir, part_index, root)
    order_by = _order_by_clause(sort_key)
    con = connect(root=root)
    try:
        for name, path in table_bindings.items():
            con.execute(
                f'CREATE VIEW "{name}" AS SELECT * FROM read_parquet({_sql_quote(str(Path(path)))})'
            )
        full_sql = f"SELECT * FROM ({sql}) AS _write_query_to_part_result ORDER BY {order_by}"
        result = con.execute(full_sql)
        reader = result.to_arrow_reader(PARQUET_ROW_GROUP_SIZE)
        write_parquet_stream(reader, dest, sort_key, {"contract_version": CONTRACT_VERSION})
    finally:
        con.close()
    return dest


# ------------------------------------------------------------------------------------------
# Staging management
# ------------------------------------------------------------------------------------------


def list_part_files(part_dir: str, root: Path | None = None) -> list[Path]:
    """Every part file under `part_dir`'s staging directory, sorted by filename -- which the
    zero-padded index makes equal to numeric order. Directory listing order is
    filesystem-dependent and is never trusted directly."""
    base = staging_root(root) / part_dir
    if not base.is_dir():
        return []
    return sorted(base.glob("part-*.parquet"))


def clear_staging(part_dir: str | None = None, root: Path | None = None) -> None:
    """Remove one staging subdirectory, or the whole staging root when `part_dir` is `None`.
    A no-op when the target does not exist. Refuses to remove anything that is not a
    descendant of `staging_root(root)`, so a producer cleaning up after itself can never
    delete a data zone."""
    base = staging_root(root)
    target = base if part_dir is None else (base / part_dir).resolve()
    if target != base and not target.is_relative_to(base):
        raise ValueError(f"Refusing to clear {target}: not a descendant of the staging root {base}")
    if target.exists():
        shutil.rmtree(target)


# ------------------------------------------------------------------------------------------
# Reads and queries
# ------------------------------------------------------------------------------------------


def read_table(table_name: str, zone: Zone, root: Path | None = None) -> Table:
    """Return a **fully materialized** Arrow table. Memory cost is the result size; a caller
    whose result scales with the horizon must use `write_query_to_part` instead of `query`
    followed by a write."""
    return read_parquet_file(resolve_table_path(table_name, zone, root))


def table_exists(table_name: str, zone: Zone, root: Path | None = None) -> bool:
    return resolve_table_path(table_name, zone, root).is_file()


def query(sql: str, root: Path | None = None, **table_bindings: Path) -> Table:
    """Execute `sql` against `table_bindings` (name -> Parquet path) on a single-threaded
    connection and return a **fully materialized** Arrow table.

    `root` is a reserved parameter name and therefore cannot also be used as a bound table
    name; no table in this project is called `root`.
    """
    if "root" in table_bindings:
        raise ValueError(
            "'root' is a reserved parameter name and cannot be used as a bound table name"
        )
    con = connect(root=root)
    try:
        for name, path in table_bindings.items():
            con.execute(
                f'CREATE VIEW "{name}" AS SELECT * FROM read_parquet({_sql_quote(str(Path(path)))})'
            )
        return con.execute(sql).to_arrow_table()
    finally:
        con.close()
