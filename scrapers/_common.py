"""Shared scraper utilities.

Defines the canonical ``Listing`` dataclass and the Supabase upsert helper that
every scraper uses to write results into ``evwatch.listings`` and
``evwatch.price_history``. Also home for distance-from-Port-Orchard geocoding
and other cross-source helpers.

Not yet implemented — see SPEC §9 step 2.
"""
