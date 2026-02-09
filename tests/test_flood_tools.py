"""Tests for flood risk tools."""

import json

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_tides.tools.flood.api import register_flood_tools


@pytest.fixture
def flood_tools(mock_mcp, mock_manager):
    register_flood_tools(mock_mcp, mock_manager)
    return mock_mcp


# ── tides_flood_outlook ────────────────────────────────────────────────────


async def test_flood_outlook(flood_tools, mock_manager):
    mock_manager.get_flood_outlook = AsyncMock(return_value={
        "counts": [
            {"period": "2022", "count": 3},
            {"period": "2023", "count": 5},
        ],
        "product": "annual",
        "threshold": "minor",
        "flood_level_m": 1.04,
        "projection": {"year": 2025, "expected": 8, "low": 5, "high": 12},
    })

    result = await flood_tools.get_tool("tides_flood_outlook")("8454000")
    parsed = json.loads(result)
    assert len(parsed["counts"]) == 2
    assert parsed["flood_level_m"] == 1.04
    assert parsed["projection"]["expected"] == 8
    assert parsed["projection"]["low"] == 5


async def test_flood_outlook_no_projection(flood_tools, mock_manager):
    mock_manager.get_flood_outlook = AsyncMock(return_value={
        "counts": [{"period": "2023", "count": 5}],
        "product": "annual",
        "threshold": "minor",
        "flood_level_m": 1.04,
    })

    result = await flood_tools.get_tool("tides_flood_outlook")("8454000")
    parsed = json.loads(result)
    assert parsed["projection"] is None


async def test_flood_outlook_text(flood_tools, mock_manager):
    mock_manager.get_flood_outlook = AsyncMock(return_value={
        "counts": [{"period": "2023", "count": 5}],
        "flood_level_m": 1.04,
    })

    result = await flood_tools.get_tool("tides_flood_outlook")(
        "8454000", output_mode="text",
    )
    assert "5 flood events" in result


async def test_flood_outlook_error(flood_tools, mock_manager):
    mock_manager.get_flood_outlook = AsyncMock(
        side_effect=ValueError("NOAA only"),
    )

    result = await flood_tools.get_tool("tides_flood_outlook")("bad_id")
    parsed = json.loads(result)
    assert "NOAA only" in parsed["error"]


# ── tides_flooding_calendar ────────────────────────────────────────────────


async def test_flooding_calendar(flood_tools, mock_manager):
    mock_manager.flooding_calendar = AsyncMock(return_value={
        "year": 2024,
        "threshold": 1.5,
        "slr_offset_mm": 50,
        "datum": "MLLW",
        "total_flood_days": 10,
        "total_flood_hours": 20.0,
        "monthly_summary": [
            {"month": 1, "flood_days": 3, "max_height": 1.8, "total_hours": 6.0},
            {"month": 2, "flood_days": 2, "max_height": 1.7, "total_hours": 4.0},
        ],
        "flood_days": [
            {"date": "2024-01-15", "peak_height": 1.8, "duration_hours": 4.0, "tides_above": 2},
        ],
    })

    result = await flood_tools.get_tool("tides_flooding_calendar")(
        station_id="8454000", threshold=1.5, year=2024, slr_offset_mm=50,
    )
    parsed = json.loads(result)
    assert parsed["total_flood_days"] == 10
    assert parsed["total_flood_hours"] == 20.0
    assert len(parsed["monthly_summary"]) == 2
    assert len(parsed["flood_days"]) == 1
    assert parsed["flood_days"][0]["peak_height"] == 1.8


async def test_flooding_calendar_text(flood_tools, mock_manager):
    mock_manager.flooding_calendar = AsyncMock(return_value={
        "year": 2024,
        "threshold": 1.5,
        "slr_offset_mm": 0,
        "datum": "MLLW",
        "total_flood_days": 5,
        "total_flood_hours": 10.0,
        "monthly_summary": [
            {"month": 1, "flood_days": 2, "max_height": 1.7, "total_hours": 3.0},
        ],
        "flood_days": [],
    })

    result = await flood_tools.get_tool("tides_flooding_calendar")(
        station_id="8454000", threshold=1.5, output_mode="text",
    )
    assert "5" in result  # total_flood_days


async def test_flooding_calendar_error(flood_tools, mock_manager):
    mock_manager.flooding_calendar = AsyncMock(
        side_effect=ValueError("No prediction data"),
    )

    result = await flood_tools.get_tool("tides_flooding_calendar")(
        station_id="8454000", threshold=1.5,
    )
    parsed = json.loads(result)
    assert "No prediction data" in parsed["error"]
