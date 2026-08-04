"""Content-hash lineage: every derived table records the content hashes of its inputs and
the hash of the config that generated it, and the chain is printable (DATA-04).

Builds on the private Parquet primitive (`_parquet.py`) and `paths.py` only. Must not import
`repository.py`: `repository.py` already imports this module, so an import in the return
direction would close a cycle and the package would fail to load before a single test runs
(HIGH-2).

**Anti-forgery contract (HIGH-4).** `LineageRecordDraft` carries only what a producer
legitimately knows and declares **no** `content_hash` field and **no** `input_hashes` field.
`record_lineage` computes both itself, from the bytes on disk, at call time -- a producer
that could state its own hash could state a false one, and DATA-04's whole value is that
lineage is checkable rather than claimed. `config_hash` is the deliberate exception: it
describes the configuration, not any file, so there is nothing on disk to derive it from.

**Non-re-entry (HIGH-1).** Lineage fragments are persisted through `write_parquet_atomic`,
never through `write_table` -- `write_table` refuses the lineage zone outright -- so
recording lineage cannot re-enter the table-writing path. A lineage fragment therefore has
no lineage row describing itself, and that is correct: the fragment is the record, not a
derived table.

**Fragment ownership (HIGH-3).** One fragment file per producing stage
(`data/lineage/{stage}.parquet`) keeps the DVC graph legal: each fragment is an `out` of
exactly one stage in plan 01-11's `dvc.yaml`, so no stage writes into another stage's
declared output directory.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa
from pydantic import BaseModel, ConfigDict

from nextmove.storage._parquet import CONTRACT_VERSION, read_parquet_file, write_parquet_atomic
from nextmove.storage.paths import Stage, Zone, resolve_table_path

_HASH_CHUNK_BYTES = 1 << 20  # 1 MiB


def content_hash(path: Path) -> str:
    """The single source of every content hash in the project: the sha256 hex digest of a
    file's exact bytes, read in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LineageRecordDraft(BaseModel):
    """What a producer legitimately knows about a table it just wrote. No `content_hash`
    field and no `input_hashes` field -- that absence is the anti-forgery mechanism."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    table_name: str
    zone: str
    input_tables: list[str]
    config_hash: str
    contract_version: str
    producer_stage: Stage
    row_count: int


class LineageRecord(BaseModel):
    """The stored shape: every `LineageRecordDraft` field plus `content_hash` and
    `input_hashes`, both computed inside this module. Deliberately no timestamp field of any
    kind -- a wall-clock column would make the fragment itself differ between two
    otherwise-identical runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    table_name: str
    zone: str
    input_tables: list[str]
    config_hash: str
    contract_version: str
    producer_stage: Stage
    row_count: int
    content_hash: str
    input_hashes: list[str]


# Explicit, hand-written schema -- LineageRecord's shape is fixed and known here, so it does
# not need the generic Pydantic-model-to-Arrow-schema reflection repository.py uses for
# arbitrary domain row types.
_LINEAGE_SCHEMA = pa.schema(
    [
        pa.field("table_name", pa.string(), nullable=False),
        pa.field("zone", pa.string(), nullable=False),
        pa.field("input_tables", pa.list_(pa.string()), nullable=False),
        pa.field("config_hash", pa.string(), nullable=False),
        pa.field("contract_version", pa.string(), nullable=False),
        pa.field("producer_stage", pa.string(), nullable=False),
        pa.field("row_count", pa.int64(), nullable=False),
        pa.field("content_hash", pa.string(), nullable=False),
        pa.field("input_hashes", pa.list_(pa.string()), nullable=False),
    ]
)


def _lineage_records_to_table(records: Sequence[LineageRecord]) -> pa.Table:
    columns: dict[str, list] = {name: [] for name in _LINEAGE_SCHEMA.names}
    for record in records:
        columns["table_name"].append(record.table_name)
        columns["zone"].append(record.zone)
        columns["input_tables"].append(list(record.input_tables))
        columns["config_hash"].append(record.config_hash)
        columns["contract_version"].append(record.contract_version)
        columns["producer_stage"].append(record.producer_stage.value)
        columns["row_count"].append(record.row_count)
        columns["content_hash"].append(record.content_hash)
        columns["input_hashes"].append(list(record.input_hashes))
    arrays = [
        pa.array(columns[name], type=field.type)
        for name, field in zip(_LINEAGE_SCHEMA.names, _LINEAGE_SCHEMA, strict=True)
    ]
    return pa.Table.from_arrays(arrays, schema=_LINEAGE_SCHEMA)


def _table_from_row(row: dict) -> LineageRecord:
    return LineageRecord.model_validate(row)


def record_lineage(
    path: Path,
    draft: LineageRecordDraft,
    input_paths: Sequence[Path] = (),
    root: Path | None = None,
) -> LineageRecord:
    """Compute the described table's `content_hash` and every input's hash from the bytes on
    disk, upsert the completed record into its stage's fragment, and return it.

    Accepts no hash from its caller for either the described table or its inputs -- both are
    computed here, from disk, at call time, which is what makes the recorded hash track the
    file rather than any claim the caller made about it.
    """
    table_hash = content_hash(Path(path))
    input_hashes = sorted(content_hash(Path(p)) for p in input_paths)
    record = LineageRecord(
        table_name=draft.table_name,
        zone=draft.zone,
        input_tables=sorted(draft.input_tables),
        config_hash=draft.config_hash,
        contract_version=draft.contract_version,
        producer_stage=draft.producer_stage,
        row_count=draft.row_count,
        content_hash=table_hash,
        input_hashes=input_hashes,
    )

    fragment_path = resolve_table_path(draft.producer_stage.value, Zone.LINEAGE, root)
    records: dict[str, LineageRecord] = {}
    if fragment_path.is_file():
        existing = read_parquet_file(fragment_path)
        for row in existing.to_pylist():
            existing_record = _table_from_row(row)
            records[existing_record.table_name] = existing_record
    records[record.table_name] = record

    ordered = [records[name] for name in sorted(records)]
    fragment_table = _lineage_records_to_table(ordered)
    write_parquet_atomic(
        fragment_table, fragment_path, ("table_name",), {"contract_version": CONTRACT_VERSION}
    )
    return record


def read_lineage(root: Path | None = None) -> list[LineageRecord]:
    """Read every fragment that exists, iterating `Stage` members in sorted order rather
    than listing the directory -- directory order is filesystem-dependent and would make
    output vary between machines -- and return the concatenation sorted by
    `(producer_stage, table_name)`."""
    records: list[LineageRecord] = []
    for stage in sorted(Stage, key=lambda s: s.value):
        fragment_path = resolve_table_path(stage.value, Zone.LINEAGE, root)
        if not fragment_path.is_file():
            continue
        table = read_parquet_file(fragment_path)
        for row in table.to_pylist():
            records.append(_table_from_row(row))
    return sorted(records, key=lambda r: (r.producer_stage.value, r.table_name))


def print_lineage_chain(table_name: str, root: Path | None = None) -> str:
    """Resolve `table_name`'s row from the union of all fragments, walk `input_tables`
    transitively depth-first with children visited in sorted order, and return (and print)
    an indented text rendering. A table with no inputs renders as a root node line; a cycle
    raises `ValueError` naming the cycle rather than recursing forever."""
    records = {record.table_name: record for record in read_lineage(root)}
    if table_name not in records:
        raise KeyError(f"No lineage record found for table {table_name!r}")

    lines: list[str] = []

    def _walk(name: str, depth: int, visiting: tuple[str, ...]) -> None:
        if name in visiting:
            raise ValueError(f"Lineage cycle detected: {' -> '.join((*visiting, name))}")
        indent = "  " * depth
        record = records.get(name)
        if record is None:
            lines.append(f"{indent}{name} (no lineage record)")
            return
        lines.append(
            f"{indent}{record.table_name} (content_hash={record.content_hash[:12]}, "
            f"config_hash={record.config_hash[:12]}, rows={record.row_count})"
        )
        for input_name in sorted(record.input_tables):
            _walk(input_name, depth + 1, (*visiting, name))

    _walk(table_name, 0, ())
    rendered = "\n".join(lines)
    print(rendered)
    return rendered
