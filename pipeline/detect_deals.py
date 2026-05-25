"""Deal detection.

Phase 2: only the ``NEW_PRIORITY`` tag is implemented. ``PRICE_DROP``,
``BELOW_MARKET``, and ``RECURRENT_LISTING`` land in later phases — see
SPEC §5.2 step 1 and §9 steps 9 onward.

This module is import-friendly. ``send_digest`` calls :func:`detect` to get
the tagged listings; running this file directly just prints a summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from scrapers._common import get_supabase, load_watchlist

Tag = str
TaggedListing = tuple[dict[str, Any], list[Tag]]

NEW_PRIORITY = "NEW_PRIORITY"
# TODO(SPEC §5.2): implement PRICE_DROP, BELOW_MARKET, RECURRENT_LISTING in
# later phases. PRICE_DROP needs price_history join + threshold comparison;
# BELOW_MARKET needs baselines (phase 5); RECURRENT_LISTING needs
# re-appearance detection across runs.


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


def detect(window_hours: int = 24) -> list[TaggedListing]:
    """Return ``[(listing_row, tags), ...]`` for listings first seen in the
    last ``window_hours``.

    A listing makes the cut if it carries at least one tag. In Phase 2 the
    only tag emitted is ``NEW_PRIORITY``.
    """
    wl = load_watchlist()
    priority_models = wl.get("priority_models") or []

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    resp = (
        get_supabase()
        .schema("evwatch")
        .table("listings")
        .select("*")
        .gte("first_seen_at", cutoff)
        .execute()
    )
    candidates = resp.data or []

    out: list[TaggedListing] = []
    for row in candidates:
        tags: list[Tag] = []
        if _is_priority_match(row, priority_models):
            tags.append(NEW_PRIORITY)
        if tags:
            out.append((row, tags))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect deals in recent listings.")
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Look at listings first seen in the last N hours (default 24).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the tagged listings as JSON to stdout (used in tests).",
    )
    args = parser.parse_args(argv)

    tagged = detect(window_hours=args.window_hours)
    print(f"[detect_deals] {len(tagged)} tagged listings in last {args.window_hours}h")
    counts: dict[str, int] = {}
    for _, tags in tagged:
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
    for tag, n in sorted(counts.items()):
        print(f"  {tag}: {n}")

    if args.json:
        json.dump(
            [
                {**row, "_tags": tags}
                for row, tags in tagged
            ],
            sys.stdout,
            default=str,
            indent=2,
        )
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
