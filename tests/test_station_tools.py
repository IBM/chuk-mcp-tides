"""Tests for station discovery tools."""

import json

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_tides.constants import TideProvider
from chuk_mcp_tides.tools.stations.api import register_station_tools


@pytest.fixture
def station_tools(mock_mcp, mock_manager):
    register_station_tools(mock_mcp, mock_manager)
    return mock_mcp


# ── tides_list_stations ────────────────────────────────────────────────────


async def test_list_stations_json(station_tools, mock_manager):
    mock_manager.list_stations = AsyncMock(
        return_value=[
            {
                "station_id": "8454000",
                "name": "Providence",
                "lat": 41.8,
                "lon": -71.4,
                "provider": "noaa",
            },
            {
                "station_id": "8510560",
                "name": "Montauk",
                "lat": 41.0,
                "lon": -71.9,
                "provider": "noaa",
            },
        ]
    )

    result = await station_tools.get_tool("tides_list_stations")()
    parsed = json.loads(result)
    assert parsed["station_count"] == 2
    assert parsed["provider"] == "noaa"
    assert parsed["stations"][0]["station_id"] == "8454000"


async def test_list_stations_text(station_tools, mock_manager):
    mock_manager.list_stations = AsyncMock(
        return_value=[
            {"station_id": "123", "name": "Test", "lat": 40.0, "lon": -74.0, "provider": "noaa"},
        ]
    )

    result = await station_tools.get_tool("tides_list_stations")(output_mode="text")
    assert "Found 1 stations" in result
    assert "123" in result


async def test_list_stations_empty(station_tools, mock_manager):
    mock_manager.list_stations = AsyncMock(return_value=[])

    result = await station_tools.get_tool("tides_list_stations")()
    parsed = json.loads(result)
    assert parsed["station_count"] == 0
    assert parsed["stations"] == []


async def test_list_stations_with_proximity(station_tools, mock_manager):
    mock_manager.list_stations = AsyncMock(
        return_value=[
            {"station_id": "123", "name": "Near", "lat": 40.0, "lon": -74.0, "provider": "noaa"},
        ]
    )

    result = await station_tools.get_tool("tides_list_stations")(
        lat=40.0,
        lon=-74.0,
        radius_km=25.0,
    )
    parsed = json.loads(result)
    assert parsed["search_location"] == [40.0, -74.0]
    assert parsed["search_radius_km"] == 25.0


async def test_list_stations_error(station_tools, mock_manager):
    mock_manager.list_stations = AsyncMock(side_effect=RuntimeError("API down"))

    result = await station_tools.get_tool("tides_list_stations")()
    parsed = json.loads(result)
    assert "error" in parsed
    assert "API down" in parsed["error"]


# ── tides_describe_station ─────────────────────────────────────────────────


async def test_describe_station_basic(station_tools, mock_manager):
    mock_manager.get_station_detail = AsyncMock(
        return_value={
            "station_id": "8454000",
            "name": "Providence",
            "provider": "noaa",
            "lat": 41.8,
            "lon": -71.4,
        }
    )

    result = await station_tools.get_tool("tides_describe_station")("8454000")
    parsed = json.loads(result)
    assert parsed["station_id"] == "8454000"
    assert parsed["name"] == "Providence"


async def test_describe_station_with_datums(station_tools, mock_manager):
    mock_manager.get_station_detail = AsyncMock(
        return_value={
            "station_id": "8454000",
            "name": "Providence",
            "provider": "noaa",
            "lat": 41.8,
            "lon": -71.4,
            "datums": [{"name": "MLLW", "value": 0.0}, {"name": "MSL", "value": 1.2}],
        }
    )

    result = await station_tools.get_tool("tides_describe_station")("8454000")
    parsed = json.loads(result)
    assert len(parsed["datums"]) == 2
    assert parsed["datums"][0]["name"] == "MLLW"


async def test_describe_station_with_harcon(station_tools, mock_manager):
    mock_manager.get_station_detail = AsyncMock(
        return_value={
            "station_id": "8454000",
            "name": "Providence",
            "provider": "noaa",
            "lat": 41.8,
            "lon": -71.4,
            "harcon": [{"name": "M2", "amplitude": 0.5, "phase_GMT": 123.4, "speed": 28.984}],
        }
    )

    result = await station_tools.get_tool("tides_describe_station")("8454000")
    parsed = json.loads(result)
    assert parsed["harmonic_constituents"] is not None
    assert parsed["harmonic_constituents"][0]["name"] == "M2"


async def test_describe_station_with_flood_levels(station_tools, mock_manager):
    mock_manager.get_station_detail = AsyncMock(
        return_value={
            "station_id": "8454000",
            "name": "Providence",
            "provider": "noaa",
            "lat": 41.8,
            "lon": -71.4,
            "floodlevels": {"minor": 1.5, "moderate": 2.0, "major": 2.5},
        }
    )

    result = await station_tools.get_tool("tides_describe_station")("8454000")
    parsed = json.loads(result)
    assert parsed["flood_thresholds"]["minor"] == 1.5
    assert parsed["flood_thresholds"]["major"] == 2.5


async def test_describe_station_error(station_tools, mock_manager):
    mock_manager.get_station_detail = AsyncMock(
        side_effect=ValueError("Station not found"),
    )

    result = await station_tools.get_tool("tides_describe_station")("bad_id")
    parsed = json.loads(result)
    assert "Station not found" in parsed["error"]


# ── tides_find_nearest ─────────────────────────────────────────────────────


async def test_find_nearest(station_tools, mock_manager):
    mock_manager.find_nearest = AsyncMock(
        return_value=[
            {
                "station_id": "8454000",
                "name": "Providence",
                "lat": 41.8,
                "lon": -71.4,
                "provider": "noaa",
                "distance_km": 1.23,
            },
        ]
    )

    result = await station_tools.get_tool("tides_find_nearest")(lat=41.8, lon=-71.4)
    parsed = json.loads(result)
    assert parsed["search_location"] == [41.8, -71.4]
    assert len(parsed["stations"]) == 1
    assert parsed["stations"][0]["distance_km"] == 1.23


async def test_find_nearest_all_providers(station_tools, mock_manager):
    mock_manager.find_nearest = AsyncMock(return_value=[])

    await station_tools.get_tool("tides_find_nearest")(lat=40.0, lon=-74.0, provider="all")
    mock_manager.find_nearest.assert_called_once_with(
        40.0,
        -74.0,
        providers=None,
        max_results=5,
    )


async def test_find_nearest_specific_provider(station_tools, mock_manager):
    mock_manager.resolve_provider.return_value = TideProvider.NOAA
    mock_manager.find_nearest = AsyncMock(return_value=[])

    await station_tools.get_tool("tides_find_nearest")(
        lat=40.0,
        lon=-74.0,
        provider="noaa",
    )
    mock_manager.find_nearest.assert_called_once_with(
        40.0,
        -74.0,
        providers=[TideProvider.NOAA],
        max_results=5,
    )


async def test_find_nearest_text(station_tools, mock_manager):
    mock_manager.find_nearest = AsyncMock(
        return_value=[
            {
                "station_id": "123",
                "name": "Close",
                "lat": 40.01,
                "lon": -74.01,
                "provider": "noaa",
                "distance_km": 1.5,
            },
        ]
    )

    result = await station_tools.get_tool("tides_find_nearest")(
        lat=40.0,
        lon=-74.0,
        output_mode="text",
    )
    assert "1.5 km" in result
    assert "Close" in result
