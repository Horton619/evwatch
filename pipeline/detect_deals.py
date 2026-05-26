"""Deal detection.

Phase 5: NEW_PRIORITY + BELOW_MARKET + PRICE_DROP (SPEC §5.2 step 1).
RECURRENT_LISTING is still deferred — it's not load-bearing for the
digest or dashboard.

This module owns the canonical ``deal_tags`` shape persisted on
``evwatch.listings.deal_tags`` (added by migration 002). Shape:

    {
      "NEW_PRIORITY":  {},
      "BELOW_MARKET":  { "pct_below": 0.164, "dollars_below": 5500,
                         "baseline_median": 33500, "comp_count": 31 },
      "PRICE_DROP":    { "previous_price": 35000, "delta": -1500,
                         "delta_pct": -0.043,
                         "observed_at_previous": "2026-05-19T..." }
    }

After every pipeline run we clear ``deal_tags`` for every active listing
(``removed_at is null``) and rewrite from scratch. Tags reflect "what the
latest pipeline thought of this listing", not historical fact.

The CLI ``--json`` flag emits the tagged listings as JSON for the
digest (which still filters to last-24h-relevant tags downstream).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from scrapers._common import bucket_key, get_supabase, load_watchlist

NEW_PRIORITY = "NEW_PRIORITY"
BELOW_MARKET = "BELOW_MARKET"
PRICE_DROP = "PRICE_DROP"
# TODO(SPEC §5.2): RECURRENT_LISTING — landing of a previously-removed
# listing under a new id. Defer; not load-bearing for digests yet.

Tag = str
DealTagPayload = dict[str, Any]
DealTags = dict[Tag, DealTagPayload]
TaggedListing = tuple[dict[str, Any], DealTags]


# ---------------------------------------------------------------------------
# Per-tag predicates
# ---------------------------------------------------------------------------


def _is_priority_match(
    listing: dict[str, Any], priority_models: list[dict]
) -> bool:
    make = (listing.get("make") or "").lower()
    model = (listing.get("model") or "").lower()
    year = listing.get("year")
    if not make or not model:
        return False
    for entry in priority_models:
        if entry["make"].lower() != make or entry["model"].lower() != model:
            continue
        years = entry.get("years")
        if not years or year is None:
            return True
        lo, hi = int(years[0]), int(years[1])
        if lo <= int(year) <= hi:
            return True
    return False


def _below_market_payload(
    listing: dict[str, Any],
    baselines: dict[str, dict[str, Any]],
    *,
    pct_threshold: float,
    min_comps: int,
) -> DealTagPayload | None:
    price = listing.get("price")
    if not price or price <= 0:
        return None
    key = bucket_key(
        listing.get("make"),
        listing.get("model"),
        listing.get("year"),
        listing.get("mileage"),
    )
    if key is None:
        return None
    baseline = baselines.get(key)
    if baseline is None:
        return None
    comp_count = baseline.get("comp_count") or 0
    median = baseline.get("median_price") or 0
    if comp_count < min_comps or median <= 0:
        return None
    pct_below = 1.0 - (price / median)
    if pct_below < pct_threshold:
        return None
    return {
        "pct_below": round(pct_below, 4),
        "dollars_below": int(median - price),
        "baseline_median": int(median),
        "comp_count": int(comp_count),
    }


def _price_drop_payload(
    history_for_listing: list[dict[str, Any]],
    *,
    min_dollars: int,
    min_pct: float,
) -> DealTagPayload | None:
    if len(history_for_listing) < 2:
        return None
    # Sorted desc by observed_at — caller's responsibility.
    latest = history_for_listing[0]
    prev = history_for_listing[1]
    try:
        latest_price = int(latest["price"])
        prev_price = int(prev["price"])
    except (TypeError, ValueError, KeyError):
        return None
    if prev_price <= 0 or latest_price <= 0:
        return None
    delta = latest_price - prev_price  # negative = drop
    if delta >= 0:
        return None
    drop = -delta
    if drop < min_dollars:
        return None
    pct = drop / prev_price
    if pct < min_pct:
        return None
    return {
        "previous_price": prev_price,
        "delta": int(delta),
        "delta_pct": round(-pct, 4),  # match sign convention: negative = drop
        "observed_at_previous": prev.get("observed_at"),
    }


# ---------------------------------------------------------------------------
# Supabase loaders
# ---------------------------------------------------------------------------


def _fetch_active_listings() -> list[dict[str, Any]]:
    sb = get_supabase()
    out: list[dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.schema("evwatch")
            .table("listings")
            .select("*")
            .is_("removed_at", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def _fetch_baselines() -> dict[str, dict[str, Any]]:
    sb = get_supabase()
    resp = sb.schema("evwatch").table("baselines").select("*").execute()
    return {r["model_key"]: r for r in (resp.data or [])}


def _fetch_recent_price_history(window_hours: int) -> dict[str, list[dict[str, Any]]]:
    """Return ``{listing_id: [obs desc by observed_at]}`` for listings that
    have at least one observation in the window. Each list includes the
    most recent observation AND its predecessor (or more) so the drop
    detector can diff.

    We need at least two observations per listing to detect a drop, so we
    pull a wider lookback (90 days) and let the detector filter.
    """
    sb = get_supabase()
    lookback = datetime.now(timezone.utc) - timedelta(days=90)
    out: dict[str, list[dict[str, Any]]] = {}
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.schema("evwatch")
            .table("price_history")
            .select("listing_id, price, observed_at")
            .gte("observed_at", lookback.isoformat())
            .order("observed_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        for r in rows:
            out.setdefault(r["listing_id"], []).append(r)
        if len(rows) < page_size:
            break
        offset += page_size

    # Filter to listings whose latest observation is inside the run window.
    window_start = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return {
        lid: rows
        for lid, rows in out.items()
        if rows and datetime.fromisoformat(rows[0]["observed_at"].replace("Z", "+00:00")) >= window_start
    }


# ---------------------------------------------------------------------------
# Top-level detect()
# ---------------------------------------------------------------------------


def detect(window_hours: int = 24) -> list[TaggedListing]:
    """Tag every active listing. Returns only listings that earned at least
    one tag. The pipeline also calls :func:`write_back` to persist the
    tags to ``evwatch.listings.deal_tags``.
    """
    wl = load_watchlist()
    priority_models = wl.get("priority_models") or []
    thresholds = wl.get("thresholds") or {}
    pct_below = float(thresholds.get("deal_pct_below_baseline") or 0.15)
    min_comps = int(thresholds.get("min_baseline_comps") or 6)
    min_drop_dollars = int(thresholds.get("price_drop_min_dollars") or 500)
    min_drop_pct = float(thresholds.get("price_drop_min_pct") or 0.03)

    listings = _fetch_active_listings()
    baselines = _fetch_baselines()
    recent_history = _fetch_recent_price_history(window_hours=window_hours)

    print(
        f"[detect_deals] {len(listings)} active listings, {len(baselines)} baselines, "
        f"{len(recent_history)} listings with recent price activity"
    )

    cutoff_new = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

    tagged: list[TaggedListing] = []
    for row in listings:
        tags: DealTags = {}

        # NEW_PRIORITY: priority watchlist match AND newly seen.
        if (
            row.get("first_seen_at")
            and row["first_seen_at"] >= cutoff_new
            and _is_priority_match(row, priority_models)
        ):
            tags[NEW_PRIORITY] = {}

        # BELOW_MARKET: always compute for any active listing. Even old
        # listings can newly qualify if baselines shifted.
        bm = _below_market_payload(
            row, baselines, pct_threshold=pct_below, min_comps=min_comps,
        )
        if bm is not None:
            tags[BELOW_MARKET] = bm

        # PRICE_DROP: only if there's recent price activity for this listing.
        history = recent_history.get(row["id"])
        if history:
            pd = _price_drop_payload(
                history, min_dollars=min_drop_dollars, min_pct=min_drop_pct,
            )
            if pd is not None:
                tags[PRICE_DROP] = pd

        if tags:
            tagged.append((row, tags))

    return tagged


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def write_back(tagged: list[TaggedListing]) -> dict[str, int]:
    """Clear ``deal_tags`` on every active listing, then write tags onto
    the subset that earned them.

    Two passes:
      1. Bulk null-out deal_tags for all active listings (one PATCH).
      2. Per-listing PATCH with the new tags. We can't batch distinct
         JSONB values in a single PostgREST call.
    """
    sb = get_supabase()

    # Pass 1 — clear.
    sb.schema("evwatch").table("listings").update({"deal_tags": None}).is_(
        "removed_at", "null"
    ).execute()

    # Pass 2 — write.
    written = 0
    for row, tags in tagged:
        sb.schema("evwatch").table("listings").update({"deal_tags": tags}).eq(
            "id", row["id"]
        ).execute()
        written += 1

    return {"cleared_all_active": 1, "tagged_written": written}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect deals + persist deal_tags.")
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Look at NEW_PRIORITY hits + PRICE_DROP events in the last N hours.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Detect but don't write deal_tags back to listings.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print tagged listings as JSON to stdout (used by tests).",
    )
    args = parser.parse_args(argv)

    tagged = detect(window_hours=args.window_hours)

    counts: dict[str, int] = {}
    for _, tags in tagged:
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
    print(f"[detect_deals] {len(tagged)} tagged listings in last {args.window_hours}h")
    for tag in (NEW_PRIORITY, BELOW_MARKET, PRICE_DROP):
        print(f"  {tag}: {counts.get(tag, 0)}")

    if not args.no_write:
        summary = write_back(tagged)
        print(f"[detect_deals] persistence: {summary}")

    if args.json:
        json.dump(
            [{**row, "_tags": tags} for row, tags in tagged],
            sys.stdout,
            default=str,
            indent=2,
        )
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
