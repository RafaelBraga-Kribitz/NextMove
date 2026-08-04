"""CLI entry point: `python -m nextmove.ingest --profile <name> [--out <dir>]`.

Loads config, streams `events_raw` (written by `nextmove.simulator`, plan 01-08) through
`ingest_events`, evaluates the reject-rate threshold, prints D-22's one-line summary, and
exits non-zero when the threshold was exceeded. That is the whole sequence: this module runs
no gate, writes no table and quarantines nothing itself -- every one of those happens inside
`ingest_events`, before the flush (see `pipeline.py`'s module docstring).

**Streaming the raw source, not `read_table`.** `nextmove.storage.read_table` returns a
**fully materialized** Arrow table by its own documented contract, and `events_raw` is a
horizon-scaled table -- exactly the case that module's docstring says must not go through
`read_table`. This CLI instead opens its own DuckDB connection through the storage layer's
public `connect()` and reads `events_raw` via `to_arrow_reader`, yielding one Python dict per
row only as `ingest_events`'s batch loop actually consumes it, so the CLI's own memory
footprint tracks the reader's chunk size rather than the whole raw table. `payload` is
decoded from its flattened JSON string (plan 01-08's `EventRow` shape) back into a nested
dict here, because `Event.payload` validates against a nested discriminated union, not a JSON
string.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from nextmove.config.loader import load_config
from nextmove.ingest.pipeline import VALIDATION_BATCH_SIZE, ingest_events
from nextmove.ingest.quality import RejectRateExceeded, evaluate_reject_rate, format_dq_summary
from nextmove.storage import Zone, connect, resolve_table_path


def _sql_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _raw_record_stream(out_root: Path | None, batch_size: int) -> Iterator[Mapping[str, Any]]:
    """Stream `events_raw` rows through DuckDB's Arrow reader, decoding each row's
    JSON-flattened `payload` column back into a nested dict."""
    events_path = resolve_table_path("events_raw", Zone.RAW, root=out_root)
    con = connect(root=out_root)
    try:
        result = con.execute(f"SELECT * FROM read_parquet({_sql_quote(str(events_path))})")
        reader = result.to_arrow_reader(batch_size)
        for record_batch in reader:
            for row in record_batch.to_pylist():
                row = dict(row)
                row["payload"] = json.loads(row["payload"])
                yield row
    finally:
        con.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m nextmove.ingest")
    parser.add_argument("--profile", default="default", help="Config profile name to run.")
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Output root; defaults to the storage layer's DATA_ROOT.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    resolved = load_config(args.profile)
    raw_records = _raw_record_stream(args.out, VALIDATION_BATCH_SIZE)
    result = ingest_events(raw_records, resolved, out_root=args.out)

    print(format_dq_summary(result))

    try:
        evaluate_reject_rate(result, resolved.config.data_quality)
    except RejectRateExceeded:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
