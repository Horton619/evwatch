"""CarGurus scraper (Mac-only, anti-bot protected).

Uses Playwright headless Chromium against CarGurus listing search. Captures
the CarGurus deal-rating label per listing as an extra signal. Runs from the
Electron app via residential IP — not from GitHub Actions.
"""
