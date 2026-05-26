"""Tiny smoke tests for scrapers/_common.py — no Supabase required.

Also exercises the run_scraper wrapper and confirms every scraper module
imports cleanly with no env vars set (so a typo in one source can't break
the others on cold import).
"""

from __future__ import annotations

import importlib

import pytest

from scrapers import _common
from scrapers._common import (
    Listing,
    bucket_key,
    mileage_bucket,
    run_scraper,
)


def test_port_orchard_to_self_is_zero() -> None:
    assert _common.miles_from_port_orchard(_common.PORT_ORCHARD_ZIP) == 0


def test_seattle_is_within_30_miles() -> None:
    # 98101 is downtown Seattle. Port Orchard is across Puget Sound;
    # great-circle distance is ~14 mi.
    d = _common.miles_from_port_orchard("98101")
    assert d is not None
    assert 10 <= d <= 30, f"Seattle distance came back as {d}"


def test_portland_is_around_140_miles() -> None:
    # 97214 is inner SE Portland. Great-circle from Port Orchard is ~135 mi.
    d = _common.miles_from_port_orchard("97214")
    assert d is not None
    assert 120 <= d <= 160, f"Portland distance came back as {d}"


def test_unknown_zip_returns_none() -> None:
    assert _common.miles_from_port_orchard("99999") is None
    assert _common.miles_from_port_orchard(None) is None
    assert _common.miles_from_port_orchard("") is None


def test_zip_plus_4_is_truncated() -> None:
    # eBay sometimes returns ZIP+4. We only use the leading 5 digits.
    assert _common.miles_from_port_orchard("98101-1234") == _common.miles_from_port_orchard("98101")


def test_watchlist_loads_with_priority_and_broad_models() -> None:
    wl = _common.load_watchlist()
    assert wl["priority_models"], "priority_models should be populated"
    assert wl["broad_models"], "broad_models should be populated"
    assert wl["filters"]["origin_zip"] == "98366"


# ---------------------------------------------------------------------------
# run_scraper helper
# ---------------------------------------------------------------------------


def _fake_scrape_ok(_filters: dict) -> list[Listing]:
    return [
        Listing(
            source="testsrc",
            source_listing_id="abc",
            url="https://example.com/abc",
            make="Tesla",
            model="Model Y",
            year=2023,
            mileage=12000,
            price=42000,
        )
    ]


def _fake_scrape_boom(_filters: dict) -> list[Listing]:
    raise RuntimeError("simulated source failure")


def test_run_scraper_dry_run_does_not_touch_supabase(capsys) -> None:
    exit_code = run_scraper("testsrc", _fake_scrape_ok, dry_run=True)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "scraped 1 listings" in captured.out
    assert "2023 Tesla Model Y" in captured.out


def test_run_scraper_dry_run_handles_scrape_exception(capsys) -> None:
    exit_code = run_scraper("testsrc", _fake_scrape_boom, dry_run=True)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "scrape failed" in captured.err
    assert "scraped 0 listings" in captured.out


# ---------------------------------------------------------------------------
# Bucketing for baselines
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "miles,expected",
    [
        (0,       "lt10k"),
        (9_999,   "lt10k"),
        (10_000,  "10k-20k"),
        (35_500,  "30k-40k"),
        (60_000,  "60k-80k"),
        (79_999,  "60k-80k"),
        (80_000,  "80kplus"),
        (150_000, "80kplus"),
    ],
)
def test_mileage_bucket_boundaries(miles: int, expected: str) -> None:
    assert mileage_bucket(miles) == expected


def test_mileage_bucket_rejects_missing_or_negative() -> None:
    assert mileage_bucket(None) is None
    assert mileage_bucket(-1) is None


def test_bucket_key_happy_path() -> None:
    assert bucket_key("Tesla", "Model Y", 2022, 35_000) == "tesla:model-y:2022:30k-40k:pnw"
    assert bucket_key("Ford", "Mustang Mach-E", 2023, 18_000) == "ford:mustang-mach-e:2023:10k-20k:pnw"


def test_bucket_key_returns_none_for_missing_inputs() -> None:
    assert bucket_key(None, "Model Y", 2022, 35_000) is None
    assert bucket_key("Tesla", None, 2022, 35_000) is None
    assert bucket_key("Tesla", "Model Y", None, 35_000) is None
    assert bucket_key("Tesla", "Model Y", 2022, None) is None


def test_bucket_key_region_is_overridable() -> None:
    assert bucket_key("Tesla", "Model Y", 2022, 35_000, region="national") == (
        "tesla:model-y:2022:30k-40k:national"
    )


# ---------------------------------------------------------------------------
# Cold-import smoke for every scraper module
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "modname",
    [
        "scrapers.ebay",
        "scrapers.carmax",
        "scrapers.carvana",
        "scrapers.craigslist",
        "scrapers.autotempest",
    ],
)
def test_scraper_module_imports_without_env(monkeypatch, modname: str) -> None:
    # Strip every secret to confirm import-time code doesn't read env vars.
    for var in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "EBAY_APP_ID",
        "EBAY_CERT_ID",
        "RESEND_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    mod = importlib.import_module(modname)
    assert callable(getattr(mod, "scrape", None))
    assert callable(getattr(mod, "main", None))
    assert getattr(mod, "SOURCE", None)
