"""Craigslist scraper (Playwright).

Craigslist no longer serves their RSS search to programmatic clients
(403s even with a browser UA). The HTML search page still works if we
warm up cookies by visiting the regional homepage first.

3 host regions × 15 watchlist entries = ~45 page navigations per run,
each preceded by a homepage warmup (one warmup per region — cookies
persist across navigations in the same context). Roughly 1–2 minutes
total. Seattle CL covers Tacoma / Olympia / Bellevue under its host;
Portland and Bellingham are separate hosts.

Honest disclosure: mileage isn't on the search-result card — it lives on
the listing detail page. Phase 3 skips that follow-up fetch (would add
hundreds of nav calls per run). ``mileage`` will be ``None`` for nearly
all Craigslist listings until we either parse it from the title or add a
detail-page hop in a later phase.
"""

from __future__ import annotations

import argparse
import hashlib
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

SOURCE = "craigslist"

# Craigslist consolidates tacoma + olympia + bellevue etc. under the
# seattle.craigslist.org domain (sub-regions like /tac/, /skc/ appear in
# the listing URL path, not the host). bellingham gets its own host.
REGIONS = ["seattle", "portland", "bellingham"]

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILEAGE_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d+\s*[kK]|\d{4,6})\s*(?:mi|miles|mile)\b",
    re.IGNORECASE,
)
PRICE_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d{4,6})")
PID_RE = re.compile(r"/(\d{10})\.html\b")


def _region_zip_proxy(region: str) -> str:
    """Approximate metro zip for the regional feed. Real per-listing zip
    lives on the detail page; Phase 3 doesn't fetch those.
    """
    return {
        "seattle":    "98101",
        "tacoma":     "98402",
        "olympia":    "98501",
        "portland":   "97201",
        "bellingham": "98225",
    }.get(region, PORT_ORCHARD_ZIP)


def _search_url(region: str, make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> str:
    query = f"{make} {model}".lower().replace(" ", "+")
    return (
        f"https://{region}.craigslist.org/search/cta"
        f"?postal={PORT_ORCHARD_ZIP}"
        f"&search_distance={radius}"
        f"&auto_make_model={query}"
        f"&min_auto_year={min_year}"
        f"&max_auto_miles={max_mileage}"
    )


def _stable_id_from_url(url: str) -> str:
    m = PID_RE.search(url)
    if m:
        return m.group(1)
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _parse_int(s: str | None) -> int | None:
    if not s:
        return None
    s = s.strip()
    if s.lower().endswith("k"):
        try:
            return int(float(s[:-1].strip()) * 1000)
        except ValueError:
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
    if y < 2000 or y > 2030:
        return None
    return y


def _scrape_region_query(page: Page, region: str, make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> list[Listing]:
    url = _search_url(region, make, model, radius=radius, min_year=min_year, max_mileage=max_mileage)
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
        if resp and resp.status >= 400:
            print(f"[craigslist] {region}/{make} {model} -> HTTP {resp.status}", file=sys.stderr)
            return []
    except Exception as e:  # noqa: BLE001
        print(f"[craigslist] {region}/{make} {model} nav failed: {e}", file=sys.stderr)
        return []

    cards = page.query_selector_all("li.cl-static-search-result")
    out: list[Listing] = []
    region_zip = _region_zip_proxy(region)
    distance = miles_from_port_orchard(region_zip)

    for card in cards:
        link_el = card.query_selector("a")
        href = link_el.get_attribute("href") if link_el else None
        if not href:
            continue
        title_el = card.query_selector(".title")
        price_el = card.query_selector(".price")
        loc_el = card.query_selector(".location")
        title = title_el.inner_text().strip() if title_el else ""
        # Craigslist sometimes wraps tokens in asterisks: "*2024* *Tesla*"
        title_clean = title.replace("*", " ").replace("_", " ")
        price_text = price_el.inner_text().strip() if price_el else ""
        location = loc_el.inner_text().strip() if loc_el else None

        year = _parse_year(title_clean)
        price_m = PRICE_RE.search(price_text)
        price = _parse_int(price_m.group(1)) if price_m else None
        # Filter out $0 placeholders ("call for price")
        if price == 0:
            price = None
        mileage_m = MILEAGE_RE.search(title_clean)
        mileage = _parse_int(mileage_m.group(1)) if mileage_m else None

        out.append(
            Listing(
                source=SOURCE,
                source_listing_id=_stable_id_from_url(href),
                url=href,
                make=make,
                model=model,
                trim=None,
                year=year,
                mileage=mileage,
                price=price,
                vin=None,
                location=location or region.title(),
                miles_from_port_orchard=distance,
                thumbnail_url=None,
                raw={
                    "region": region,
                    "title": title,
                    "price_text": price_text,
                },
            )
        )
    return out


def scrape(filters: dict | None = None) -> list[Listing]:
    wl = load_watchlist()
    cfg = wl.get("filters") or {}
    radius = int(cfg.get("radius_miles") or 100)
    min_year = int(cfg.get("min_year") or 2020)
    max_mileage = int(cfg.get("max_mileage") or 80000)

    entries = (wl.get("priority_models") or []) + (wl.get("broad_models") or [])
    listings: list[Listing] = []
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()

    with browser_context() as ctx:
        page = ctx.new_page()
        for region in REGIONS:
            # Warm up cookies once per region. After this navigation,
            # subsequent search-page hits in the same context succeed.
            try:
                page.goto(f"https://{region}.craigslist.org/", timeout=15000)
                page.wait_for_timeout(800)
            except Exception as e:  # noqa: BLE001
                print(f"[craigslist] {region} warmup failed: {e}", file=sys.stderr)
                continue

            for entry in entries:
                make = entry["make"]
                model = entry["model"]
                for l in _scrape_region_query(
                    page, region, make, model,
                    radius=radius, min_year=min_year, max_mileage=max_mileage,
                ):
                    if l.url in seen_urls or l.source_listing_id in seen_ids:
                        continue
                    seen_urls.add(l.url)
                    seen_ids.add(l.source_listing_id)
                    listings.append(l)

    return listings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Craigslist (Playwright) for evwatch.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
