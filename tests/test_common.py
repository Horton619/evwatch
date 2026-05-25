"""Tiny smoke tests for scrapers/_common.py — no Supabase required."""

from __future__ import annotations

from scrapers import _common


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
