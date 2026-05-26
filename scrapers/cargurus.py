"""CarGurus scraper (Mac-only, Playwright).

CarGurus' API is bot-protected hard — Cloudflare + behavior heuristics —
so we drive a headless Chromium against the search-results page and
extract from the rendered DOM.

Captures the CarGurus "Deal Rating" label per listing (great/good/fair/
high/overpriced) which is a useful market signal independent of our own
baselines.

Mac-only: this scraper is NEVER run from GitHub Actions. Residential IP
matters too much, and CarGurus blocks datacenter ASNs aggressively.
Guard via the ``EVWATCH_ALLOW_MAC_ONLY_SCRAPERS`` env var so an
accidental GHA invocation fails loud and fast.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any

from playwright.sync_api import Page

from scrapers._common import (
    Listing,
    PORT_ORCHARD_ZIP,
    load_watchlist,
    miles_from_port_orchard,
    run_scraper,
)
from scrapers._playwright import browser_context

SOURCE = "cargurus"

BASE_URL = "https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action"

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILEAGE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:mi|miles)\b", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d{4,6})")
DEAL_RE = re.compile(r"\b(great|good|fair|high|overpriced)\s*(?:price|deal)\b", re.IGNORECASE)
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")


def _ensure_mac_only() -> None:
    if os.environ.get("EVWATCH_ALLOW_MAC_ONLY_SCRAPERS") != "1":
        raise SystemExit(
            "[cargurus] refusing to run without EVWATCH_ALLOW_MAC_ONLY_SCRAPERS=1. "
            "This scraper must run from the Mac app on a residential IP, never from GHA."
        )


def _search_url(make: str, model: str, *, radius: int) -> str:
    # CarGurus uses make/model entity IDs internally but accepts a free-form
    # search via the entity-resolver flow on this URL. The parameters here
    # are what their own UI fires for a basic search.
    return (
        f"{BASE_URL}"
        f"?searchId=&zip={PORT_ORCHARD_ZIP}&distance={radius}"
        f"&showNegotiable=true&sortDir=ASC&sourceContext=carGurusHomePageModel"
        f"&entitySelectingHelper.selectedEntity=&entitySelectingHelper.selectedEntity2="
        f"&searchKeywords={make.lower()}+{model.lower().replace(' ', '+')}"
    )


def _parse_int(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.sub(r"[,\s]", "", s)
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_year(text: str) -> int | None:
    m = YEAR_RE.search(text)
    if not m:
        return None
    y = int(m.group(1))
    return y if 2000 <= y <= 2030 else None


def _parse_deal_label(text: str) -> str | None:
    """Extract CarGurus' deal rating ('Great Deal', 'Good Deal', etc.)."""
    m = DEAL_RE.search(text)
    return m.group(1).lower() if m else None


def _stable_id_from_url(url: str) -> str:
    # CarGurus listing URLs include a numeric listing id like
    # /Cars/inventorylisting/.../?listingId=12345678
    m = re.search(r"listing[Ii]d=(\d+)", url)
    if m:
        return m.group(1)
    # Fall back: any 17-char VIN in the URL.
    vin_m = VIN_RE.search(url)
    if vin_m:
        return vin_m.group(0)
    return url[-40:]


def _scrape_results_page(page: Page, expected_make: str, expected_model: str) -> list[Listing]:
    try:
        page.wait_for_selector("[data-cg-ft='srp-listing-blade']", timeout=15000)
    except Exception as e:  # noqa: BLE001
        print(f"[cargurus] no listings rendered for {expected_make} {expected_model}: {e}", file=sys.stderr)
        return []

    out: list[Listing] = []
    for card in page.query_selector_all("[data-cg-ft='srp-listing-blade']"):
        link_el = card.query_selector("a[href*='listingId']")
        url = link_el.get_attribute("href") if link_el else None
        if not url:
            continue
        if not url.startswith("http"):
            url = f"https://www.cargurus.com{url}"

        text = card.inner_text()
        title_el = card.query_selector("h4, [data-cg-ft='srp-listing-title']")
        title = title_el.inner_text().strip() if title_el else ""
        if expected_make.lower() not in title.lower() and expected_model.lower() not in title.lower():
            continue

        price_m = PRICE_RE.search(text)
        mileage_m = MILEAGE_RE.search(text)
        deal_label = _parse_deal_label(text)
        vin_m = VIN_RE.search(url)

        img_el = card.query_selector("img")
        thumbnail = None
        if img_el:
            for attr in ("data-src", "src"):
                v = img_el.get_attribute(attr)
                if v and v.startswith("http"):
                    thumbnail = v
                    break

        out.append(
            Listing(
                source=SOURCE,
                source_listing_id=_stable_id_from_url(url),
                url=url,
                make=expected_make,
                model=expected_model,
                trim=None,
                year=_parse_year(title),
                mileage=_parse_int(mileage_m.group(1)) if mileage_m else None,
                price=_parse_int(price_m.group(1)) if price_m else None,
                vin=vin_m.group(0) if vin_m else None,
                location=None,
                miles_from_port_orchard=None,
                thumbnail_url=thumbnail,
                raw={
                    "title": title,
                    "deal_label": deal_label,
                    "card_text": text[:1000],
                },
            )
        )
    return out


def scrape(filters: dict | None = None) -> list[Listing]:
    _ensure_mac_only()
    wl = load_watchlist()
    cfg = wl.get("filters") or {}
    radius = int(cfg.get("radius_miles") or 100)

    entries = (wl.get("priority_models") or []) + (wl.get("broad_models") or [])
    listings: list[Listing] = []
    seen: set[str] = set()

    with browser_context() as ctx:
        page = ctx.new_page()
        for entry in entries:
            make = entry["make"]
            model = entry["model"]
            url = _search_url(make, model, radius=radius)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                if resp and resp.status >= 400:
                    print(f"[cargurus] {make} {model} -> HTTP {resp.status}", file=sys.stderr)
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[cargurus] {make} {model} nav failed: {e}", file=sys.stderr)
                continue

            for l in _scrape_results_page(page, make, model):
                if l.source_listing_id in seen:
                    continue
                seen.add(l.source_listing_id)
                listings.append(l)

    return listings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape CarGurus (Mac-only).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
