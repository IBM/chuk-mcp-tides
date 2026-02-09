"""
Shared utility functions for chuk-mcp-tides.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points (km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_date(s: str) -> date:
    """Parse a date string (YYYY-MM-DD or 'today')."""
    if s == "today":
        return date.today()
    return date.fromisoformat(s)


def format_date_noaa(d: date) -> str:
    """Format a date for the NOAA API (YYYYMMDD)."""
    return d.strftime("%Y%m%d")


def format_date_iso(d: date) -> str:
    """Format a date as ISO 8601 (YYYY-MM-DD)."""
    return d.isoformat()


def now_utc() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)


def date_range_days(start: date, end: date) -> int:
    """Number of days between two dates (inclusive)."""
    return (end - start).days + 1


def add_days(d: date, days: int) -> date:
    """Add days to a date."""
    return d + timedelta(days=days)
