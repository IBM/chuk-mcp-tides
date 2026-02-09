"""Tests for the UK Environment Agency provider with mocked HTTP."""

import pytest

from chuk_mcp_tides.providers.ea import EAProvider


@pytest.fixture
def ea():
    return EAProvider()


async def test_list_stations(ea, mock_resilient, make_response):
    mock_resilient([
        make_response({
            "items": [
                {"stationReference": "E1234", "label": "Dover", "lat": 51.1, "long": 1.3},
                {"stationReference": "E5678", "label": "Sheerness", "lat": 51.4, "long": 0.7},
            ]
        }),
    ])

    stations = await ea.list_stations()
    assert len(stations) == 2
    assert stations[0]["station_id"] == "E1234"
    assert stations[0]["provider"] == "ea"
    assert stations[0]["datum"] == "AOD"


async def test_list_stations_proximity(ea, mock_resilient, make_response):
    mock_resilient([
        make_response({
            "items": [
                {"stationReference": "E1234", "label": "Dover", "lat": 51.1, "long": 1.3},
                {"stationReference": "E9999", "label": "Far", "lat": 10.0, "long": 10.0},
            ]
        }),
    ])

    stations = await ea.list_stations(lat=51.1, lon=1.3, radius_km=10)
    assert len(stations) == 1
    assert "distance_km" in stations[0]


async def test_get_station_detail(ea, mock_resilient, make_response):
    mock_resilient([
        make_response({
            "items": {
                "stationReference": "E1234", "label": "Dover",
                "lat": 51.1, "long": 1.3, "dateOpened": "2000-01-01",
                "measures": [{"name": "Tidal Level"}],
            }
        }),
    ])

    detail = await ea.get_station_detail("E1234")
    assert detail["station_id"] == "E1234"
    assert detail["provider"] == "ea"


async def test_get_predictions_raises(ea):
    with pytest.raises(NotImplementedError, match="does not provide tidal predictions"):
        await ea.get_predictions("E1234")


async def test_get_observations(ea, mock_resilient, make_response):
    mock_resilient([
        make_response({
            "items": [
                {"dateTime": "2024-01-01T12:00:00Z", "value": 3.45},
                {"dateTime": "2024-01-01T12:15:00Z", "value": 3.50},
            ]
        }),
    ])

    obs = await ea.get_observations("E1234")
    assert len(obs) == 2
    assert obs[0]["time"] == "2024-01-01T12:00:00Z"
    assert obs[0]["value"] == 3.45


async def test_get_latest(ea, mock_resilient, make_response):
    mock_resilient([
        make_response({
            "items": [{"dateTime": "2024-01-01T12:00:00Z", "value": 3.45}]
        }),
    ])

    latest = await ea.get_latest("E1234")
    assert latest["value"] == 3.45
    assert latest["provider"] == "ea"


async def test_get_latest_no_data(ea, mock_resilient, make_response):
    mock_resilient([make_response({"items": []})])

    with pytest.raises(ValueError, match="No readings available"):
        await ea.get_latest("E1234")
