"""Cars.com scraper (Mac-only, httpx-first with Playwright fallback).

Cars.com is less aggressive than CarGurus/AutoTrader — plain httpx with a
browser-shaped User-Agent often succeeds. Only fall back to Playwright if
the httpx attempt returns a Cloudflare interstitial or an empty results
shell.

Mac-only — guarded by EVWATCH_ALLOW_MAC_ONLY_SCRAPERS.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from scrapers._common import (
    HTTP_USER_AGENT,
    Listing,
    PORT_ORCHARD_ZIP,
    load_watchlist,
    miles_from_port_orchard,
    run_scraper,
)
from scrapers._playwright import browser_context

SOURCE = "cars_dot_com"

BASE_URL = "https://www.cars.com/shopping/results/"

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILEAGE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:mi|miles)\b", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d{4,6})")
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")

# Cars.com makes their browser-shaped UA detection mild; the standard
# evwatch UA gets through often enough that we try it first.
HEADERS = {
    "User-Agent": HTTP_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _ensure_mac_only() -> None:
    if os.environ.get("EVWATCH_ALLOW_MAC_ONLY_SCRAPERS") != "1":
        raise SystemExit(
            "[cars_dot_com] refusing to run without EVWATCH_ALLOW_MAC_ONLY_SCRAPERS=1."
        )


def _search_params(make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> dict[str, Any]:
    return {
        "makes[]": make.lower().replace(" ", "_"),
        "models[]": f"{make.lower()}-{model.lower().replace(' ', '_').replace('-', '_')}",
        "zip": PORT_ORCHARD_ZIP,
        "maximum_distance": radius,
        "year_min": min_year,
        "mileage_max": max_mileage,
        "stock_type": "used",
        "sort": "best_match_desc",
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
    return y if 2000 <= y <= 2030 else None


def _stable_id_from_url(url: str) -> str:
    # Cars.com listing URLs contain a numeric vehicle id like
    # /vehicledetail/abcd-1234567890/.
    m = re.search(r"/(\d{8,})/?", url)
    if m:
        return m.group(1)
    vin_m = VIN_RE.search(url)
    if vin_m:
        return vin_m.group(0)
    return url[-40:]


def _looks_blocked(html: str) -> bool:
    """Heuristic: Cloudflare or empty-shell response."""
    if len(html) < 5_000:
        return True
    blocks = ("just a moment", "attention required", "ray id", "captcha")
    lower = html[:8000].lower()
    return any(b in lower for b in blocks)


def _extract_cards(html: str, expected_make: str, expected_model: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    for card in soup.find_all("div", class_=re.compile(r"vehicle-card")):
        if not isinstance(card, Tag):
            continue
        link = card.find("a", href=True)
        if not link:
            continue
        url = link["href"]
        if not isinstance(url, str):
            continue
        if not url.startswith("http"):
            url = f"https://www.cars.com{url}"

        text = card.get_text(" ", strip=True)
        title_el = card.find(class_=re.compile(r"title"))
        title = title_el.get_text(strip=True) if title_el else text[:120]
        if expected_make.lower() not in title.lower() and expected_model.lower() not in title.lower():
            continue

        price_m = PRICE_RE.search(text)
        mileage_m = MILEAGE_RE.search(text)
        vin_m = VIN_RE.search(text + " " + url)

        img = card.find("img")
        thumbnail = None
        if img and isinstance(img, Tag):
            for attr in ("data-src", "src"):
                v = img.get(attr)
                if isinstance(v, str) and v.startswith("http"):
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
                raw={"title": title, "card_text": text[:1000]},
            )
        )
    return out


def _fetch_via_httpx(client: httpx.Client, make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> str | None:
    try:
        resp = client.get(
            BASE_URL,
            params=_search_params(make, model, radius=radius, min_year=min_year, max_mileage=max_mileage),
            headers=HEADERS,
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        print(f"[cars_dot_com] httpx {make} {model}: {e}", file=sys.stderr)
        return None


def _fetch_via_playwright(make: str, model: str, *, radius: int, min_year: int, max_mileage: int) -> str | None:
    params = _search_params(make, model, radius=radius, min_year=min_year, max_mileage=max_mileage)
    qs = "&".join(f"{k}={str(v).replace(' ', '+')}" for k, v in params.items())
    url = f"{BASE_URL}?{qs}"
    try:
        with browser_context() as ctx:
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector(".vehicle-card", timeout=15000)
            return page.content()
    except Exception as e:  # noqa: BLE001
        print(f"[cars_dot_com] playwright {make} {model}: {e}", file=sys.stderr)
        return None


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

    with httpx.Client() as client:
        for entry in entries:
            make = entry["make"]
            model = entry["model"]

            html = _fetch_via_httpx(
                client, make, model,
                radius=radius, min_year=min_year, max_mileage=max_mileage,
            )
            if html is None or _looks_blocked(html):
                print(f"[cars_dot_com] {make} {model}: httpx blocked, escalating to Playwright", file=sys.stderr)
                html = _fetch_via_playwright(
                    make, model,
                    radius=radius, min_year=min_year, max_mileage=max_mileage,
                )
            if html is None:
                continue

            for l in _extract_cards(html, make, model):
                if l.source_listing_id in seen:
                    continue
                seen.add(l.source_listing_id)
                listings.append(l)

    return listings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Cars.com (Mac-only).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
