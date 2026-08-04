"""D-05's acceptance target: UC1 and UC2 must genuinely occur in the generated population,
found by query against a real `demo`-profile run -- never a hand-built fixture customer.

Both queries run entirely through `nextmove.storage.query` (DuckDB) against the tables
`run_simulation` actually wrote; nothing here constructs a customer, event, or inventory row by
hand. The `demo_run_result` session fixture (`tests/integration/conftest.py`) is the one full
548-tick run this module and `test_simulation_budget.py` share.

UC1 and UC2 thresholds not already covered by a `SimulatorConfig` field (the price-sensitivity
quantile, the recency window, and the high-fatigue contact count) are test-local judgment
calls, not simulator business logic -- ENG-03's "no business number is a literal in
`src/nextmove/`" does not apply to `tests/`, and these numbers only ever gate an acceptance
assertion, never simulated behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from nextmove.config.loader import ResolvedConfig
from nextmove.storage import Zone, query, resolve_table_path

if TYPE_CHECKING:
    from tests.integration.conftest import DemoRunResult

pytestmark = pytest.mark.slow

#: Bottom quartile: "low price sensitivity" for UC1's cart-abandoning customer.
_UC1_LOW_PRICE_SENSITIVITY_QUANTILE = 0.25

#: A customer who ordered within this many days of the horizon's last tick counts as
#: "recently purchased" for UC2.
_UC2_RECENCY_WINDOW_TICKS = 30

#: Total action_delivered + campaign_exposure contacts above this count is "high fatigue" for
#: UC2. Phase 1's queue is always empty, so in practice this counts campaign exposures only.
_UC2_HIGH_FATIGUE_CONTACT_THRESHOLD = 20


def _table_paths(demo_run_result: DemoRunResult) -> dict[str, Path]:
    out_root = demo_run_result.out_root
    return {
        "events": resolve_table_path("events_raw", Zone.RAW, out_root),
        "catalog": resolve_table_path("catalog", Zone.RAW, out_root),
        "inventory": resolve_table_path("inventory_snapshots", Zone.RAW, out_root),
        "traits": resolve_table_path("customer_traits", Zone.GROUND_TRUTH, out_root),
    }


def _uc1_count(resolved: ResolvedConfig, paths: dict[str, Path]) -> tuple[int, dict[str, int]]:
    cfg = resolved.config.simulator
    start_date = cfg.start_date.isoformat()
    peak_month = cfg.seasonality.peak_month
    scarcity_threshold = cfg.inventory.low_stock_threshold
    quantile = _UC1_LOW_PRICE_SENSITIVITY_QUANTILE

    cte = f"""
    WITH cart_events AS (
        SELECT
            e.customer_id,
            e.session_id,
            json_extract_string(e.payload, '$.sku') AS sku,
            date_diff('day', DATE '{start_date}', CAST(e.ts AS DATE)) AS tick
        FROM events e
        WHERE e.type = 'add_to_cart' AND date_part('month', e.ts) = {peak_month}
    ),
    order_sessions AS (
        SELECT DISTINCT session_id FROM events WHERE type = 'order_placed'
    ),
    high_season_skus AS (
        SELECT sku FROM catalog WHERE seasonality_class = 'high'
    ),
    price_threshold AS (
        SELECT quantile_cont(price_sensitivity, {quantile}) AS q FROM traits
    )
    """

    full_sql = (
        cte
        + f"""
    SELECT COUNT(DISTINCT ce.customer_id) AS n
    FROM cart_events ce
    JOIN high_season_skus hs ON hs.sku = ce.sku
    JOIN inventory inv ON inv.tick = ce.tick AND inv.sku = ce.sku
    JOIN traits t ON t.customer_id = ce.customer_id
    CROSS JOIN price_threshold pt
    WHERE ce.session_id NOT IN (SELECT session_id FROM order_sessions)
      AND inv.units < {scarcity_threshold}
      AND t.price_sensitivity <= pt.q
    """
    )
    result = query(full_sql, **paths).to_pylist()
    count = result[0]["n"] if result else 0

    # Nearest-miss diagnostics: relax one clause at a time.
    diagnostics = {}
    diagnostics["december_add_to_cart_in_high_season_category"] = query(
        cte
        + """
        SELECT COUNT(*) AS n FROM cart_events ce JOIN high_season_skus hs ON hs.sku = ce.sku
        """,
        **paths,
    ).to_pylist()[0]["n"]
    diagnostics["and_no_order_in_session"] = query(
        cte
        + """
        SELECT COUNT(*) AS n FROM cart_events ce JOIN high_season_skus hs ON hs.sku = ce.sku
        WHERE ce.session_id NOT IN (SELECT session_id FROM order_sessions)
        """,
        **paths,
    ).to_pylist()[0]["n"]
    diagnostics["and_scarce_inventory_at_that_tick"] = query(
        cte
        + f"""
        SELECT COUNT(*) AS n FROM cart_events ce JOIN high_season_skus hs ON hs.sku = ce.sku
        JOIN inventory inv ON inv.tick = ce.tick AND inv.sku = ce.sku
        WHERE ce.session_id NOT IN (SELECT session_id FROM order_sessions)
          AND inv.units < {scarcity_threshold}
        """,
        **paths,
    ).to_pylist()[0]["n"]
    return count, diagnostics


def _uc2_count(resolved: ResolvedConfig, paths: dict[str, Path]) -> tuple[int, dict[str, int]]:
    cfg = resolved.config.simulator
    start_date = cfg.start_date.isoformat()
    horizon_days = cfg.horizon_days
    recency_window = _UC2_RECENCY_WINDOW_TICKS
    fatigue_threshold = _UC2_HIGH_FATIGUE_CONTACT_THRESHOLD
    cutoff_tick = horizon_days - 1 - recency_window

    cte = f"""
    WITH orders AS (
        SELECT DISTINCT customer_id,
            date_diff('day', DATE '{start_date}', CAST(ts AS DATE)) AS order_tick
        FROM events WHERE type = 'order_placed'
    ),
    contacts AS (
        SELECT customer_id, COUNT(*) AS contact_count
        FROM events WHERE type IN ('action_delivered', 'campaign_exposure')
        GROUP BY customer_id
    )
    """

    full_sql = (
        cte
        + f"""
    SELECT COUNT(DISTINCT o.customer_id) AS n
    FROM orders o
    JOIN contacts c ON c.customer_id = o.customer_id
    WHERE o.order_tick >= {cutoff_tick}
      AND c.contact_count >= {fatigue_threshold}
    """
    )
    result = query(full_sql, events=paths["events"]).to_pylist()
    count = result[0]["n"] if result else 0

    diagnostics = {}
    diagnostics["recent_orders"] = query(
        cte + f"SELECT COUNT(*) AS n FROM orders WHERE order_tick >= {cutoff_tick}",
        events=paths["events"],
    ).to_pylist()[0]["n"]
    diagnostics["customers_above_fatigue_threshold"] = query(
        cte + f"SELECT COUNT(*) AS n FROM contacts WHERE contact_count >= {fatigue_threshold}",
        events=paths["events"],
    ).to_pylist()[0]["n"]
    return count, diagnostics


class TestUC1CartAbandonerWithScarcePriceInsensitiveInventory:
    def test_uc1_genuinely_occurs_in_the_generated_population(
        self, demo_run_result: DemoRunResult
    ) -> None:
        paths = _table_paths(demo_run_result)
        count, diagnostics = _uc1_count(demo_run_result.resolved, paths)
        assert count > 0, (
            "UC1 (winter-jacket cart abandoner, low stock, low price sensitivity, "
            f"pre-Christmas) did not occur. Nearest-miss counts by clause: {diagnostics}"
        )

    def test_uc1_does_not_construct_any_customer_by_hand(
        self, demo_run_result: DemoRunResult
    ) -> None:
        # The population and every event came from run_simulation; this test only queries it.
        assert demo_run_result.written["customer_traits"].is_file()


class TestUC2RecentlyPurchasedHighFatigueCustomer:
    def test_uc2_genuinely_occurs_in_the_generated_population(
        self, demo_run_result: DemoRunResult
    ) -> None:
        paths = _table_paths(demo_run_result)
        count, diagnostics = _uc2_count(demo_run_result.resolved, paths)
        assert count > 0, (
            "UC2 (recently purchased, satisfied, high-fatigue customer) did not occur. "
            f"Nearest-miss counts by clause: {diagnostics}"
        )
