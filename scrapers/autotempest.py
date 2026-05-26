"""AutoTempest scraper (Playwright).

AutoTempest's results page is a JS-rendered single-page app that
aggregates listings from CarGurus, AutoTrader, Cars.com, eBay, smaller
dealer sites, and various ad networks. ``httpx`` gets back an empty
template; Playwright renders the real results.

One headless Chromium navigation per (make, model). Each card text block
is line-formatted:

    TITLE
    $PRICE
    MILEAGE mi.
    N days ago
    LOCATION
    DEALER
    ...

We extract from that text and from the card's outbound link href.
Sponsored cards are tolerated — title-vs-watchlist matching downstream
filters them out (an ad for a Corvette won't match "Tesla Model Y").
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page

from scrapers._common import (
    Listing,
    PORT_ORCHARD_ZIP,
    load_watchlist,
    miles_from_port_orchard,
    run_scraper,
)
from scrapers._playwright import browser_context

SOURCE = "autotempest"

BASE_URL = "https://www.autotempest.com/results"

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILEAGE_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*mi\.?",
    re.IGNORECASE,
)
PRICE_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d{4,6})")
# Standard 17-char VIN. AutoTempest embeds it in ad-redirect URLs and
# sometimes in the image filename. Matches uppercase letters + digits
# excluding I, O, Q.
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")


def _params(make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> dict[str, Any]:
    # AutoTempest's structured make/model params reject names containing
    # spaces or dashes ("model y" / "mustang mach-e" both fail with a
    # validator error). The free-text `q=` param accepts anything.
    return {
        "q": f"{make} {model}",
        "zip": PORT_ORCHARD_ZIP,
        "radius": radius,
        "minyear": min_year,
        "maxmiles": max_mileage,
    }


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
    if y < 2000 or y > 2030:
        return None
    return y


def _stable_id_from_url(url: str) -> str:
    # Prefer the VIN from the redirect URL if present — stable across runs
    # even if AutoTempest's ad-tracking params shift.
    qs = parse_qs(urlparse(url).query)
    if "ad" in qs and qs["ad"] and VIN_RE.fullmatch(qs["ad"][0]):
        return qs["ad"][0]
    if m := VIN_RE.search(url):
        return m.group(0)
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _original_source_from_url(url: str) -> str | None:
    for host, name in (
        ("cargurus.com",   "cargurus"),
        ("autotrader.com", "autotrader"),
        ("cars.com",       "cars_dot_com"),
        ("ebay.com",       "ebay"),
        ("carvana.com",    "carvana"),
        ("carmax.com",     "carmax"),
        ("craigslist.org", "craigslist"),
        ("lotlinx.com",    "lotlinx"),
    ):
        if host in url:
            return name
    return None


def _extract_thumbnail(card_html: str) -> str | None:
    m = re.search(r'data-img="([^"]+)"', card_html)
    return m.group(1) if m else None


def _scrape_results_page(page: Page, expected_make: str, expected_model: str) -> list[Listing]:
    """Pull listings off the currently-loaded results page."""
    try:
        page.wait_for_selector(".search-result", timeout=10000)
    except Exception as e:  # noqa: BLE001 — selector timeout is the common case
        print(f"[autotempest] no .search-result rendered: {e}", file=sys.stderr)
        return []

    out: list[Listing] = []
    for card in page.query_selector_all(".search-result"):
        title_el = card.query_selector(".listing-title a")
        title = (title_el.inner_text().strip() if title_el else "")
        if expected_make.lower() not in title.lower() and expected_model.lower() not in title.lower():
            # Sponsored/ad card for an unrelated vehicle. Skip.
            continue

        link_el = card.query_selector("a.listing-link")
        out_url = link_el.get_attribute("href") if link_el else None
        if not out_url:
            continue

        text = card.inner_text()
        year = _parse_year(title)
        price_m = PRICE_RE.search(text)
        mileage_m = MILEAGE_RE.search(text)
        price = _parse_int(price_m.group(1)) if price_m else None
        mileage = _parse_int(mileage_m.group(1)) if mileage_m else None

        # Location is usually the line right after the days-ago line. Best-effort.
        location: str | None = None
        for line in text.splitlines():
            line = line.strip()
            if "," in line and len(line) < 60 and re.search(r"[A-Z]{2}\b", line):
                location = line
                break

        vin_m = VIN_RE.search(out_url)
        vin = vin_m.group(0) if vin_m else None

        card_html = card.inner_html()
        thumbnail = _extract_thumbnail(card_html)

        out.append(
            Listing(
                source=SOURCE,
                source_listing_id=_stable_id_from_url(out_url),
                url=out_url,
                make=expected_make,
                model=expected_model,
                trim=None,
                year=year,
                mileage=mileage,
                price=price,
                vin=vin,
                location=location,
                # Without a zip on the card, we can't compute distance accurately.
                # AutoTempest already filtered server-side by our radius param.
                miles_from_port_orchard=None,
                thumbnail_url=thumbnail,
                raw={
                    "title": title,
                    "card_text": text[:1000],
                    "original_source": _original_source_from_url(out_url),
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
    seen: set[str] = set()

    with browser_context() as ctx:
        page = ctx.new_page()
        for entry in entries:
            make = entry["make"]
            model = entry["model"]
            params = _params(make, model, radius=radius, min_year=min_year, max_mileage=max_mileage)
            qs = "&".join(f"{k}={str(v).replace(' ', '+')}" for k, v in params.items())
            url = f"{BASE_URL}?{qs}"
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                if resp and resp.status >= 400:
                    print(f"[autotempest] {make} {model} -> HTTP {resp.status}", file=sys.stderr)
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[autotempest] {make} {model} nav failed: {e}", file=sys.stderr)
                continue

            for l in _scrape_results_page(page, make, model):
                if l.source_listing_id in seen:
                    continue
                seen.add(l.source_listing_id)
                listings.append(l)

    return listings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape AutoTempest (Playwright) for evwatch.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
