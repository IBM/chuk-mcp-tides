"""Tests for core utility functions."""

from datetime import date, datetime, timezone

from chuk_mcp_tides.core.utils import (
    add_days,
    date_range_days,
    format_date_iso,
    format_date_noaa,
    haversine_km,
    now_utc,
    parse_date,
)


def test_haversine_km_known_distance():
    # NYC to London ~ 5570 km
    dist = haversine_km(40.7128, -74.0060, 51.5074, -0.1278)
    assert 5550 < dist < 5590


def test_haversine_km_same_point():
    dist = haversine_km(51.5, -0.1, 51.5, -0.1)
    assert dist == 0.0


def test_haversine_km_short_distance():
    # ~1 degree latitude ~ 111 km
    dist = haversine_km(50.0, 0.0, 51.0, 0.0)
    assert 110 < dist < 112


def test_parse_date_today():
    result = parse_date("today")
    assert result == date.today()


def test_parse_date_iso_string():
    result = parse_date("2024-06-15")
    assert result == date(2024, 6, 15)


def test_parse_date_iso_format():
    result = parse_date("2024-01-01")
    assert result == date(2024, 1, 1)


def test_format_date_noaa():
    d = date(2024, 6, 15)
    assert format_date_noaa(d) == "20240615"


def test_format_date_iso():
    d = date(2024, 6, 15)
    assert format_date_iso(d) == "2024-06-15"


def test_now_utc():
    result = now_utc()
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc


def test_date_range_days():
    start = date(2024, 1, 1)
    end = date(2024, 1, 10)
    assert date_range_days(start, end) == 10  # inclusive


def test_add_days():
    d = date(2024, 1, 1)
    result = add_days(d, 7)
    assert result == date(2024, 1, 8)


def test_add_days_negative():
    d = date(2024, 1, 10)
    result = add_days(d, -3)
    assert result == date(2024, 1, 7)
