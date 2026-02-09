"""Tests for prediction tools."""

import json

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_tides.tools.predictions.api import register_prediction_tools


@pytest.fixture
def prediction_tools(mock_mcp, mock_manager):
    register_prediction_tools(mock_mcp, mock_manager)
    return mock_mcp


# ── tides_predict ──────────────────────────────────────────────────────────


async def test_predict_basic(prediction_tools, mock_manager):
    mock_manager.get_predictions = AsyncMock(
        return_value={
            "predictions": [
                {"datetime": "2024-01-01T06:00:00", "height": 1.5, "event_type": "high"},
                {"datetime": "2024-01-01T12:00:00", "height": -0.3, "event_type": "low"},
            ],
            "provider": "noaa",
            "datum": "MLLW",
            "units": "metric",
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
            "interval": "hilo",
        }
    )
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Providence"})

    result = await prediction_tools.get_tool("tides_predict")("8454000")
    parsed = json.loads(result)
    assert parsed["event_count"] == 2
    assert parsed["station_name"] == "Providence"
    assert parsed["predictions"][0]["height"] == 1.5
    assert parsed["predictions"][0]["event_type"] == "high"


async def test_predict_with_time_field(prediction_tools, mock_manager):
    """Providers may return 'time' instead of 'datetime'."""
    mock_manager.get_predictions = AsyncMock(
        return_value={
            "predictions": [
                {"time": "2024-01-01T06:00:00", "height": 1.5},
            ],
            "provider": "ukho",
            "datum": "CD",
        }
    )
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Aberdeen"})

    result = await prediction_tools.get_tool("tides_predict")("0001")
    parsed = json.loads(result)
    assert parsed["predictions"][0]["datetime"] == "2024-01-01T06:00:00"


async def test_predict_station_detail_failure(prediction_tools, mock_manager):
    """Should still work if station detail lookup fails."""
    mock_manager.get_predictions = AsyncMock(
        return_value={
            "predictions": [{"datetime": "2024-01-01T06:00", "height": 1.0}],
        }
    )
    mock_manager.get_station_detail = AsyncMock(side_effect=RuntimeError("not found"))

    result = await prediction_tools.get_tool("tides_predict")("8454000")
    parsed = json.loads(result)
    assert parsed["station_name"] == "8454000"  # falls back to station_id
    assert parsed["event_count"] == 1


async def test_predict_text(prediction_tools, mock_manager):
    mock_manager.get_predictions = AsyncMock(
        return_value={
            "predictions": [
                {"datetime": "2024-01-01T06:00", "height": 1.5, "event_type": "high"},
            ],
        }
    )
    mock_manager.get_station_detail = AsyncMock(return_value={"name": "Test"})

    result = await prediction_tools.get_tool("tides_predict")(
        "8454000",
        output_mode="text",
    )
    assert "[high]" in result


async def test_predict_error(prediction_tools, mock_manager):
    mock_manager.get_predictions = AsyncMock(
        side_effect=ValueError("No predictions available"),
    )

    result = await prediction_tools.get_tool("tides_predict")("bad_id")
    parsed = json.loads(result)
    assert "No predictions available" in parsed["error"]


# ── tides_predict_local ────────────────────────────────────────────────────


async def test_predict_local(prediction_tools, mock_manager):
    mock_manager.predict_local = AsyncMock(
        return_value={
            "predictions": [
                {"datetime": "2024-01-01T00:00", "height": 0.5},
                {"datetime": "2024-01-01T01:00", "height": 0.8},
            ],
            "highs_lows": [
                {"datetime": "2024-01-01T06:00", "height": 1.2, "event_type": "high"},
            ],
            "constituent_count": 37,
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
        }
    )

    result = await prediction_tools.get_tool("tides_predict_local")(
        start_date="2024-01-01",
        end_date="2024-01-02",
        station_id="8454000",
    )
    parsed = json.loads(result)
    assert parsed["constituent_count"] == 37
    assert parsed["event_count"] == 2
    assert len(parsed["highs_lows"]) == 1
    assert parsed["highs_lows"][0]["event_type"] == "high"


async def test_predict_local_text(prediction_tools, mock_manager):
    mock_manager.predict_local = AsyncMock(
        return_value={
            "predictions": [],
            "highs_lows": [],
            "constituent_count": 37,
        }
    )

    result = await prediction_tools.get_tool("tides_predict_local")(
        start_date="2024-01-01",
        end_date="2024-01-07",
        output_mode="text",
    )
    assert "37" in result


async def test_predict_local_error(prediction_tools, mock_manager):
    mock_manager.predict_local = AsyncMock(
        side_effect=ValueError("No constituents stored"),
    )

    result = await prediction_tools.get_tool("tides_predict_local")(
        start_date="2024-01-01",
        end_date="2024-01-07",
    )
    parsed = json.loads(result)
    assert "No constituents stored" in parsed["error"]
