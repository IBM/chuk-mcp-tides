"""Tests for observation tools."""

import json

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_tides.tools.observations.api import register_observation_tools


@pytest.fixture
def observation_tools(mock_mcp, mock_manager):
    register_observation_tools(mock_mcp, mock_manager)
    return mock_mcp


# ── tides_observations ─────────────────────────────────────────────────────


async def test_observations_basic(observation_tools, mock_manager):
    mock_manager.get_observations = AsyncMock(return_value={
        "readings": [
            {"datetime": "2024-01-01T12:00:00", "value": 0.5, "quality": "v"},
            {"datetime": "2024-01-01T12:06:00", "value": 0.55},
        ],
        "provider": "noaa", "datum": "MLLW", "units": "metric", "product": "water_level",
    })
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Providence"})

    result = await observation_tools.get_tool("tides_observations")("8454000")
    parsed = json.loads(result)
    assert parsed["reading_count"] == 2
    assert parsed["station_name"] == "Providence"
    assert parsed["readings"][0]["value"] == 0.5
    assert parsed["readings"][0]["quality"] == "v"


async def test_observations_with_time_field(observation_tools, mock_manager):
    """Providers may return 'time' instead of 'datetime'."""
    mock_manager.get_observations = AsyncMock(return_value={
        "readings": [{"time": "2024-01-01T12:00:00Z", "value": 3.45}],
        "provider": "ea",
    })
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Dover"})

    result = await observation_tools.get_tool("tides_observations")("E1234")
    parsed = json.loads(result)
    assert parsed["readings"][0]["datetime"] == "2024-01-01T12:00:00Z"


async def test_observations_text(observation_tools, mock_manager):
    mock_manager.get_observations = AsyncMock(return_value={
        "readings": [{"datetime": "2024-01-01T12:00", "value": 0.5}],
        "product": "water_level",
    })
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Test"})

    result = await observation_tools.get_tool("tides_observations")(
        "8454000", output_mode="text",
    )
    assert "water_level" in result


async def test_observations_error(observation_tools, mock_manager):
    mock_manager.get_observations = AsyncMock(
        side_effect=RuntimeError("API timeout"),
    )

    result = await observation_tools.get_tool("tides_observations")("8454000")
    parsed = json.loads(result)
    assert "API timeout" in parsed["error"]


# ── tides_latest ───────────────────────────────────────────────────────────


async def test_latest_basic(observation_tools, mock_manager):
    mock_manager.get_latest = AsyncMock(return_value={
        "datetime": "2024-01-01T12:00:00", "value": 0.75,
        "datum": "MLLW", "provider": "noaa",
    })
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Providence"})
    mock_manager.get_predictions = AsyncMock(return_value={
        "predictions": [
            {"datetime": "2024-01-01T18:00:00", "height": 1.5, "event_type": "high"},
            {"datetime": "2024-01-01T06:00:00", "height": -0.3, "event_type": "low"},
        ],
    })
    mock_manager.determine_tide_state.return_value = (
        "rising",
        {"datetime": "2024-01-01T18:00:00", "height": 1.5},
        {"datetime": "2024-01-02T00:00:00", "height": -0.3},
    )

    result = await observation_tools.get_tool("tides_latest")("8454000")
    parsed = json.loads(result)
    assert parsed["value"] == 0.75
    assert parsed["tide_state"] == "rising"
    assert parsed["station_name"] == "Providence"
    assert parsed["next_high"]["event_type"] == "high"
    assert parsed["next_low"]["event_type"] == "low"


async def test_latest_no_predictions(observation_tools, mock_manager):
    """Should still work if predictions fail."""
    mock_manager.get_latest = AsyncMock(return_value={
        "datetime": "2024-01-01T12:00:00", "value": 0.5, "datum": "MLLW",
    })
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Test"})
    mock_manager.get_predictions = AsyncMock(side_effect=RuntimeError("no data"))

    result = await observation_tools.get_tool("tides_latest")("8454000")
    parsed = json.loads(result)
    assert parsed["value"] == 0.5
    assert parsed["tide_state"] == "unknown"


async def test_latest_text(observation_tools, mock_manager):
    mock_manager.get_latest = AsyncMock(return_value={
        "datetime": "2024-01-01T12:00:00", "value": 0.75, "datum": "MLLW",
    })
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Test"})
    mock_manager.get_predictions = AsyncMock(side_effect=RuntimeError("skip"))

    result = await observation_tools.get_tool("tides_latest")(
        "8454000", output_mode="text",
    )
    assert "0.750" in result or "+0.750" in result


async def test_latest_error(observation_tools, mock_manager):
    mock_manager.get_latest = AsyncMock(
        side_effect=ValueError("No recent observations"),
    )

    result = await observation_tools.get_tool("tides_latest")("8454000")
    parsed = json.loads(result)
    assert "No recent observations" in parsed["error"]
