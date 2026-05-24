"""Wayback Machine historical seeder.

One-time bulk fetch of archived search-page snapshots for priority models over
the last ~12 months. Uses the Internet Archive CDX API to list snapshots,
fetches each, parses observable prices, and writes to ``evwatch.price_history``
with ``source_kind = 'wayback'``. Rate-limited by archive.org — runs from the
Mac.
"""
