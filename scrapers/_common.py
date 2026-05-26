"""Shared scraper utilities.

Defines the canonical ``Listing`` dataclass, the Supabase upsert helper that
every scraper uses, and a handful of small helpers used across modules:

- ``get_supabase()`` — service-role client cached for the process lifetime
- ``load_watchlist()`` — parses ``config/watchlist.yml``
- ``miles_from_port_orchard(zip_code)`` — zip → great-circle distance,
  using the bundled ``scrapers/data/us_zips_pnw.csv`` (built by
  ``scripts/build_zip_csv.py``)
- ``upsert_listings(...)`` — writes to ``evwatch.listings`` and appends a
  fresh ``evwatch.price_history`` row whenever a listing's price changed
- ``record_source_run(...)`` — one row per scraper invocation

All Supabase writes use the **service-role** key, which bypasses RLS.
"""

from __future__ import annotations

import csv
import math
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv
from supabase import Client, create_client

# Load .env once at import time. In GitHub Actions the env vars come from
# secrets and this is a no-op.
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = REPO_ROOT / "config" / "watchlist.yml"
ZIP_CSV_PATH = REPO_ROOT / "scrapers" / "data" / "us_zips_pnw.csv"

PORT_ORCHARD_ZIP = "98366"

# Identifies us on HTML / RSS sources that don't take API keys. Friendly and
# attributable so a site operator can find us if they need to.
HTTP_USER_AGENT = "evwatch/0.1 (+https://github.com/Horton619/evwatch)"


# ---------------------------------------------------------------------------
# Listing dataclass
# ---------------------------------------------------------------------------


@dataclass
class Listing:
    """One vehicle listing, mirroring the ``evwatch.listings`` schema."""

    source: str
    source_listing_id: str
    url: str
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    year: int | None = None
    mileage: int | None = None
    price: int | None = None
    vin: str | None = None
    location: str | None = None
    miles_from_port_orchard: int | None = None
    thumbnail_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_db_row(self) -> dict[str, Any]:
        """Project to the keys Supabase expects for an upsert."""
        row = asdict(self)
        # `first_seen_at` / `last_seen_at` use DB defaults on insert;
        # on update we set last_seen_at explicitly.
        return row


# ---------------------------------------------------------------------------
# Env / Supabase
# ---------------------------------------------------------------------------


def _env(name: str, required: bool = True) -> str:
    val = os.environ.get(name, "").strip()
    if required and not val:
        raise RuntimeError(
            f"{name} is required. Set it in .env (local) or GHA secrets (CI). "
            "See .env.example and SPEC §7."
        )
    return val


@cache
def get_supabase() -> Client:
    """Service-role Supabase client (bypasses RLS — write-capable)."""
    return create_client(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


@cache
def load_watchlist() -> dict[str, Any]:
    """Parse ``config/watchlist.yml`` into a plain dict."""
    with WATCHLIST_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Zip-distance helpers
# ---------------------------------------------------------------------------


@cache
def _zip_centroids() -> dict[str, tuple[float, float]]:
    """Map of 5-digit zip → (lat, lon), loaded from the bundled CSV."""
    out: dict[str, tuple[float, float]] = {}
    if not ZIP_CSV_PATH.exists():
        # Soft failure: scrapers will report null distances rather than crash.
        # Run scripts/build_zip_csv.py to populate.
        return out
    with ZIP_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                out[row["zip"]] = (float(row["lat"]), float(row["lon"]))
            except (ValueError, KeyError):
                continue
    return out


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_miles = 3958.7613
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r_miles * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Baseline bucketing (SPEC §5.3)
# ---------------------------------------------------------------------------

# Mileage buckets — slug → (lo, hi) where hi is exclusive. 60-80k is
# double-wide on purpose: most listings cap at the watchlist's 80k limit so
# we'd otherwise have a thin 60-70k bucket.
_MILEAGE_BUCKETS: list[tuple[str, int, int]] = [
    ("lt10k",   0,      10_000),
    ("10k-20k", 10_000, 20_000),
    ("20k-30k", 20_000, 30_000),
    ("30k-40k", 30_000, 40_000),
    ("40k-50k", 40_000, 50_000),
    ("50k-60k", 50_000, 60_000),
    ("60k-80k", 60_000, 80_000),
    ("80kplus", 80_000, 10**9),
]

# v1 region. SPEC §6 accepts mixed-source baselines under a single region;
# we keep the field in the key so a future split into ("pnw", "national")
# doesn't require a schema change.
DEFAULT_REGION = "pnw"


def _slug(s: str) -> str:
    """Lowercase, spaces+slashes → hyphens, strip non [a-z0-9-]."""
    s = s.strip().lower()
    s = re.sub(r"[\s/]+", "-", s)
    return re.sub(r"[^a-z0-9-]", "", s)


def mileage_bucket(mileage: int | None) -> str | None:
    if mileage is None or mileage < 0:
        return None
    for slug, lo, hi in _MILEAGE_BUCKETS:
        if lo <= mileage < hi:
            return slug
    return None  # unreachable given the catch-all 80kplus


def bucket_key(
    make: str | None,
    model: str | None,
    year: int | None,
    mileage: int | None,
    region: str = DEFAULT_REGION,
) -> str | None:
    """Build the model_key used by ``evwatch.baselines``.

    Returns ``None`` when the listing can't be bucketed (missing year,
    mileage, make, or model). Callers should skip baseline contribution
    and BELOW_MARKET evaluation in that case.
    """
    if not make or not model or year is None:
        return None
    mb = mileage_bucket(mileage)
    if mb is None:
        return None
    return f"{_slug(make)}:{_slug(model)}:{year}:{mb}:{region}"


def miles_from_port_orchard(zip_code: str | None) -> int | None:
    """Great-circle distance from Port Orchard, WA to ``zip_code`` in miles.

    Returns ``None`` if the zip isn't in the bundled centroid table (e.g. a
    Canadian postal code or a US zip outside the WA/OR/ID/MT/CA/NV bundle).
    """
    if not zip_code:
        return None
    zip5 = zip_code.strip()[:5]
    centroids = _zip_centroids()
    origin = centroids.get(PORT_ORCHARD_ZIP)
    target = centroids.get(zip5)
    if not origin or not target:
        return None
    return round(_haversine_miles(origin[0], origin[1], target[0], target[1]))


# ---------------------------------------------------------------------------
# Supabase writes
# ---------------------------------------------------------------------------


def upsert_listings(listings: list[Listing]) -> dict[str, int]:
    """Upsert ``listings`` keyed on ``(source, source_listing_id)``.

    For every listing whose price changed (or is new), append a row to
    ``evwatch.price_history`` with ``source_kind = 'live'``. Returns a small
    ``{inserted, updated, price_changes}`` summary for run logging.
    """
    if not listings:
        return {"inserted": 0, "updated": 0, "price_changes": 0}

    sb = get_supabase()
    table = sb.schema("evwatch").table("listings")

    # Look up existing rows to detect price changes + insert vs update.
    keys = [(l.source, l.source_listing_id) for l in listings]
    sources = list({k[0] for k in keys})
    ids = [k[1] for k in keys]
    existing_resp = (
        table.select("id, source, source_listing_id, price")
        .in_("source", sources)
        .in_("source_listing_id", ids)
        .execute()
    )
    existing = {
        (r["source"], r["source_listing_id"]): r for r in (existing_resp.data or [])
    }

    now = datetime.now(timezone.utc).isoformat()
    upsert_rows: list[dict[str, Any]] = []
    for l in listings:
        row = l.to_db_row()
        row["last_seen_at"] = now
        # Don't try to send first_seen_at — let the DB default fill it on insert
        # and leave it alone on update.
        upsert_rows.append(row)

    upserted = table.upsert(
        upsert_rows, on_conflict="source,source_listing_id"
    ).execute()

    inserted = updated = 0
    price_history_rows: list[dict[str, Any]] = []
    by_key = {(r["source"], r["source_listing_id"]): r for r in (upserted.data or [])}
    for l in listings:
        prior = existing.get((l.source, l.source_listing_id))
        upserted_row = by_key.get((l.source, l.source_listing_id))
        if upserted_row is None:
            continue
        listing_id = upserted_row["id"]
        if prior is None:
            inserted += 1
            if l.price is not None:
                price_history_rows.append(
                    {
                        "listing_id": listing_id,
                        "observed_at": now,
                        "price": int(l.price),
                        "source_kind": "live",
                    }
                )
        else:
            updated += 1
            if l.price is not None and prior.get("price") != l.price:
                price_history_rows.append(
                    {
                        "listing_id": listing_id,
                        "observed_at": now,
                        "price": int(l.price),
                        "source_kind": "live",
                    }
                )

    price_changes = len(price_history_rows)
    if price_history_rows:
        sb.schema("evwatch").table("price_history").upsert(
            price_history_rows, on_conflict="listing_id,observed_at"
        ).execute()

    return {"inserted": inserted, "updated": updated, "price_changes": price_changes}


def record_source_run(
    source: str,
    duration_ms: int,
    listings_found: int,
    error: str | None = None,
) -> None:
    """Log one ``evwatch.source_runs`` row."""
    get_supabase().schema("evwatch").table("source_runs").insert(
        {
            "source": source,
            "duration_ms": int(duration_ms),
            "listings_found": int(listings_found),
            "error": error,
        }
    ).execute()


# ---------------------------------------------------------------------------
# Standard CLI runner for individual scrapers
# ---------------------------------------------------------------------------


def run_scraper(
    source: str,
    scrape_fn: Callable[[dict], list[Listing]],
    *,
    dry_run: bool = False,
    filters: dict | None = None,
) -> int:
    """Time, run, upsert, and log one scraper. Returns process exit code.

    Each ``scrapers/<name>.py:main`` boils down to::

        def main(argv=None):
            args = parser.parse_args(argv)
            return run_scraper(SOURCE, scrape, dry_run=args.dry_run)
    """
    started = time.time()
    error: str | None = None
    listings: list[Listing] = []
    try:
        listings = scrape_fn(filters or {})
    except Exception as e:  # noqa: BLE001 — top-level scraper boundary
        error = f"{type(e).__name__}: {e}"
        print(f"[{source}] scrape failed: {error}", file=sys.stderr)

    duration_ms = int((time.time() - started) * 1000)
    print(f"[{source}] scraped {len(listings)} listings in {duration_ms} ms")

    if dry_run:
        for l in listings[:10]:
            print(
                f"  {l.year or '----'} {l.make} {l.model} | "
                f"${l.price or '?':>6} | {l.mileage or '?'} mi | "
                f"{l.miles_from_port_orchard if l.miles_from_port_orchard is not None else '?'}mi away | {l.url}"
            )
        if len(listings) > 10:
            print(f"  ... ({len(listings) - 10} more)")
        return 0 if error is None else 1

    if listings:
        summary = upsert_listings(listings)
        print(
            f"[{source}] upsert: inserted={summary['inserted']} "
            f"updated={summary['updated']} price_changes={summary['price_changes']}"
        )
    try:
        record_source_run(source, duration_ms, len(listings), error=error)
    except Exception as e:  # noqa: BLE001
        print(f"[{source}] could not record source_run: {e}", file=sys.stderr)
    return 0 if error is None else 1
