"""Carvana scraper — DEFERRED to Phase 6.

Empirically blocked in Phase 3 testing: Carvana's Cloudflare config lets
the *first* page navigation per browser session through (returns real
results), then 403s or times out every subsequent nav in the same
context. ``networkidle`` waits don't help — they just make the run
slower without improving the success rate.

Workarounds that don't pencil out for GHA:
- Fresh browser context per (make, model) — 15× slower, still hits the
  same IP-rate-limit ceiling.
- Longer pacing — Cloudflare's clearance cookie doesn't extend to new
  page paths reliably.

Deferred to Phase 6, where the Mac Electron app runs from your
residential IP with persistent cookies, real interaction patterns, and
the time to look human. The Playwright code that was here is preserved
in git history (commit before this one) and is the right starting point
— just needs a different runner.

Module shape matches scrapers/carmax.py (the other deferred source).
"""

from __future__ import annotations

import argparse
import sys

from scrapers._common import Listing, run_scraper

SOURCE = "carvana"


def scrape(filters: dict | None = None) -> list[Listing]:
    print(
        "[carvana] deferred to Phase 6 (residential IP via Mac app). "
        "Returning 0 listings; nothing to upsert.",
        file=sys.stderr,
    )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carvana scraper (deferred).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
