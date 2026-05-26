"""Email digest composition + send.

Pulls tagged listings from :mod:`pipeline.detect_deals`, renders
``templates/email.html.j2``, and POSTs to Resend via ``RESEND_API_KEY``.
Persists the rendered HTML + subject + counts to :data:`HANDOFF_PATH` so
:mod:`pipeline.record_run` (next workflow step) can write the digest row
without re-rendering.

Phase 5: emits three sections (Priority / Below market / Price drops).
The digest is filtered to recently-relevant tags only — detect_deals
also writes tags for older listings so the dashboard can show them, but
the digest only mentions:

- NEW_PRIORITY: ``first_seen_at`` in last 24h (already filtered)
- BELOW_MARKET: ``first_seen_at`` in last 24h (re-filtered here so we
  don't email about the same below-market car every day)
- PRICE_DROP: latest ``price_history.observed_at`` in last 24h (already
  filtered by detect_deals)

Cold-start subject ``[evwatch] day N/7 — X new listings`` is used until
seven digests have shipped; then it switches to the steady-state
``[evwatch] 2 priority, 4 deals, 6 drops``.

``--stub`` skips Supabase entirely and renders against fake data so
Resend wiring can be verified without scrapes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline.detect_deals import (
    BELOW_MARKET,
    NEW_PRIORITY,
    PRICE_DROP,
    TaggedListing,
    detect,
)
from scrapers._common import _env, get_supabase

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "templates"
TEMPLATE_NAME = "email.html.j2"
DASHBOARD_URL = os.environ.get(
    "EVWATCH_DASHBOARD_URL", "https://evwatch.veproductions.net"
)
RESEND_ENDPOINT = "https://api.resend.com/emails"

# Hand-off file read by pipeline.record_run in the next workflow step.
HANDOFF_PATH = Path(
    os.environ.get("EVWATCH_DIGEST_HANDOFF")
    or (Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "evwatch-digest.json")
)


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------


def _cold_start_day_number() -> int | None:
    """Return ``N`` such that this is day ``N/7`` of the firehose, or
    ``None`` once the firehose is over.
    """
    try:
        resp = (
            get_supabase()
            .schema("evwatch")
            .table("digests")
            .select("id", count="exact")
            .execute()
        )
    except Exception:
        return None
    count = resp.count or 0
    if count >= 7:
        return None
    return count + 1


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _subject(priority: int, deals: int, drops: int, total_new: int) -> str:
    day = _cold_start_day_number()
    if day is not None:
        return f"[evwatch] day {day}/7 — {total_new} new listings"
    # Steady-state. Skip zero-count sections.
    pieces: list[str] = []
    if priority:
        pieces.append(_plural(priority, "priority hit", "priority hits"))
    if deals:
        pieces.append(_plural(deals, "deal"))
    if drops:
        pieces.append(_plural(drops, "drop"))
    if not pieces:
        # Shouldn't happen — caller only ships if tagged is non-empty.
        return "[evwatch] nothing new"
    return f"[evwatch] {', '.join(pieces)}"


# ---------------------------------------------------------------------------
# Digest filtering
# ---------------------------------------------------------------------------


def _filter_for_digest(
    tagged: list[TaggedListing], *, window_hours: int
) -> tuple[list[dict], list[dict], list[dict]]:
    """Bucket tagged listings into the three digest sections.

    NEW_PRIORITY and BELOW_MARKET are restricted to first_seen_at in the
    window (we don't email about the same below-market car every day).
    PRICE_DROP is already filtered by detect_deals (latest observation in
    window), so we just unwrap.
    """
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=window_hours)

    priority: list[dict] = []
    deals: list[dict] = []
    drops: list[dict] = []

    for row, tags in tagged:
        is_newly_seen = False
        first_seen = row.get("first_seen_at")
        if first_seen:
            try:
                t = dt.datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
                is_newly_seen = t >= cutoff
            except (ValueError, AttributeError):
                pass

        if NEW_PRIORITY in tags and is_newly_seen:
            priority.append(row)
        if BELOW_MARKET in tags and is_newly_seen:
            deals.append({**row, "_below_market": tags[BELOW_MARKET]})
        if PRICE_DROP in tags:
            drops.append({**row, "_price_drop": tags[PRICE_DROP]})

    return priority, deals, drops


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def _env_jinja() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )


def render(
    tagged: list[TaggedListing],
    total_listings: int,
    *,
    window_hours: int = 24,
) -> dict[str, Any]:
    priority, deals, drops = _filter_for_digest(tagged, window_hours=window_hours)

    counts = {
        "priority": len(priority),
        "deals":    len(deals),
        "drops":    len(drops),
    }
    total_new = sum(counts.values())

    subject = _subject(counts["priority"], counts["deals"], counts["drops"], total_new)
    today = dt.date.today().isoformat()

    if counts["priority"] and not counts["deals"] and not counts["drops"]:
        heading = _plural(counts["priority"], "new priority listing")
    elif total_new == 0:
        heading = "No new activity"
    else:
        bits = []
        if counts["priority"]: bits.append(_plural(counts["priority"], "priority hit", "priority hits"))
        if counts["deals"]:    bits.append(_plural(counts["deals"], "below-market deal"))
        if counts["drops"]:    bits.append(_plural(counts["drops"], "price drop"))
        heading = " · ".join(bits)

    tmpl = _env_jinja().get_template(TEMPLATE_NAME)
    html = tmpl.render(
        subject=subject,
        heading=heading,
        today=today,
        year=dt.date.today().year,
        priority=priority,
        deals=deals,
        drops=drops,
        total_listings=total_listings,
        dashboard_url=DASHBOARD_URL,
    )

    rendered = {"subject": subject, "html": html, "counts": counts}
    try:
        HANDOFF_PATH.parent.mkdir(parents=True, exist_ok=True)
        HANDOFF_PATH.write_text(json.dumps(rendered))
    except OSError as e:
        print(f"[send_digest] could not write handoff file: {e}", file=sys.stderr)
    return rendered


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


def _send_via_resend(subject: str, html: str) -> dict[str, Any]:
    api_key = _env("RESEND_API_KEY")
    sender = os.environ.get("EVWATCH_DIGEST_FROM", "noreply@veproductions.net")
    recipient = os.environ.get("EVWATCH_DIGEST_TO", "dave@veproductions.net")
    resp = httpx.post(
        RESEND_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": sender,
            "to": [recipient],
            "subject": subject,
            "html": html,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Stub data (for --stub mode)
# ---------------------------------------------------------------------------


def _stub_tagged() -> list[TaggedListing]:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    fake_priority = {
        "id": "stub-1",
        "source": "ebay",
        "url": "https://example.com/stub-listing-1",
        "make": "Kia",
        "model": "EV9",
        "trim": "Wind",
        "year": 2024,
        "mileage": 12_500,
        "price": 48_900,
        "vin": None,
        "location": "Tacoma, WA, 98402",
        "miles_from_port_orchard": 18,
        "thumbnail_url": None,
        "first_seen_at": now,
    }
    fake_deal = {
        "id": "stub-2",
        "source": "carmax",
        "url": "https://example.com/stub-listing-2",
        "make": "Tesla",
        "model": "Model Y",
        "trim": "Long Range",
        "year": 2022,
        "mileage": 34_800,
        "price": 28_500,
        "vin": "5YJ3E1EA0NF000001",
        "location": "Lynnwood, WA",
        "miles_from_port_orchard": 38,
        "thumbnail_url": None,
        "first_seen_at": now,
    }
    fake_drop = {
        "id": "stub-3",
        "source": "carvana",
        "url": "https://example.com/stub-listing-3",
        "make": "Ford",
        "model": "Mustang Mach-E",
        "trim": "Premium",
        "year": 2023,
        "mileage": 19_400,
        "price": 31_200,
        "vin": None,
        "location": "Phoenix, AZ (ships to PNW)",
        "miles_from_port_orchard": None,
        "thumbnail_url": None,
        "first_seen_at": (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)
        ).isoformat(),
    }
    return [
        (fake_priority, {NEW_PRIORITY: {}}),
        (
            fake_deal,
            {
                BELOW_MARKET: {
                    "pct_below": 0.182,
                    "dollars_below": 6_350,
                    "baseline_median": 34_850,
                    "comp_count": 24,
                }
            },
        ),
        (
            fake_drop,
            {
                PRICE_DROP: {
                    "previous_price": 33_700,
                    "delta": -2_500,
                    "delta_pct": -0.074,
                    "observed_at_previous": (
                        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)
                    ).isoformat(),
                }
            },
        ),
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render + send the evwatch digest.")
    parser.add_argument("--stub", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render + print HTML; don't POST to Resend.")
    parser.add_argument("--window-hours", type=int, default=24)
    args = parser.parse_args(argv)

    if args.stub:
        tagged = _stub_tagged()
        total_listings = len(tagged)
    else:
        tagged = detect(window_hours=args.window_hours)
        try:
            resp = (
                get_supabase()
                .schema("evwatch")
                .table("listings")
                .select("id", count="exact")
                .execute()
            )
            total_listings = resp.count or 0
        except Exception:
            total_listings = 0

    # Pre-check: would the digest actually contain anything?
    priority, deals, drops = _filter_for_digest(tagged, window_hours=args.window_hours)
    if not (priority or deals or drops) and not args.stub:
        print("[send_digest] nothing to report — skipping send.")
        return 0

    rendered = render(tagged, total_listings=total_listings, window_hours=args.window_hours)
    print(f"[send_digest] subject: {rendered['subject']}")
    print(f"[send_digest] counts: {rendered['counts']}")

    if args.dry_run:
        sys.stdout.write(rendered["html"])
        return 0

    try:
        result = _send_via_resend(rendered["subject"], rendered["html"])
    except httpx.HTTPError as e:
        print(f"[send_digest] Resend send failed: {e}", file=sys.stderr)
        return 1
    print(f"[send_digest] sent: {result.get('id') or result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
