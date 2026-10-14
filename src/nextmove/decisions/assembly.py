"""Observation step of the decision pipeline: assemble point-in-time `DecisionContext`s from the
pipeline's observable tables (`DECISION_ENGINE_DESIGN.md` §4, step 1).

Inputs are only business-observable data: the daily feature grid, the canonical event log
(campaign exposures the business itself sent, orders), the catalog and the inventory snapshots.
Nothing here reads the ground-truth zone. Every lookup is "as of" the start of the decision day:
a decision on day `d` sees feature-grid row `d` (computed over events with `ts <= d 00:00`),
contacts strictly before `d`, and the inventory left at the end of day `d - 1`.

`ContextStore.business_reference_cutoff` bounds the order history used for average order value
and the top-seller category, so evaluation contexts never use orders from their own test window.
"""

from __future__ import annotations

import json
from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from nextmove.config.loader import ResolvedConfig
from nextmove.decisions.context import BusinessState, DecisionContext
from nextmove.storage import Zone, query, resolve_table_path

__all__ = ["ContextStore", "day_index"]

_NUMERIC_GRID_COLUMNS = (
    "rfm_recency_days",
    "rfm_frequency_count",
    "rfm_monetary_cents",
    "session_visits_count",
    "session_depth_mean_views",
    "price_sensitivity_proxy",
    "message_fatigue_count",
    "cart_state_units",
    "abandonment_history_count",
)


def day_index(start: date, when: datetime | date) -> int:
    """Simulator tick (day index) of a timestamp or date."""
    day = when.date() if isinstance(when, datetime) else when
    return (day - start).days


@dataclass(frozen=True)
class _Reference:
    margin_rate: dict[str, float]
    avg_order_value_cents: dict[str, int]
    top_seller_category: str


class ContextStore:
    """In-memory, read-only index over the observable tables of one pipeline run."""

    def __init__(
        self,
        resolved: ResolvedConfig,
        root: Path | None = None,
        days: Iterable[int] | None = None,
        business_reference_cutoff: int | None = None,
    ) -> None:
        self.resolved = resolved
        self.root = root
        sim = resolved.config.simulator
        self.start: date = sim.start_date
        self.horizon_days: int = sim.horizon_days
        self.low_stock_threshold: int = sim.inventory.low_stock_threshold
        self.categories: list[str] = [category.name for category in sim.categories]
        cutoff = (
            self.horizon_days if business_reference_cutoff is None else business_reference_cutoff
        )
        self._grid = self._load_grid(days)
        self._load_events()
        self._stock = self._load_stock()
        self._reference = self._load_reference(cutoff)

    # -- loading -------------------------------------------------------------------------

    def _path(self, name: str, zone: Zone) -> Path:
        return resolve_table_path(name, zone, self.root)

    def _load_grid(self, days: Iterable[int] | None) -> pd.DataFrame:
        day_filter = ""
        if days is not None:
            wanted = sorted({int(d) for d in days})
            if not wanted:
                wanted = [-1]
            day_filter = (
                "WHERE date_diff('day', DATE '" + self.start.isoformat() + "', "
                "CAST(as_of_ts AS DATE)) IN (" + ",".join(str(d) for d in wanted) + ")"
            )
        sql = (
            "SELECT customer_id, date_diff('day', DATE '"
            + self.start.isoformat()
            + "', CAST(as_of_ts AS DATE)) AS day, "
            + ", ".join(_NUMERIC_GRID_COLUMNS)
            + ", session_dwell_counts_json, category_affinity_json, micro_conversion_counts_json "
            "FROM grid " + day_filter + " ORDER BY customer_id, day"
        )
        table = query(sql, root=self.root, grid=self._path("feature_grid", Zone.FEATURES))
        frame = table.to_pandas()
        frame["day"] = frame["day"].astype(int)
        return frame.set_index(["customer_id", "day"]).sort_index()

    def _load_events(self) -> None:
        events = self._path("events", Zone.CANONICAL)
        start = self.start.isoformat()
        exposures = query(
            "SELECT customer_id, date_diff('day', DATE '" + start + "', CAST(ts AS DATE)) AS day "
            "FROM events WHERE type = 'campaign_exposure' ORDER BY customer_id, day",
            root=self.root,
            events=events,
        ).to_pandas()
        self._exposure_days: dict[str, list[int]] = {
            str(cid): group["day"].astype(int).tolist()
            for cid, group in exposures.groupby("customer_id", sort=True)
        }
        first = query(
            "SELECT customer_id, MIN(date_diff('day', DATE '" + start + "', CAST(ts AS DATE))) "
            "AS first_day FROM events GROUP BY customer_id ORDER BY customer_id",
            root=self.root,
            events=events,
        ).to_pandas()
        self._first_day: dict[str, int] = dict(
            zip(first["customer_id"].astype(str), first["first_day"].astype(int), strict=True)
        )

    def _load_stock(self) -> dict[str, np.ndarray]:
        table = query(
            "SELECT s.tick, c.category, MIN(s.units) AS units FROM snapshots s "
            "JOIN catalog c ON c.sku = s.sku GROUP BY s.tick, c.category ORDER BY 1, 2",
            root=self.root,
            snapshots=self._path("inventory_snapshots", Zone.RAW),
            catalog=self._path("catalog", Zone.RAW),
        ).to_pandas()
        stock: dict[str, np.ndarray] = {}
        initial = self.resolved.config.simulator.inventory.initial_stock_per_sku
        for category in self.categories:
            series = np.full(self.horizon_days, initial, dtype=np.int64)
            rows = table[table["category"] == category]
            series[rows["tick"].to_numpy()] = rows["units"].to_numpy()
            stock[category] = series
        return stock

    def _load_reference(self, cutoff: int) -> _Reference:
        catalog = self._path("catalog", Zone.RAW)
        margins = query(
            "SELECT category, AVG(margin_rate) AS margin_rate, "
            "CAST(ROUND(AVG(base_price_cents)) AS BIGINT) AS mean_price "
            "FROM catalog GROUP BY category ORDER BY category",
            root=self.root,
            catalog=catalog,
        ).to_pandas()
        orders = query(
            "SELECT c.category, COUNT(*) AS n_orders, "
            "CAST(ROUND(AVG(CAST(json_extract_string(e.payload, '$.order_total_cents') "
            "AS BIGINT))) AS BIGINT) AS aov "
            "FROM events e JOIN catalog c ON c.sku = json_extract_string(e.payload, "
            "'$.line_items[0].sku') WHERE e.type = 'order_placed' AND date_diff('day', DATE '"
            + self.start.isoformat()
            + "', CAST(e.ts AS DATE)) < "
            + str(int(cutoff))
            + " GROUP BY c.category ORDER BY c.category",
            root=self.root,
            events=self._path("events", Zone.CANONICAL),
            catalog=catalog,
        ).to_pandas()
        margin_rate = {
            str(c): round(float(m), 6)
            for c, m in zip(margins["category"], margins["margin_rate"], strict=True)
        }
        aov = dict(zip(margins["category"], margins["mean_price"].astype(int), strict=True))
        aov.update(dict(zip(orders["category"], orders["aov"].astype(int), strict=True)))
        if len(orders):
            top = orders.sort_values(["n_orders", "category"], ascending=[False, True])
            top_category = str(top["category"].iloc[0])
        else:
            top_category = self.categories[0]
        return _Reference(margin_rate, aov, top_category)

    # -- lookups -------------------------------------------------------------------------

    @property
    def avg_order_value_cents(self) -> dict[str, int]:
        return dict(self._reference.avg_order_value_cents)

    @property
    def margin_rate(self) -> dict[str, float]:
        return dict(self._reference.margin_rate)

    def customer_ids(self) -> list[str]:
        return sorted(self._first_day, key=lambda cid: (len(cid), cid))

    def first_active_day(self, customer_id: str) -> int | None:
        return self._first_day.get(customer_id)

    def eligible_customers(self, day: int, rows: dict[str, dict] | None = None) -> list[str]:
        """Customers with any observed activity before `day` and a feature row on `day`."""
        rows = self.day_rows(day) if rows is None else rows
        return [cid for cid in self.customer_ids() if self._first_day[cid] < day and cid in rows]

    def has_row(self, customer_id: str, day: int) -> bool:
        return (customer_id, day) in self._grid.index

    def exposure_days_before(self, customer_id: str, day: int) -> list[int]:
        days = self._exposure_days.get(customer_id, [])
        return days[: bisect_left(days, day)]

    def business_state(self, day: int) -> BusinessState:
        prior = max(day - 1, 0)
        return BusinessState(
            category_min_stock_units={c: int(self._stock[c][prior]) for c in self.categories},
            low_stock_threshold=self.low_stock_threshold,
            category_margin_rate=self._reference.margin_rate,
            category_avg_price_cents=self._reference.avg_order_value_cents,
            top_seller_category=self._reference.top_seller_category,
        )

    def day_rows(self, day: int) -> dict[str, dict]:
        """Every feature-grid row on `day`, keyed by customer id."""
        try:
            frame = self._grid.xs(day, level="day")
        except KeyError:
            return {}
        return frame.to_dict(orient="index")

    def context(
        self,
        customer_id: str,
        day: int,
        extra_contact_days: Iterable[int] = (),
        business: BusinessState | None = None,
        row: dict | None = None,
    ) -> DecisionContext:
        """The point-in-time context for `customer_id` at the start of `day`.

        `extra_contact_days` are contacts made by the policy under evaluation (replay) or by
        an operator; they join the business's own historical campaign exposures.
        """
        if row is None:
            row = self._grid.loc[(customer_id, day)].to_dict()
        exposures = self.exposure_days_before(customer_id, day)
        contacts = sorted([*exposures, *(d for d in extra_contact_days if d < day)], reverse=True)
        affinity = json.loads(row["category_affinity_json"] or "{}")
        business = business or self.business_state(day)
        if affinity:
            primary = max(sorted(affinity), key=lambda name: affinity[name])
        else:
            primary = business.top_seller_category
        dwell = json.loads(row["session_dwell_counts_json"] or "{}")
        micro = json.loads(row["micro_conversion_counts_json"] or "{}")
        features: dict[str, float | None] = {}
        for column in _NUMERIC_GRID_COLUMNS:
            value = row[column]
            features[column] = None if value is None or pd.isna(value) else float(value)
        as_of = datetime.combine(self.start + timedelta(days=day), datetime.min.time(), UTC)
        first = self._first_day.get(customer_id, day)
        features.update(
            {
                "dwell_long_count": float(dwell.get("long", 0)),
                "dwell_medium_count": float(dwell.get("medium", 0)),
                "scroll_count": float(micro.get("scroll", 0)),
                "filter_apply_count": float(micro.get("filter_apply", 0)),
                "primary_affinity_share": float(affinity.get(primary, 0.0)),
                "contacts_7d": float(sum(1 for d in contacts if day - d <= 7)),
                "contacts_total": float(len(contacts)),
                "tenure_days": float(max(day - first, 0)),
                "month": float(as_of.month),
            }
        )
        return DecisionContext(
            customer_id=customer_id,
            as_of=as_of,
            primary_category=primary,
            features=features,
            contact_days_ago=tuple(day - d - 1 for d in contacts),
            business=business,
        )

    def as_of_day(self, as_of: datetime) -> int:
        return day_index(self.start, as_of)
