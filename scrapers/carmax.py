"""CarMax scraper — DEFERRED to Phase 6.

Empirically blocked: CarMax returns 403 on every path (including the
public homepage), both from plain ``httpx`` AND from headless Chromium
via Playwright. That rules out the standard fingerprint-bypass tricks —
they're filtering on IP reputation and behavioural signals, not on
browser shape. GHA datacenter IPs are worse-than-residential, so adding
Playwright to CI doesn't help CarMax either.

Deferred to Phase 6, where the Mac Electron app runs scrapers from your
residential IP via a Playwright session that has the time to look human
(real mouse moves, slower nav, persistent cookies). The structured
code that was here originally is preserved in git history (commit before
this one) and will be the starting point.

This module still exposes ``scrape()`` / ``main()`` so the workflow can
include it as a clean no-op, logging a 0-listings ``source_runs`` row
that makes the deferral visible in the daily log.
"""

from __future__ import annotations

import argparse
import sys

from scrapers._common import Listing, run_scraper

SOURCE = "carmax"


def scrape(filters: dict | None = None) -> list[Listing]:
    print(
        "[carmax] deferred to Phase 6 (residential IP via Mac app). "
        "Returning 0 listings; nothing to upsert.",
        file=sys.stderr,
    )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CarMax scraper (deferred).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run_scraper(SOURCE, scrape, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
