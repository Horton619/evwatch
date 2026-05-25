"""Email digest composition + send.

Pulls tagged listings from :mod:`pipeline.detect_deals`, renders
``templates/email.html.j2``, and POSTs to Resend via ``RESEND_API_KEY``.
Persists the rendered HTML + subject + counts to :data:`HANDOFF_PATH` so
:mod:`pipeline.record_run` (next workflow step) can write the digest row
without re-rendering.

Phase 2 quirks:
- Only the ``NEW_PRIORITY`` section is emitted (no drops, deals, or trends).
- Cold-start subject ``[evwatch] day N/7 — X new listings`` is used while
  there have been fewer than 7 digests sent. After that, a basic steady
  subject is used until later phases flesh out drops/deals.
- ``--stub`` skips Supabase entirely and renders against fake data — used
  to verify Resend wiring before any scrapers have run.

Exit codes:
- ``0`` — sent successfully (or skipped cleanly because there was nothing
  to report)
- ``1`` — render/send failed
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

from pipeline.detect_deals import NEW_PRIORITY, TaggedListing, detect
from scrapers._common import _env, get_supabase

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "templates"
TEMPLATE_NAME = "email.html.j2"
DASHBOARD_URL = os.environ.get(
    "EVWATCH_DASHBOARD_URL", "https://evwatch.veproductions.net"
)
RESEND_ENDPOINT = "https://api.resend.com/emails"

# Hand-off file read by pipeline.record_run in the next workflow step.
# Lives outside the repo so it doesn't risk getting committed. On GHA we
# prefer $RUNNER_TEMP (auto-cleaned between runs).
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

    Counts existing ``evwatch.digests`` rows. The next digest is day
    ``count + 1``. Returns ``None`` once seven digests have already been
    sent.
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
        # Don't let a Supabase blip block the email — fall back to no day
        # number, which yields the steady-state subject.
        return None
    count = resp.count or 0
    if count >= 7:
        return None
    return count + 1


def _subject(priority_count: int) -> str:
    day = _cold_start_day_number()
    if day is not None:
        return f"[evwatch] day {day}/7 — {priority_count} new listings"
    # Steady-state subject. Once drops/deals exist, this gets enriched.
    return f"[evwatch] {priority_count} priority hit{'s' if priority_count != 1 else ''}"


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
) -> dict[str, Any]:
    """Render the digest. Returns ``{"subject", "html", "counts"}``."""
    priority = [row for row, tags in tagged if NEW_PRIORITY in tags]

    counts = {
        "priority": len(priority),
        "drops": 0,  # phase 4+
        "deals": 0,  # phase 5+
    }

    subject = _subject(counts["priority"])
    today = dt.date.today().isoformat()
    heading = (
        f"{counts['priority']} new priority listing"
        f"{'' if counts['priority'] == 1 else 's'}"
        if counts["priority"]
        else "No priority hits today"
    )

    tmpl = _env_jinja().get_template(TEMPLATE_NAME)
    html = tmpl.render(
        subject=subject,
        heading=heading,
        today=today,
        year=dt.date.today().year,
        priority=priority,
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
    fake = [
        {
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
            "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        {
            "id": "stub-2",
            "source": "ebay",
            "url": "https://example.com/stub-listing-2",
            "make": "Rivian",
            "model": "R1S",
            "trim": "Adventure",
            "year": 2023,
            "mileage": 24_100,
            "price": 65_500,
            "vin": None,
            "location": "Portland, OR, 97214",
            "miles_from_port_orchard": 142,
            "thumbnail_url": None,
            "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    ]
    return [(row, [NEW_PRIORITY]) for row in fake]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render + send the evwatch digest.")
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use fake listings; skip Supabase. Useful for testing Resend.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render + print the HTML to stdout; don't POST to Resend.",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Look at listings first seen in the last N hours (default 24).",
    )
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

    if not tagged and not args.stub:
        print("[send_digest] nothing to report — skipping send.")
        return 0

    rendered = render(tagged, total_listings=total_listings)
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
