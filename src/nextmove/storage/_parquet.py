"""The private deterministic Parquet primitive both `repository.py` and `lineage.py` build
on (ENG-01, ENG-04, HIGH-2, HIGH-10).

Owns the single streaming writer and the pinned row-group size. Imports only `pyarrow`, the
standard library, and nothing else in this package -- not `repository.py`, not `lineage.py`,
not the package root. That restriction is what keeps the storage package's own import graph
a DAG: `lineage.py` and `repository.py` both build on this module, and this module imports
neither of them, so no lazy-import workaround is ever needed (HIGH-2).

`write_parquet_stream` is the single site in this project where Parquet bytes are produced.
It consumes a `pyarrow.RecordBatchReader` and emits fixed-size row groups through a
`pyarrow.parquet.ParquetWriter`, holding at most one row group plus one incoming batch at
any point -- never the whole table. `write_parquet_atomic` is a thin in-memory convenience
that sorts a table and hands the sorted table's reader to the stream writer; it performs no
write of its own, which is what keeps a merged table and a single in-memory write of the
same rows byte-identical (HIGH-10).

Attach only caller-supplied key-value metadata. Never attach a wall-clock value, a generation
stamp, a hostname, or a user name: those differ between two runs and would break
byte-identical comparison at the footer even when every data byte matched.
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

# Storage's own write-contract version, stamped into every table's key-value metadata.
# Independent of any domain schema's own contract version (e.g. the canonical Event
# contract in nextmove.ingest.contracts) -- this one describes the storage layer's own
# write contract.
CONTRACT_VERSION = "1.0.0"

# A writer option in the same sense as `compression` and `version`: it materially
# determines the bytes on disk, so it is pinned here as a literal rather than exposed as a
# parameter or a config key. Every Parquet file in the project is written in row groups of
# exactly this size, with only the final group short. That single pinned value is what lets
# a streamed write and an in-memory write of the same rows produce identical bytes.
PARQUET_ROW_GROUP_SIZE = 65536

# Pinned writer options (RESEARCH: PyArrow's writer version string and library defaults are
# both documented determinism hazards if left unpinned).
_WRITER_OPTIONS: dict[str, object] = {
    "compression": "zstd",
    "version": "2.6",
    "write_statistics": True,
}


def _check_batch_keys(
    batch: pa.RecordBatch,
    sort_key: tuple[str, ...],
    previous_key: tuple | None,
) -> tuple | None:
    """Compare each row's `sort_key` tuple against the previous row's, carrying state across
    batch boundaries, and raise on the first duplicate found.

    Because the stream is presumed already sorted by `sort_key`, duplicate tuples are
    necessarily adjacent, so comparing each row's key to only the immediately preceding
    row's key -- never holding more than one key tuple -- detects exactly the violations a
    whole-table scan would, in constant memory.
    """
    if batch.num_rows == 0:
        return previous_key
    key_columns = [batch.column(name).to_pylist() for name in sort_key]
    previous = previous_key
    for row_key in zip(*key_columns, strict=True):
        if previous is not None and row_key == previous:
            raise ValueError(
                f"Duplicate value for sort key {sort_key!r}: {row_key!r} is not unique "
                "across the supplied rows"
            )
        previous = row_key
    return previous


def _rechunked_tables(
    batches: pa.RecordBatchReader, schema: pa.Schema, sort_key: tuple[str, ...]
) -> Iterator[pa.Table]:
    """Consume `batches`, checking sort-key uniqueness on adjacent rows, and yield
    fixed-size (`PARQUET_ROW_GROUP_SIZE`-row) tables carrying `schema`'s metadata -- with
    only the final yielded table short. Peak allocation at any point is one row group plus
    one incoming batch, never the whole stream.
    """
    pending: pa.Table | None = None
    previous_key: tuple | None = None
    saw_any = False
    for batch in batches:
        saw_any = True
        previous_key = _check_batch_keys(batch, sort_key, previous_key)
        batch_table = pa.Table.from_batches([batch]).replace_schema_metadata(schema.metadata)
        pending = batch_table if pending is None else pa.concat_tables([pending, batch_table])
        while pending.num_rows >= PARQUET_ROW_GROUP_SIZE:
            yield pending.slice(0, PARQUET_ROW_GROUP_SIZE)
            pending = pending.slice(PARQUET_ROW_GROUP_SIZE)
    if not saw_any:
        yield pa.Table.from_batches([], schema=schema)
    elif pending is not None and pending.num_rows > 0:
        yield pending


def write_parquet_stream(
    batches: pa.RecordBatchReader,
    dest: Path,
    sort_key: tuple[str, ...],
    kv_metadata: dict[str, str],
) -> Path:
    """The single site in this project where Parquet bytes are produced.

    Precondition: `batches` must already be sorted ascending by `sort_key` with nulls last.
    The sort-key **tuple** uniqueness precondition is enforced on the stream itself -- one
    key tuple of state carried across batch boundaries -- and raises `ValueError` naming
    `sort_key` and the first duplicate tuple on a violation. Feeding an unsorted stream
    produces a silent false pass rather than a loud error; the docstring states this because
    it is the reason the check is sound.

    Writes to a sibling temporary path in `dest`'s directory and `os.replace`s onto `dest`
    only after every row group is written, so an interrupted run leaves no partial table at
    `dest` and no stray temporary file behind (deleted on any exception).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    schema = batches.schema
    if kv_metadata:
        schema = schema.with_metadata({k: str(v).encode("utf-8") for k, v in kv_metadata.items()})
    else:
        schema = schema.with_metadata({})

    fd, tmp_name = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=dest.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with pq.ParquetWriter(tmp_path, schema, **_WRITER_OPTIONS) as writer:
            for chunk in _rechunked_tables(batches, schema, sort_key):
                writer.write_table(chunk, row_group_size=PARQUET_ROW_GROUP_SIZE)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    os.replace(tmp_path, dest)
    return dest


def write_parquet_atomic(
    table: pa.Table,
    dest: Path,
    sort_key: tuple[str, ...],
    kv_metadata: dict[str, str],
) -> Path:
    """The in-memory convenience over the stream writer, for callers that already hold a
    whole table and whose row count is bounded by a population or catalog count rather than
    by the horizon.

    Sorts with `Table.sort_by` on `sort_key` with nulls-last placement pinned per key, then
    hands the sorted table's reader -- chunked at `PARQUET_ROW_GROUP_SIZE` -- to
    `write_parquet_stream`. Performs no write of its own: a second writer would be a second
    set of row-group boundaries and writer options to keep in agreement with the stream
    writer, and the byte-equality between a merged table and a single-call write depends on
    there being exactly one.
    """
    sorting = [(col, "ascending", "at_end") for col in sort_key]
    sorted_table = table.sort_by(sorting) if sort_key else table
    reader = pa.RecordBatchReader.from_batches(
        sorted_table.schema, sorted_table.to_batches(max_chunksize=PARQUET_ROW_GROUP_SIZE)
    )
    return write_parquet_stream(reader, dest, sort_key, kv_metadata)


def read_parquet_file(path: Path) -> pa.Table:
    """Plain whole-file read with no zone logic. Used for small whole-file reads only: the
    lineage fragment upsert and test fixtures. Deliberately **not** how the part merge reads
    its inputs -- the merge reads through DuckDB so it never holds a part, let alone all of
    them, in memory at once.
    """
    return pq.read_table(Path(path))
