"""eBay Motors scraper.

Pulls used EV listings from the eBay Browse API (free tier: 5000 calls/day).
Friendly source — runs from GitHub Actions on the daily cron. Requires
``EBAY_APP_ID`` env var.
"""
