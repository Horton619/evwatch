"""Run + source-health logging.

Runs after :mod:`pipeline.send_digest`. Writes one row to ``evwatch.digests``
containing the counts and rendered HTML from the digest that just shipped,
then prints today's ``evwatch.source_runs`` rows so GHA logs surface what
each scraper did (or didn't do).

If ``send_digest`` was skipped because there was nothing to report, this
still writes a digest row with zero counts and empty HTML — so the run is
always visible in the log.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from pipeline.send_digest import HANDOFF_PATH
from scrapers._common import get_supabase


def _surface_source_runs(window_hours: int = 24) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    try:
        resp = (
            get_supabase()
            .schema("evwatch")
            .table("source_runs")
            .select("*")
            .gte("ran_at", cutoff)
            .order("ran_at", desc=True)
            .execute()
        )
    except Exception as e:
        print(f"[record_run] could not read source_runs: {e}", file=sys.stderr)
        return

    rows = resp.data or []
    print(f"[record_run] source_runs in last {window_hours}h: {len(rows)}")
    for r in rows:
        status = "ok" if not r.get("error") else f"ERROR: {r['error']}"
        print(
            f"  {r['ran_at']} | {r['source']:<12} | "
            f"{r.get('listings_found', 0):>4} listings | "
            f"{r.get('duration_ms', 0):>6}ms | {status}"
        )


def _write_digest_row() -> None:
    if HANDOFF_PATH.exists():
        try:
            rendered = json.loads(HANDOFF_PATH.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"[record_run] handoff file unreadable: {e}", file=sys.stderr)
            rendered = {}
    else:
        # send_digest skipped (nothing to report) — log a zero-count row.
        rendered = {}
    counts = rendered.get("counts") or {"priority": 0, "drops": 0, "deals": 0}
    try:
        get_supabase().schema("evwatch").table("digests").insert(
            {
                "priority_count": int(counts.get("priority", 0)),
                "drop_count": int(counts.get("drops", 0)),
                "deal_count": int(counts.get("deals", 0)),
                "email_html": rendered.get("html") or "",
            }
        ).execute()
        print(
            f"[record_run] digest row written "
            f"(priority={counts['priority']}, drops={counts['drops']}, deals={counts['deals']})"
        )
    except Exception as e:
        print(f"[record_run] could not write digest row: {e}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Log the run + source health.")
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Window of source_runs to surface in the log (default 24).",
    )
    args = parser.parse_args(argv)

    _write_digest_row()
    _surface_source_runs(window_hours=args.window_hours)
    return 0


if __name__ == "__main__":
    sys.exit(main())
