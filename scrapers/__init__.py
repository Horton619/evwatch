"""evwatch scrapers package.

Each module exposes ``scrape(filters) -> list[Listing]`` and writes results to
Supabase via the helpers in :mod:`scrapers._common`. Scrapers are stateless and
repeat-safe — they upsert on the stable ``(source, source_listing_id)`` key.
"""
