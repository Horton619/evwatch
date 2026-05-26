"""AutoTrader scraper (Mac-only, Playwright).

AutoTrader serves real listings only to a real browser; httpx gets a
client-shell template. OEM-direct programs (Tesla, Ford, etc.) sometimes
list here at prices that don't show up on the dealer-network sources.

Mac-only — guarded by EVWATCH_ALLOW_MAC_ONLY_SCRAPERS.
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

SOURCE = "autotrader"

BASE_URL = "https://www.autotrader.com/cars-for-sale/all-cars"

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILEAGE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:mi|miles)\b", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d{4,6})")
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")


def _ensure_mac_only() -> None:
    if os.environ.get("EVWATCH_ALLOW_MAC_ONLY_SCRAPERS") != "1":
        raise SystemExit(
            "[autotrader] refusing to run without EVWATCH_ALLOW_MAC_ONLY_SCRAPERS=1. "
            "Run from the Mac app on a residential IP, not GHA."
        )


def _search_url(make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> str:
    # AutoTrader's URL accepts a make/model/year filter in the query.
    return (
        f"{BASE_URL}"
        f"?makeCodeList={make.upper().replace(' ', '')}"
        f"&modelCodeList={model.upper().replace(' ', '').replace('-', '')}"
        f"&zip={PORT_ORCHARD_ZIP}"
        f"&searchRadius={radius}"
        f"&startYear={min_year}"
        f"&maxMileage={max_mileage}"
        f"&sortBy=relevance"
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


def _stable_id_from_url(url: str) -> str:
    # AutoTrader listing URLs include a numeric listing id near the end.
    m = re.search(r"/(\d{9,})(?:\?|$)", url)
    if m:
        return m.group(1)
    vin_m = VIN_RE.search(url)
    if vin_m:
        return vin_m.group(0)
    return url[-40:]


def _scrape_results_page(page: Page, expected_make: str, expected_model: str) -> list[Listing]:
    try:
        page.wait_for_selector("[data-cmp='inventoryListing']", timeout=15000)
    except Exception as e:  # noqa: BLE001
        print(f"[autotrader] no listings rendered for {expected_make} {expected_model}: {e}", file=sys.stderr)
        return []

    out: list[Listing] = []
    for card in page.query_selector_all("[data-cmp='inventoryListing']"):
        link_el = card.query_selector("a[href*='/cars-for-sale/']")
        url = link_el.get_attribute("href") if link_el else None
        if not url:
            continue
        if not url.startswith("http"):
            url = f"https://www.autotrader.com{url}"

        text = card.inner_text()
        title_el = card.query_selector("h3, [data-cmp='subheading']")
        title = title_el.inner_text().strip() if title_el else ""
        if expected_make.lower() not in title.lower() and expected_model.lower() not in title.lower():
            continue

        price_m = PRICE_RE.search(text)
        mileage_m = MILEAGE_RE.search(text)
        vin_m = VIN_RE.search(text + " " + url)

        img_el = card.query_selector("img")
        thumbnail = None
        if img_el:
            for attr in ("data-src", "src"):
                v = img_el.get_attribute(attr)
                if v and v.startswith("http"):
                    thumbnail = v
                    break

        # Location is usually a "City, ST" line. Best-effort.
        location: str | None = None
        for line in text.splitlines():
            line = line.strip()
            if re.match(r"^[A-Z][a-zA-Z\.\s]+,\s*[A-Z]{2}$", line):
                location = line
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
                location=location,
                miles_from_port_orchard=None,
                thumbnail_url=thumbnail,
                raw={"title": title, "card_text": text[:1000]},
            )
        )
    return out


def scrape(filters: dict | None = None) -> list[Listing]:
    _ensure_mac_only()
    wl = load_watchlist()
    cfg = wl.get("filters") or {}
    radius = int(cfg.get("radius_miles") or 100)
    min_year = int(cfg.get("min_year") or 2020)
    max_mileage = int(cfg.get("max_mileage") or 80000)

    entries = (wl.get("priority_models") or []) + (wl.get("broad_models") or [])
    listings: list[Listing] = []
    seen: set[str] = set()

    with browser_context() as ctx:
        page = ctx.new_page()
        for entry in entries:
            make = entry["make"]
            model = entry["model"]
            url = _search_url(make, model, radius=radius, min_year=min_year, max_mileage=max_mileage)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                if resp and resp.status >= 400:
                    print(f"[autotrader] {make} {model} -> HTTP {resp.status}", file=sys.stderr)
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[autotrader] {make} {model} nav failed: {e}", file=sys.stderr)
                continue

            for l in _scrape_results_page(page, make, model):
                if l.source_listing_id in seen:
                    continue
                seen.add(l.source_listing_id)
                listings.append(l)

    return listings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape AutoTrader (Mac-only).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
