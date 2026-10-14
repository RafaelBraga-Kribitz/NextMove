"""Capture the UC1 demo screenshots into docs/assets/ (AC-14 evidence).

Usage (with `just serve` running on port 8000):
    uv run --with playwright python scripts/capture_demo_screenshots.py [customer_id]

Uses an already-installed Chromium (PLAYWRIGHT_BROWSERS_PATH, or CHROMIUM_PATH for a specific
binary); Playwright is not a project dependency.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"


def main(customer: str | None = None) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        executable = os.environ.get("CHROMIUM_PATH")
        browser = (
            p.chromium.launch(executable_path=executable) if executable else p.chromium.launch()
        )
        page = browser.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=1)
        page.goto(f"{BASE}/demo")
        page.screenshot(path=str(ASSETS / "demo_home.png"), full_page=True)
        link = (
            page.locator(f'a[href^="/demo/customers/{customer}?"]').first
            if customer
            else page.locator('a[href^="/demo/customers/"]').first
        )
        link.click()
        page.wait_for_load_state()
        page.screenshot(path=str(ASSETS / "demo_customer.png"), full_page=True)
        # Override towards an action that does something, so the evaluation shows its price.
        options = page.locator("select[name=override_candidate] option").all_text_contents()
        preferred = [o for o in options if o.startswith(("recommend", "email", "bundle"))]
        if preferred:
            page.select_option("select[name=override_candidate]", preferred[0])
        page.locator("button[type=submit]").click()
        page.wait_for_load_state()
        page.screenshot(path=str(ASSETS / "demo_evaluation.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    main(*sys.argv[1:])
