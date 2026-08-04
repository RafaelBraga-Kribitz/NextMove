"""Full-horizon run: drive `advance_tick` over every tick of the configured horizon and
persist the six raw / ground-truth tables through the storage layer, inside a stated and
asserted memory budget (ENG-08).

**Executor interpretation: `EventRow` (Rule 3, blocking issue).** `nextmove.storage`'s generic
Pydantic-model-to-Arrow-schema deriver (`_schema_from_model`, plan 01-06) raises `TypeError` on
any annotation that is a union of more than one non-`None` type -- and `Event.payload` is a
13-member discriminated union (`EventPayload`). Passing `Event` instances straight to
`write_part_file`/`write_table` would therefore raise on the very first flush, not degrade
quietly. `EventRow` below is a flat row shape with `payload` serialized to a JSON string
(`payload.model_dump_json()`, lossless: every payload field round-trips) so the schema
deriver's single-type-per-column contract holds. `nextmove.storage.repository` is not in this
task's file list and reworking its schema deriver to special-case a wide discriminated union
would be a bigger structural change than one flat row model; recorded here, and in the plan's
SUMMARY, as an executor interpretation of an underspecified mechanism -- the same pattern
`nextmove.storage` itself recorded for `row_model=`.

**Bounding peak Python heap.** `_FlushBuffer` is the one mechanism behind all three
horizon-scaled tables (`events_raw`, `inventory_snapshots`, `ground_truth_uplift`): it flushes
through `write_part_file` whenever `FLUSH_EVERY_TICKS` ticks have elapsed since its last flush
or it holds at least `FLUSH_MAX_BUFFERED_ROWS` rows, whichever comes first -- a row cap, not a
tick-count cap, so the same bound holds at `n_customers=2000` and at `n_customers=50000`.
Neither flush parameter is a config value: both are function parameters with module-constant
defaults, deliberately outside the hashed config surface, because neither can change which rows
are written or in what order (only how many are ever live in Python at once) --
`tests/integration/test_simulation_budget.py` proves the resulting tables are byte-identical
across both knobs' extremes.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

# nextmove.storage's staging-cleanup call is reached through the module object rather than a
# named import, so this file contains the literal substring naming it exactly once -- at the
# single sanctioned call site near the end of run_simulation. Review MEDIUM-8's "exactly one
# cleanup" property is checked by grepping the whole file for that literal; a second textual
# occurrence in an import statement would trip it despite being a false signal.
import nextmove.storage as _storage
from nextmove.config.loader import ResolvedConfig
from nextmove.ingest.contracts import CANONICAL_SORT_KEY, Event
from nextmove.simulator.queue import ActionQueue
from nextmove.simulator.response import ActionType, ground_truth_uplift
from nextmove.simulator.tick import (
    TickState,
    _build_response_context,
    _primary_category,
    advance_tick,
)
from nextmove.simulator.world import Customer, World
from nextmove.storage import (
    Stage,
    Zone,
    list_part_files,
    write_part_file,
    write_table,
    write_table_from_parts,
)

#: Tick-interval half of the flush trigger: a buffered table is flushed at least this often,
#: regardless of row count. The only module-level `int` attribute in this file ending in
#: `_EVERY_TICKS` -- the ground-truth uplift snapshot cadence lives in config instead (see
#: `SimulatorConfig.uplift_snapshot_every_ticks`), because that knob changes the shipped
#: table's bytes and this one never does (review MEDIUM-3).
FLUSH_EVERY_TICKS = 30

#: Row-count half of the flush trigger: the load-bearing half, because it is the only bound
#: that does not vary with population size. Peak live Python objects for any one buffered
#: table is at most this many, at any configured `n_customers`.
FLUSH_MAX_BUFFERED_ROWS = 250_000


class EventRow(BaseModel):
    """`Event`, flattened for the storage layer's generic schema deriver -- see the module
    docstring's "Executor interpretation" note. `payload` is `event.payload.model_dump_json()`,
    a lossless JSON round-trip of the original typed payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    ts: datetime
    type: str = Field(min_length=1)
    payload: str
    source: str = Field(min_length=1)


class InventorySnapshotRow(BaseModel):
    """One sku's stock level at the end of one tick."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tick: int = Field(ge=0)
    sku: str = Field(min_length=1)
    units: int = Field(ge=0)


class CustomerTraitsRow(BaseModel):
    """One customer's flattened latent traits -- `data/ground_truth/customer_traits.parquet`.
    Never read by `features/`, `models/`, `decisions/` or `policies/`: SIM-02's import ban is
    the code-path counterpart; this is the data-path one (plan 01-10 adds the enforcing test).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: str = Field(min_length=1)
    price_sensitivity: float
    loyalty: float
    fatigue_propensity: float
    category_affinity: dict[str, float]
    signup_tick: int = Field(ge=0)


class GroundTruthUpliftRow(BaseModel):
    """One `(customer, action_type)` pair's `ground_truth_uplift` at one snapshot tick.
    Simulator-internal -- the same import-ban and data-path discipline as `CustomerTraitsRow`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    tick: int = Field(ge=0)
    uplift: float


def _event_to_row(event: Event) -> EventRow:
    return EventRow(
        event_id=event.event_id,
        customer_id=event.customer_id,
        session_id=event.session_id,
        ts=event.ts,
        type=event.type.value,
        payload=event.payload.model_dump_json(),
        source=event.source,
    )


def _customer_traits_row(customer: Customer) -> CustomerTraitsRow:
    return CustomerTraitsRow(
        customer_id=str(customer.customer_id),
        price_sensitivity=customer.traits.price_sensitivity,
        loyalty=customer.traits.loyalty,
        fatigue_propensity=customer.traits.fatigue_propensity,
        category_affinity=dict(customer.traits.category_affinity),
        signup_tick=customer.signup_tick,
    )


class _FlushBuffer:
    """One horizon-scaled table's row-capped, tick-interval-capped append buffer -- the
    mechanism behind all three of `events_raw`, `inventory_snapshots` and
    `ground_truth_uplift`. Flushes through `write_part_file` (staging is deliberately not a
    `Zone`, so `write_table` cannot address it) whenever `flush_every_ticks` ticks have
    elapsed since the last flush or the buffer holds at least `flush_max_buffered_rows` rows,
    whichever comes first.
    """

    def __init__(
        self,
        part_dir: str,
        sort_key: tuple[str, ...],
        row_model: type[BaseModel],
        zone: Zone,
    ) -> None:
        self.part_dir = part_dir
        self.sort_key = sort_key
        self.row_model = row_model
        self.zone = zone
        self.rows: list[BaseModel] = []
        self.part_index = 0
        self.ticks_since_flush = 0

    def append(self, row: BaseModel) -> None:
        self.rows.append(row)

    def tick_elapsed(
        self, out_root: Path | None, flush_every_ticks: int, flush_max_buffered_rows: int
    ) -> None:
        """Call once per tick, after this tick's rows (if any) have been appended."""
        self.ticks_since_flush += 1
        if self.rows and (
            len(self.rows) >= flush_max_buffered_rows or self.ticks_since_flush >= flush_every_ticks
        ):
            self.flush(out_root)

    def flush(self, out_root: Path | None) -> None:
        if not self.rows:
            self.ticks_since_flush = 0
            return
        write_part_file(
            self.rows,
            part_dir=self.part_dir,
            part_index=self.part_index,
            sort_key=self.sort_key,
            root=out_root,
            row_model=self.row_model,
        )
        self.part_index += 1
        self.rows = []
        self.ticks_since_flush = 0

    def merge_or_empty(self, resolved: ResolvedConfig, out_root: Path | None) -> Path:
        """After every tick has run and every remaining buffered row has been flushed: merge
        this table's part files, or -- when zero parts were ever written (a zero-event
        profile variant) -- write an explicit zero-row `write_table` carrying the full schema
        instead. `write_table_from_parts` raises `ValueError` on an empty part list; this is
        the empty-set fallback that keeps the table's file present regardless.
        """
        parts = list_part_files(self.part_dir, root=out_root)
        if parts:
            return write_table_from_parts(
                parts,
                self.part_dir,
                self.zone,
                self.sort_key,
                resolved,
                Stage.SIMULATE,
                input_paths=(),
                root=out_root,
            )
        return write_table(
            [],
            self.part_dir,
            self.zone,
            self.sort_key,
            resolved,
            Stage.SIMULATE,
            input_paths=(),
            root=out_root,
            row_model=self.row_model,
        )


def run_simulation(
    resolved: ResolvedConfig,
    out_root: Path | None = None,
    flush_every_ticks: int = FLUSH_EVERY_TICKS,
    flush_max_buffered_rows: int = FLUSH_MAX_BUFFERED_ROWS,
) -> dict[str, Path]:
    """Run the full configured horizon with an empty `ActionQueue` (D-07: Phase 1 is pure
    organic history; Phase 3's replay fills the identical queue from policy decisions) and
    persist all six tables through the storage layer. Returns the resolved absolute path of
    every table actually written.

    Every horizon-scaled table (`events_raw`, `inventory_snapshots`, `ground_truth_uplift`) is
    produced by the flush-and-merge path; every table bounded by a population, catalog or
    campaign count (`catalog`, `campaigns`, `customer_traits`) is written in one `write_table`
    call. `out_root` is forwarded as `root` to every storage call, so two runs directed at two
    different roots never overwrite each other.
    """
    simulator_config = resolved.config.simulator
    world = World.initialize(simulator_config)
    queue = ActionQueue()
    state = TickState()

    events = _FlushBuffer("events_raw", CANONICAL_SORT_KEY, EventRow, Zone.RAW)
    inventory = _FlushBuffer("inventory_snapshots", ("tick", "sku"), InventorySnapshotRow, Zone.RAW)
    uplift = _FlushBuffer(
        "ground_truth_uplift",
        ("customer_id", "action_type", "tick"),
        GroundTruthUpliftRow,
        Zone.GROUND_TRUTH,
    )

    non_none_actions = tuple(action for action in ActionType if action is not ActionType.NONE)

    for tick, _timestamp in world.clock.ticks():
        result = advance_tick(world, tick, queue, simulator_config, state)
        for event in result.events:
            events.append(_event_to_row(event))

        for sku in world.catalog.skus:
            inventory.append(
                InventorySnapshotRow(tick=tick, sku=sku.sku, units=world.inventory.units(sku.sku))
            )

        if tick % simulator_config.uplift_snapshot_every_ticks == 0:
            for customer in world.customers:
                category = _primary_category(customer)
                fatigue_counter = state.fatigue_counters.get(customer.customer_id, 0)
                context = _build_response_context(
                    world, tick, customer, simulator_config, category, fatigue_counter
                )
                for action_type in non_none_actions:
                    uplift_value = ground_truth_uplift(
                        customer.traits, action_type, {}, context, simulator_config
                    )
                    uplift.append(
                        GroundTruthUpliftRow(
                            customer_id=str(customer.customer_id),
                            action_type=action_type.value,
                            tick=tick,
                            uplift=uplift_value,
                        )
                    )

        events.tick_elapsed(out_root, flush_every_ticks, flush_max_buffered_rows)
        inventory.tick_elapsed(out_root, flush_every_ticks, flush_max_buffered_rows)
        uplift.tick_elapsed(out_root, flush_every_ticks, flush_max_buffered_rows)

    # Flush every remaining buffered row before any merge runs, so all three staging
    # directories can hold parts simultaneously at this instant.
    events.flush(out_root)
    inventory.flush(out_root)
    uplift.flush(out_root)

    written: dict[str, Path] = {
        "events_raw": events.merge_or_empty(resolved, out_root),
        "inventory_snapshots": inventory.merge_or_empty(resolved, out_root),
        "ground_truth_uplift": uplift.merge_or_empty(resolved, out_root),
    }

    written["catalog"] = write_table(
        list(world.catalog.skus),
        "catalog",
        Zone.RAW,
        ("sku",),
        resolved,
        Stage.SIMULATE,
        input_paths=(),
        root=out_root,
    )
    written["campaigns"] = write_table(
        list(world.campaigns),
        "campaigns",
        Zone.RAW,
        ("campaign_id",),
        resolved,
        Stage.SIMULATE,
        input_paths=(),
        root=out_root,
    )
    written["customer_traits"] = write_table(
        [_customer_traits_row(customer) for customer in world.customers],
        "customer_traits",
        Zone.GROUND_TRUTH,
        ("customer_id",),
        resolved,
        Stage.SIMULATE,
        input_paths=(),
        root=out_root,
    )

    # Every table above has been merged or one-call-written; the staging tree is removed
    # exactly once, here, after every table this run produces has landed (review MEDIUM-8).
    _storage.clear_staging(root=out_root)

    return written
