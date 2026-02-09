"""Tests for current tools."""

import json

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_tides.tools.currents.api import register_currents_tools


@pytest.fixture
def currents_tools(mock_mcp, mock_manager):
    register_currents_tools(mock_mcp, mock_manager)
    return mock_mcp


# ── tides_currents_stations ───────────────────────────────────────────────


async def test_currents_stations_basic(currents_tools, mock_manager):
    mock_manager.list_current_stations = AsyncMock(
        return_value=[
            {
                "station_id": "PUG1515",
                "name": "Admiralty Inlet",
                "lat": 48.23,
                "lon": -122.73,
                "type": "S",
                "depth": 4.3,
                "depth_type": "S",
                "bin_number": 1,
                "provider": "noaa",
            },
            {
                "station_id": "PCT0101",
                "name": "Puget Sound",
                "lat": 47.60,
                "lon": -122.34,
                "provider": "noaa",
            },
        ]
    )

    result = await currents_tools.get_tool("tides_currents_stations")()
    parsed = json.loads(result)
    assert parsed["station_count"] == 2
    assert parsed["provider"] == "noaa"
    assert parsed["stations"][0]["station_id"] == "PUG1515"
    assert parsed["stations"][0]["name"] == "Admiralty Inlet"
    assert parsed["stations"][0]["depth"] == 4.3


async def test_currents_stations_with_location(currents_tools, mock_manager):
    mock_manager.list_current_stations = AsyncMock(
        return_value=[
            {
                "station_id": "PUG1515",
                "name": "Test",
                "lat": 48.0,
                "lon": -122.0,
                "provider": "noaa",
            },
        ]
    )

    result = await currents_tools.get_tool("tides_currents_stations")(
        lat=48.0,
        lon=-122.0,
        radius_km=25.0,
    )
    parsed = json.loads(result)
    assert parsed["search_location"] == [48.0, -122.0]
    assert parsed["search_radius_km"] == 25.0


async def test_currents_stations_text(currents_tools, mock_manager):
    mock_manager.list_current_stations = AsyncMock(
        return_value=[
            {
                "station_id": "PUG1515",
                "name": "Admiralty Inlet",
                "lat": 48.23,
                "lon": -122.73,
                "provider": "noaa",
            },
        ]
    )

    result = await currents_tools.get_tool("tides_currents_stations")(output_mode="text")
    assert "Admiralty Inlet" in result
    assert "PUG1515" in result


async def test_currents_stations_error(currents_tools, mock_manager):
    mock_manager.list_current_stations = AsyncMock(
        side_effect=RuntimeError("API timeout"),
    )

    result = await currents_tools.get_tool("tides_currents_stations")()
    parsed = json.loads(result)
    assert "API timeout" in parsed["error"]


# ── tides_currents_predictions ────────────────────────────────────────────


async def test_currents_predictions_basic(currents_tools, mock_manager):
    mock_manager.get_current_predictions = AsyncMock(
        return_value={
            "predictions": [
                {
                    "datetime": "2024-01-01 02:45",
                    "event_type": "slack",
                    "velocity_cm_s": 0.0,
                    "mean_flood_dir": 133,
                    "mean_ebb_dir": 317,
                    "depth": 4.3,
                    "bin": "1",
                },
                {
                    "datetime": "2024-01-01 05:30",
                    "event_type": "flood",
                    "velocity_cm_s": 14.7,
                    "mean_flood_dir": 133,
                    "mean_ebb_dir": 317,
                    "depth": 4.3,
                    "bin": "1",
                },
            ],
            "provider": "noaa",
            "units": "cm/s",
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "interval": "MAX_SLACK",
        }
    )
    mock_manager.list_current_stations = AsyncMock(
        return_value=[
            {"station_id": "PUG1515", "name": "Puget Sound"},
        ]
    )

    result = await currents_tools.get_tool("tides_currents_predictions")("PUG1515")
    parsed = json.loads(result)
    assert parsed["event_count"] == 2
    assert parsed["station_name"] == "Puget Sound"
    assert parsed["predictions"][0]["velocity_cm_s"] == 0.0
    assert parsed["predictions"][0]["event_type"] == "slack"
    assert parsed["predictions"][1]["event_type"] == "flood"
    assert parsed["predictions"][1]["velocity_cm_s"] == 14.7
    assert parsed["predictions"][1]["mean_flood_dir"] == 133


async def test_currents_predictions_text(currents_tools, mock_manager):
    mock_manager.get_current_predictions = AsyncMock(
        return_value={
            "predictions": [
                {
                    "datetime": "2024-01-01 05:30",
                    "event_type": "flood",
                    "velocity_cm_s": 14.7,
                    "mean_flood_dir": 133,
                    "bin": "1",
                },
            ],
            "provider": "noaa",
            "units": "cm/s",
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "interval": "MAX_SLACK",
        }
    )
    mock_manager.list_current_stations = AsyncMock(return_value=[])

    result = await currents_tools.get_tool("tides_currents_predictions")(
        "PUG1515",
        output_mode="text",
    )
    assert "cm/s" in result
    assert "flood" in result


async def test_currents_predictions_error(currents_tools, mock_manager):
    mock_manager.get_current_predictions = AsyncMock(
        side_effect=RuntimeError("Station not found"),
    )

    result = await currents_tools.get_tool("tides_currents_predictions")("INVALID")
    parsed = json.loads(result)
    assert "Station not found" in parsed["error"]


# ── tides_currents_latest ─────────────────────────────────────────────────


async def test_currents_latest_basic(currents_tools, mock_manager):
    mock_manager.get_current_latest = AsyncMock(
        return_value={
            "station_id": "cb0102",
            "datetime": "2024-01-01T12:00:00",
            "velocity_cm_s": 25.3,
            "direction": 133.0,
            "bin": "1",
            "units": "cm/s",
        }
    )
    mock_manager.list_current_stations = AsyncMock(
        return_value=[
            {"station_id": "cb0102", "name": "Chesapeake Bay"},
        ]
    )

    result = await currents_tools.get_tool("tides_currents_latest")("cb0102")
    parsed = json.loads(result)
    assert parsed["velocity_cm_s"] == 25.3
    assert parsed["direction"] == 133.0
    assert parsed["event_type"] == "flood"
    assert parsed["station_name"] == "Chesapeake Bay"


async def test_currents_latest_event_type(currents_tools, mock_manager):
    """Event type is derived from velocity sign."""
    # Ebb (negative velocity)
    mock_manager.get_current_latest = AsyncMock(
        return_value={
            "datetime": "2024-01-01T12:00:00",
            "velocity_cm_s": -18.5,
            "units": "cm/s",
        }
    )
    mock_manager.list_current_stations = AsyncMock(return_value=[])

    result = await currents_tools.get_tool("tides_currents_latest")("cb0102")
    parsed = json.loads(result)
    assert parsed["event_type"] == "ebb"

    # Slack (zero velocity)
    mock_manager.get_current_latest = AsyncMock(
        return_value={
            "datetime": "2024-01-01T15:00:00",
            "velocity_cm_s": 0.0,
            "units": "cm/s",
        }
    )

    result = await currents_tools.get_tool("tides_currents_latest")("cb0102")
    parsed = json.loads(result)
    assert parsed["event_type"] == "slack"


async def test_currents_latest_text(currents_tools, mock_manager):
    mock_manager.get_current_latest = AsyncMock(
        return_value={
            "datetime": "2024-01-01T12:00:00",
            "velocity_cm_s": 25.3,
            "direction": 133.0,
            "units": "cm/s",
        }
    )
    mock_manager.list_current_stations = AsyncMock(return_value=[])

    result = await currents_tools.get_tool("tides_currents_latest")(
        "cb0102",
        output_mode="text",
    )
    assert "25.3" in result or "+25.3" in result
    assert "flood" in result


async def test_currents_latest_error(currents_tools, mock_manager):
    mock_manager.get_current_latest = AsyncMock(
        side_effect=ValueError("No recent current observations"),
    )

    result = await currents_tools.get_tool("tides_currents_latest")("cb0102")
    parsed = json.loads(result)
    assert "No recent current observations" in parsed["error"]
