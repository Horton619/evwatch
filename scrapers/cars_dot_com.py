"""Cars.com scraper (Mac-only, less aggressive anti-bot).

Try plain ``httpx`` requests first; fall back to Playwright if blocked. Runs
from the Electron app via residential IP — not from GitHub Actions.
"""
