"""Shared Playwright helpers used by the residential-class scrapers.

Why Playwright instead of plain httpx for these sources:
- Carvana, Craigslist (search), and AutoTempest all serve real data only
  to a real browser-shaped request. httpx gets 403s or empty templates.
- One headless Chromium per scrape run covers all three. ``page_context()``
  builds a sensibly-defaulted browser context so each scraper just gets a
  ``Page`` and goes.

Honest disclosure: even with Playwright, datacenter IP reputation (e.g.
GitHub Actions runners) can earn 403s these sites don't give residential
IPs. CarMax stays blocked even with Playwright, hence its deferred stub.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

# A current-ish desktop Chrome UA. Updated occasionally; sites sometimes
# flag obviously-old UAs.
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@contextmanager
def browser_context(*, user_agent: str = DEFAULT_UA) -> Iterator[BrowserContext]:
    """Yield a Chromium browser context. Caller closes nothing — the context
    manager handles teardown.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/Los_Angeles",
            )
            try:
                yield ctx
            finally:
                ctx.close()
        finally:
            browser.close()


def goto_with_warmup(page: Page, target_url: str, *, warmup_url: str | None, timeout_ms: int = 20000) -> int:
    """Optionally visit ``warmup_url`` first (so cookies get set), then
    navigate to ``target_url``. Returns the final response status.
    """
    if warmup_url:
        page.goto(warmup_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(800)
    resp = page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
    return resp.status if resp else 0
