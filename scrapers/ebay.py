"""eBay Motors scraper.

Pulls used EV listings from the eBay Browse API (free tier: 5000 calls/day).
Runs from GitHub Actions on the daily cron, and on-demand from the Mac app.

Auth: OAuth2 client-credentials. We need both ``EBAY_APP_ID`` (client id)
and ``EBAY_CERT_ID`` (client secret) — see SPEC §7. The bearer token is
cached for the process lifetime.

Phase 2 limitations to be aware of:
- Browse API ``item_summary/search`` doesn't return rich aspects (year,
  mileage, VIN) — only ``title``. We parse year/mileage from the title via
  regex, then for any listing that matches a watchlist priority model we
  follow up with one ``get_item`` call to get authoritative mileage + VIN.
- eBay's location filters don't cleanly express "within X miles of ZIP" for
  motors, so we pull everything in the US matching the keyword and
  category, then drop anything > ``radius_miles`` from Port Orchard
  client-side using ``miles_from_port_orchard``.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

from scrapers._common import (
    Listing,
    _env,
    load_watchlist,
    miles_from_port_orchard,
    record_source_run,
    upsert_listings,
)

SOURCE = "ebay"

# eBay Motors > Cars & Trucks. https://www.ebay.com/b/Cars-Trucks/6001
CATEGORY_CARS_TRUCKS = "6001"

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"
BROWSE_SCOPE = "https://api.ebay.com/oauth/api_scope"

# eBay Browse API hard-caps `limit` at 200 and `offset` + `limit` at 10_000.
PAGE_LIMIT = 200
MAX_OFFSET = 10_000

# Salvage / parts vehicles get filtered out by title match. eBay's
# `conditions` filter alone isn't reliable — sellers list salvage cars as
# "Used".
TITLE_DENY_RE = re.compile(
    r"\b(salvage|rebuilt|flood|hail|wrecked|parts only|for parts|"
    r"non[\s-]*running|no title|bill of sale only|theft recovery)\b",
    re.IGNORECASE,
)

# "2023" or "2023" appearing near start of title; matched as the first
# 19xx/20xx token to avoid hitting trim names like "Tesla Model 3 2024 update".
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")

# "55,000 mi", "55k miles", "55,000 miles", "55000 mi"
MILEAGE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[,\s]\d{3})+|\d+(?:\.\d+)?\s*[kK]|\d{4,6})"
    r"\s*(?:mi|miles|mile)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------


@dataclass
class _Token:
    value: str
    expires_at: float  # epoch seconds


_token: _Token | None = None


def _get_token(client: httpx.Client) -> str:
    global _token
    if _token and _token.expires_at > time.time() + 60:
        return _token.value

    app_id = _env("EBAY_APP_ID")
    cert_id = _env("EBAY_CERT_ID")
    basic = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
    resp = client.post(
        OAUTH_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": BROWSE_SCOPE},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    _token = _Token(
        value=payload["access_token"],
        expires_at=time.time() + int(payload.get("expires_in", 7200)),
    )
    return _token.value


# ---------------------------------------------------------------------------
# Title parsing
# ---------------------------------------------------------------------------


def parse_year(title: str) -> int | None:
    m = YEAR_RE.search(title)
    if not m:
        return None
    y = int(m.group(1))
    # Reject implausible vehicle years for an EV monitor (Tesla Model S
    # started 2012; older listings here are almost certainly false matches).
    if y < 2000 or y > 2030:
        return None
    return y


def parse_mileage(title: str) -> int | None:
    m = MILEAGE_RE.search(title)
    if not m:
        return None
    raw = m.group("num").strip()
    if raw.lower().endswith("k"):
        try:
            return int(float(raw[:-1].strip()) * 1000)
        except ValueError:
            return None
    digits = re.sub(r"[,\s]", "", raw)
    try:
        return int(digits)
    except ValueError:
        return None


def title_is_salvage(title: str) -> bool:
    return bool(TITLE_DENY_RE.search(title))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _search_one(
    client: httpx.Client, token: str, query: str
) -> Iterable[dict[str, Any]]:
    """Yield raw ``itemSummary`` dicts for one (make, model) query."""
    offset = 0
    while offset < MAX_OFFSET:
        params: dict[str, str | int] = {
            "q": query,
            "category_ids": CATEGORY_CARS_TRUCKS,
            "filter": (
                "conditions:{USED|CERTIFIED_REFURBISHED},"
                "itemLocationCountry:US"
            ),
            "limit": PAGE_LIMIT,
            "offset": offset,
        }
        resp = client.get(
            f"{BROWSE_BASE}/item_summary/search",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            params=params,
            timeout=30,
        )
        # 204 = no results; treat as empty page.
        if resp.status_code == 204:
            return
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("itemSummaries") or []
        if not items:
            return
        for item in items:
            yield item
        total = int(payload.get("total", 0))
        offset += PAGE_LIMIT
        if offset >= total:
            return


def _fetch_item_detail(
    client: httpx.Client, token: str, item_id: str
) -> dict[str, Any] | None:
    """Authoritative aspect lookup via ``get_item``. Used for priority hits."""
    resp = client.get(
        f"{BROWSE_BASE}/item/{item_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        },
        timeout=30,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _aspect(detail: dict[str, Any], name: str) -> str | None:
    for a in detail.get("localizedAspects") or []:
        if a.get("name", "").lower() == name.lower():
            return a.get("value")
    return None


def _is_priority(make: str | None, model: str | None, year: int | None, wl: dict) -> bool:
    if not make or not model:
        return False
    mk, md = make.lower(), model.lower()
    for entry in wl.get("priority_models") or []:
        if entry["make"].lower() == mk and entry["model"].lower() == md:
            years = entry.get("years")
            if not years or year is None:
                return True
            lo, hi = int(years[0]), int(years[1])
            return lo <= year <= hi
    return False


def _matches_watchlist(make: str | None, model: str | None, wl: dict) -> bool:
    if not make or not model:
        return False
    mk, md = make.lower(), model.lower()
    for entry in (wl.get("priority_models") or []) + (wl.get("broad_models") or []):
        if entry["make"].lower() == mk and entry["model"].lower() == md:
            return True
    return False


def _query_for(entry: dict) -> str:
    return f'{entry["make"]} {entry["model"]}'


def _itemlocation_to_str(loc: dict[str, Any] | None) -> str | None:
    if not loc:
        return None
    bits = [loc.get("city"), loc.get("stateOrProvince"), loc.get("postalCode")]
    return ", ".join(b for b in bits if b)


# ---------------------------------------------------------------------------
# Top-level scrape
# ---------------------------------------------------------------------------


def scrape(filters: dict | None = None) -> list[Listing]:
    """Run a full eBay scrape against every watchlist entry.

    ``filters`` is currently ignored — we pull config from ``watchlist.yml``
    directly. The argument exists to keep the signature consistent across
    sources (SPEC §5.1).
    """
    wl = load_watchlist()
    cfg_filters = wl.get("filters") or {}
    radius = int(cfg_filters.get("radius_miles") or 100)
    max_mileage = cfg_filters.get("max_mileage")
    min_year = cfg_filters.get("min_year")

    entries = (wl.get("priority_models") or []) + (wl.get("broad_models") or [])

    listings: list[Listing] = []
    seen_ids: set[str] = set()

    with httpx.Client() as client:
        token = _get_token(client)

        for entry in entries:
            query = _query_for(entry)
            try:
                items = list(_search_one(client, token, query))
            except httpx.HTTPError as e:
                # One bad query shouldn't kill the whole run.
                print(f"[ebay] search failed for {query!r}: {e}", file=sys.stderr)
                continue

            for item in items:
                item_id = item.get("itemId")
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                title = item.get("title") or ""
                if title_is_salvage(title):
                    continue

                year = parse_year(title)
                mileage = parse_mileage(title)
                make = entry["make"]
                model = entry["model"]

                if min_year and year and year < int(min_year):
                    continue
                if max_mileage and mileage and mileage > int(max_mileage):
                    continue

                price_obj = item.get("price") or {}
                try:
                    price = int(float(price_obj.get("value"))) if price_obj.get("value") else None
                except (TypeError, ValueError):
                    price = None

                loc = item.get("itemLocation") or {}
                postal = loc.get("postalCode")
                distance = miles_from_port_orchard(postal)
                # Drop anything outside the radius. Keep null-distance items
                # (zip unknown to our centroid table) — they're rare and
                # better surfaced than silently dropped.
                if distance is not None and distance > radius:
                    continue

                # Authoritative aspects for priority hits only — cheap.
                vin: str | None = None
                trim: str | None = None
                if _is_priority(make, model, year, wl):
                    try:
                        detail = _fetch_item_detail(client, token, item_id)
                    except httpx.HTTPError as e:
                        print(f"[ebay] get_item {item_id} failed: {e}", file=sys.stderr)
                        detail = None
                    if detail:
                        vin = _aspect(detail, "VIN")
                        trim = _aspect(detail, "Trim")
                        detail_mileage = _aspect(detail, "Mileage")
                        if detail_mileage:
                            parsed = parse_mileage(detail_mileage + " mi")
                            if parsed is not None:
                                mileage = parsed
                        detail_year = _aspect(detail, "Year")
                        if detail_year and not year:
                            try:
                                year = int(detail_year)
                            except ValueError:
                                pass

                # Final guard: matches a watchlist entry. (We searched by
                # entry, so this should always pass unless the title was
                # wildly off — but cheap to assert.)
                if not _matches_watchlist(make, model, wl):
                    continue

                listings.append(
                    Listing(
                        source=SOURCE,
                        source_listing_id=str(item_id),
                        url=item.get("itemWebUrl") or "",
                        make=make,
                        model=model,
                        trim=trim,
                        year=year,
                        mileage=mileage,
                        price=price,
                        vin=vin,
                        location=_itemlocation_to_str(loc),
                        miles_from_port_orchard=distance,
                        thumbnail_url=(item.get("image") or {}).get("imageUrl"),
                        raw=item,
                    )
                )

    return listings


# ---------------------------------------------------------------------------
# CLI entry point — used by GHA and local runs
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape eBay Motors for evwatch.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and print a summary; don't write to Supabase.",
    )
    args = parser.parse_args(argv)

    started = time.time()
    error: str | None = None
    listings: list[Listing] = []
    try:
        listings = scrape({})
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        print(f"[ebay] scrape failed: {error}", file=sys.stderr)

    duration_ms = int((time.time() - started) * 1000)
    print(f"[ebay] scraped {len(listings)} listings in {duration_ms} ms")

    if args.dry_run:
        for l in listings[:10]:
            print(
                f"  {l.year or '----'} {l.make} {l.model} | "
                f"${l.price or '?':>6} | {l.mileage or '?'} mi | "
                f"{l.miles_from_port_orchard or '?'}mi away | {l.url}"
            )
        if len(listings) > 10:
            print(f"  ... ({len(listings) - 10} more)")
        return 0 if error is None else 1

    if listings:
        summary = upsert_listings(listings)
        print(
            f"[ebay] upsert: inserted={summary['inserted']} "
            f"updated={summary['updated']} price_changes={summary['price_changes']}"
        )
    record_source_run(SOURCE, duration_ms, len(listings), error=error)
    return 0 if error is None else 1


if __name__ == "__main__":
    sys.exit(main())
