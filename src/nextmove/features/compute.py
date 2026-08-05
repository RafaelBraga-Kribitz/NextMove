"""DuckDB ASOF point-in-time computation shared by the daily grid and the on-demand path
(D-19, FEAT-01, FEAT-02).

**One definition, two call sites.** `_build_asof_sql` is the single SQL-composition function
both `compute_as_of` (the on-demand path Phase 2's decision endpoint calls) and
`materialize_grid` (the batch daily grid) call. Neither hand-rolls its own join: DuckDB's `ASOF
LEFT JOIN` establishes the inclusive `grid.as_of_ts >= events.ts` boundary structurally (an event
timestamped exactly at `as_of_ts` is seen; one microsecond later is not), and every registered
transform's own correlated subquery (`nextmove.features.definitions`) enforces the identical
boundary independently, so point-in-time correctness does not depend on the join clause alone --
a leakage test exercises the transform's own predicate, not merely the anchor join's.

**Why the grid is never one Arrow table (ENG-08, review HIGH-13).** `query` returns a fully
materialized Arrow table, so it is used only for `compute_as_of`'s on-demand path, which is
capped at `COMPUTE_AS_OF_MAX_CUSTOMERS`. The daily grid is materialized in
`GRID_CHUNK_CUSTOMERS`-sized, customer-id-ordered chunks, each streamed straight into a staging
part file by `write_query_to_part` -- never collected into one Arrow table or one Python list --
and the parts are merged out-of-core by `write_table_from_parts`. The one Python-materialized
object in `materialize_grid`'s whole call graph is the active-customer id list, produced by the
private `_active_customer_ids` helper (bounded by `n_customers`, the same population bound plan
01-08 accepts for `customer_traits`) and never by `materialize_grid`'s own body -- which is what
keeps the region-scoped `to_pylist`/`to_pandas`/`to_pydict` prohibition on `materialize_grid`
itself satisfiable rather than vacuously forbidding a necessary call.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, create_model

from nextmove.config.loader import ResolvedConfig
from nextmove.features.definitions import FEATURE_SET_VERSION, FeatureTransform, resolve_feature_set
from nextmove.storage import (
    Stage,
    Table,
    Zone,
    clear_staging,
    list_part_files,
    query,
    resolve_table_path,
    table_exists,
    write_query_to_part,
    write_table,
    write_table_from_parts,
)

__all__ = [
    "COMPUTE_AS_OF_MAX_CUSTOMERS",
    "GRID_CHUNK_CUSTOMERS",
    "compute_as_of",
    "materialize_grid",
]

#: The on-demand path's population ceiling. `query` returns a fully materialized Arrow table, so
#: `compute_as_of`'s memory cost is its result size; beyond this many customer ids the caller
#: almost certainly wants the batch path instead. A module constant, not a config key: it bounds
#: a caller's argument, not a property of the simulated world.
COMPUTE_AS_OF_MAX_CUSTOMERS = 10_000

#: The daily grid's working-set control: at most this many customers are ever "in flight" (one
#: chunk's ASOF query plus one streamed part file) regardless of the configured population. A
#: module constant, not a config key, for the same reason plan 01-08's flush knobs are not --
#: it changes how much is in flight, never which rows are produced or in what order.
GRID_CHUNK_CUSTOMERS = 5_000

_DTYPE_TO_PYTHON: dict[str, type] = {"int64": int, "float64": float, "string": str}


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def _utc_timestamptz_literal(value: datetime) -> str:
    """A DuckDB `TIMESTAMPTZ` literal carrying an explicit `+00` offset.

    **Why not a bare `TIMESTAMP` literal (RESEARCH Pitfall 1, rediscovered by
    `tests/leakage/test_no_lookahead.py`'s explicit boundary pair).** `events.ts` is stored as
    an Arrow/Parquet `timestamp(us, tz=UTC)` column (`nextmove.storage`'s schema deriver), which
    DuckDB reads back as `TIMESTAMPTZ`. A naive `TIMESTAMP '...'` literal compared against a
    `TIMESTAMPTZ` column is implicitly cast using DuckDB's **session** `TimeZone` setting, which
    defaults to the host's local zone -- `Europe/Vienna` on this dev machine, `UTC` on a
    typically-configured Linux CI runner. That default silently shifts the grid's `as_of_ts` by
    the local UTC offset, which on this dev machine was large enough to move an event from
    "at or before as_of_ts" to "after as_of_ts" and back, undetectable on a CI box already
    configured for UTC. An explicit `+00` offset on every grid timestamp removes the session
    setting from the comparison entirely, so the boundary is the same instant regardless of
    which machine or session evaluates it.
    """
    return f"TIMESTAMPTZ '{_format_timestamp(value)}+00'"


def _customer_values_relation(customer_ids: Sequence[str]) -> str:
    """A DuckDB derived-table expression yielding one `customer_id` column, one row per id in
    `customer_ids` -- or, when empty, a well-typed zero-row relation, so the caller never has to
    special-case an empty id list into a SQL syntax error."""
    if not customer_ids:
        return "(SELECT NULL::VARCHAR AS customer_id WHERE FALSE) AS _customers"
    rows = ", ".join(f"({_sql_quote(cid)})" for cid in customer_ids)
    return f"(VALUES {rows}) AS _customers(customer_id)"


def _build_asof_sql(transforms: Sequence[FeatureTransform], grid_sql: str) -> str:
    """Compose `transforms`' `sql_expression` fragments into one DuckDB statement ASOF LEFT
    JOINing the canonical `events` table (bound by the caller as a `table_bindings` view named
    `events`) onto the `(customer_id, as_of_ts)` grid relation produced by `grid_sql`.

    The join predicate `grid.as_of_ts >= events.ts` is deliberately inclusive: a feature computed
    at exactly an event's timestamp sees that event, and an event one microsecond later does not.
    Every transform's own `sql_expression` re-enforces the identical `<=` boundary independently
    (see `nextmove.features.definitions`'s module docstring), so this join's role is structural --
    it is what makes the statement a genuine ASOF-joined point-in-time computation rather than an
    unbounded cross join -- not the sole enforcement point a leakage test would need to trust.

    Ends with an explicit `ORDER BY` so output row order is deterministic rather than dependent on
    DuckDB's execution plan; both callers additionally sort at the write site (`query`'s caller
    for the on-demand path; `write_query_to_part`'s own outer `ORDER BY` for the grid path).
    """
    columns = ",\n    ".join(
        f'{transform.sql_expression} AS "{transform.output_column}"' for transform in transforms
    )
    return f"""
WITH grid AS (
    {grid_sql}
),
grid_anchor AS (
    SELECT grid.customer_id, grid.as_of_ts, events.ts AS anchor_ts
    FROM grid
    ASOF LEFT JOIN events
        ON grid.customer_id = events.customer_id
       AND grid.as_of_ts >= events.ts
)
SELECT
    grid_anchor.customer_id,
    grid_anchor.as_of_ts,
    {columns}
FROM grid_anchor
ORDER BY grid_anchor.customer_id, grid_anchor.as_of_ts
""".strip()


def compute_as_of(
    customer_ids: Sequence[str],
    as_of_ts: datetime,
    resolved: ResolvedConfig,
    out_root: Path | None = None,
) -> Table:
    """The on-demand point-in-time lookup: every registered feature for each id in
    `customer_ids`, evaluated at the single timestamp `as_of_ts`.

    Raises `ValueError` naming `as_of_ts` when it is naive (RESEARCH Pitfall 1: a naive/aware
    comparison mid-pipeline breaks point-in-time correctness in ways that are easy to miss), and
    raises `ValueError` naming `COMPUTE_AS_OF_MAX_CUSTOMERS`, the supplied count, and
    `materialize_grid` when `customer_ids` exceeds the on-demand ceiling -- `query` returns a
    fully materialized Arrow table, so this function's memory cost is its result size, and it
    must not silently become the bulk path.
    """
    if as_of_ts.tzinfo is None:
        raise ValueError(
            "compute_as_of requires a timezone-aware as_of_ts; a naive datetime for 'as_of_ts' "
            "is rejected rather than silently interpreted as local time"
        )
    customer_ids = list(customer_ids)
    if len(customer_ids) > COMPUTE_AS_OF_MAX_CUSTOMERS:
        raise ValueError(
            f"compute_as_of received {len(customer_ids)} customer_ids, exceeding "
            f"COMPUTE_AS_OF_MAX_CUSTOMERS={COMPUTE_AS_OF_MAX_CUSTOMERS}; use materialize_grid for "
            "a bulk computation instead"
        )

    _check_catalog_present(out_root)
    transforms = resolve_feature_set(resolved.config.features)
    grid_sql = (
        f"SELECT customer_id, {_utc_timestamptz_literal(as_of_ts)} AS as_of_ts "
        f"FROM {_customer_values_relation(customer_ids)}"
    )
    sql = _build_asof_sql(transforms, grid_sql)
    events_path = resolve_table_path("events", Zone.CANONICAL, root=out_root)
    return query(sql, root=out_root, events=events_path)


def _check_catalog_present(out_root: Path | None) -> None:
    """Confirm the simulator's `catalog` table (`Zone.RAW`) exists, without reading its
    contents.

    Category and sku identifiers are only meaningful compared against the catalog's single
    canonical spelling (see `nextmove.features.definitions`'s NFC-normalization discipline); the
    event payloads this stage actually aggregates already carry that canonical spelling as
    written by the trusted simulator/adapter, so no transform reads the catalog's rows today.
    This check exists so a features run against a `Zone.RAW` with no catalog at all -- an input
    state that would make every category/sku identifier unverifiable in principle, even though
    nothing here would currently notice -- resolves the same zone a future catalog-validating
    transform would, keeping `Zone.RAW` a genuine, exercised input to this stage rather than a
    read permission that is granted but never used. Never raises: an absent catalog does not
    block computation today, since no transform depends on its contents yet.
    """
    table_exists("catalog", Zone.RAW, root=out_root)


def _active_customer_ids(out_root: Path | None) -> list[str]:
    """The one Python materialization in this module's call graph: every distinct
    `customer_id` in the canonical `events` table, ascending -- bounded by `n_customers`, the
    same population bound plan 01-08 accepts for `customer_traits`. Deliberately its own
    function, never inlined into `materialize_grid`'s body: the region-scoped
    `to_pylist`/`to_pandas`/`to_pydict` prohibition on `materialize_grid` itself would otherwise
    forbid this necessary call and could never go green.
    """
    events_path = resolve_table_path("events", Zone.CANONICAL, root=out_root)
    result = query(
        "SELECT DISTINCT customer_id FROM events ORDER BY customer_id",
        root=out_root,
        events=events_path,
    )
    return result.column("customer_id").to_pylist()


def _empty_feature_grid_row_model(transforms: Sequence[FeatureTransform]) -> type[BaseModel]:
    """Build, once per call, the Pydantic row model naming every column `feature_grid` carries --
    `customer_id`, `as_of_ts`, plus one field per registered transform's `output_column` -- so the
    zero-active-customer fallback (`write_table([], ..., row_model=...)`) writes the table's full
    schema rather than an empty two-column stub."""
    fields: dict[str, tuple[type, object]] = {
        "customer_id": (str, ...),
        "as_of_ts": (datetime, ...),
    }
    for transform in transforms:
        python_type = _DTYPE_TO_PYTHON[transform.dtype]
        if transform.empty_default is None:
            python_type = python_type | None  # type: ignore[assignment]
        fields[transform.output_column] = (python_type, transform.empty_default)
    return create_model("_FeatureGridEmptyRow", **fields)  # type: ignore[call-overload]


def materialize_grid(
    resolved: ResolvedConfig,
    out_root: Path | None = None,
    chunk_customers: int = GRID_CHUNK_CUSTOMERS,
) -> Path:
    """Materialize the full daily `feature_grid`: one row per active customer per day across the
    configured horizon (D-19), in customer-id-ordered chunks of at most `chunk_customers`
    customers, each chunk's ASOF result streamed straight to a staging part file and the parts
    merged out-of-core -- the grid is never one Arrow table and never one Python list of rows
    (ENG-08, review HIGH-13).

    `chunk_customers` is a working-set control only: it changes how much is in flight, never
    which rows are produced or in what order (`tests/integration/test_features_budget.py` asserts
    this invariance). `out_root` is forwarded as `root` to every storage call, so a run directed
    at an alternate root never reads or writes the repository's own `data/` tree.
    """
    _check_catalog_present(out_root)
    transforms = resolve_feature_set(resolved.config.features)
    customer_ids = _active_customer_ids(out_root)
    events_path = resolve_table_path("events", Zone.CANONICAL, root=out_root)

    simulator_config = resolved.config.simulator
    start_ts = datetime(
        simulator_config.start_date.year,
        simulator_config.start_date.month,
        simulator_config.start_date.day,
        tzinfo=UTC,
    )
    end_ts = start_ts + timedelta(days=simulator_config.horizon_days - 1)
    day_series_sql = (
        "SELECT unnest(generate_series("
        f"{_utc_timestamptz_literal(start_ts)}, "
        f"{_utc_timestamptz_literal(end_ts)}, "
        "INTERVAL 1 DAY)) AS as_of_ts"
    )

    part_index = 0
    for chunk_start in range(0, len(customer_ids), chunk_customers):
        chunk_ids = customer_ids[chunk_start : chunk_start + chunk_customers]
        if not chunk_ids:
            continue
        grid_sql = (
            "SELECT _customers.customer_id, days.as_of_ts "
            f"FROM {_customer_values_relation(chunk_ids)} "
            f"CROSS JOIN ({day_series_sql}) AS days"
        )
        sql = _build_asof_sql(transforms, grid_sql)
        write_query_to_part(
            sql,
            part_dir="feature_grid",
            part_index=part_index,
            sort_key=("customer_id", "as_of_ts"),
            root=out_root,
            events=events_path,
        )
        part_index += 1

    parts = list_part_files("feature_grid", root=out_root)
    if parts:
        dest = write_table_from_parts(
            parts,
            table_name="feature_grid",
            zone=Zone.FEATURES,
            sort_key=("customer_id", "as_of_ts"),
            resolved_config=resolved,
            producer_stage=Stage.FEATURES,
            input_paths=[events_path],
            extra_metadata={"feature_set_version": FEATURE_SET_VERSION},
            root=out_root,
        )
    else:
        dest = write_table(
            [],
            table_name="feature_grid",
            zone=Zone.FEATURES,
            sort_key=("customer_id", "as_of_ts"),
            resolved_config=resolved,
            producer_stage=Stage.FEATURES,
            input_paths=[events_path],
            extra_metadata={"feature_set_version": FEATURE_SET_VERSION},
            root=out_root,
            row_model=_empty_feature_grid_row_model(transforms),
        )

    clear_staging(root=out_root)
    return dest
