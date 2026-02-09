"""Tests for the UKHO Admiralty provider with mocked HTTP."""

import pytest

from chuk_mcp_tides.providers.ukho import UKHOProvider


@pytest.fixture
def ukho(monkeypatch):
    monkeypatch.setenv("UKHO_API_KEY", "test-key-123")
    return UKHOProvider()


@pytest.fixture
def ukho_no_key(monkeypatch):
    monkeypatch.delenv("UKHO_API_KEY", raising=False)
    return UKHOProvider()


async def test_list_stations(ukho, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "features": [
                        {
                            "properties": {"Id": "0001", "Name": "Aberdeen", "Country": "Scotland"},
                            "geometry": {"coordinates": [-2.08, 57.14]},
                        },
                    ]
                }
            ),
        ]
    )

    stations = await ukho.list_stations()
    assert len(stations) == 1
    assert stations[0]["station_id"] == "0001"
    assert stations[0]["provider"] == "ukho"
    assert stations[0]["datum"] == "CD"
    assert stations[0]["lon"] == -2.08
    assert stations[0]["lat"] == 57.14


async def test_list_stations_proximity(ukho, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "features": [
                        {
                            "properties": {"Id": "0001", "Name": "Near"},
                            "geometry": {"coordinates": [1.32, 51.12]},
                        },
                        {
                            "properties": {"Id": "0002", "Name": "Far"},
                            "geometry": {"coordinates": [10.0, 10.0]},
                        },
                    ]
                }
            ),
        ]
    )

    stations = await ukho.list_stations(lat=51.12, lon=1.32, radius_km=10)
    assert len(stations) == 1
    assert "distance_km" in stations[0]


async def test_get_station_detail(ukho, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "properties": {"Id": "0001", "Name": "Aberdeen", "Country": "Scotland"},
                    "geometry": {"coordinates": [-2.08, 57.14]},
                }
            ),
        ]
    )

    detail = await ukho.get_station_detail("0001")
    assert detail["station_id"] == "0001"
    assert detail["country"] == "Scotland"


async def test_get_predictions(ukho, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                [
                    {
                        "DateTime": "2024-01-01T06:00:00",
                        "EventType": "HighWater",
                        "Height": 4.5,
                        "IsApproximateTime": False,
                        "IsApproximateHeight": False,
                    },
                ]
            ),
        ]
    )

    preds = await ukho.get_predictions("0001")
    assert len(preds) == 1
    assert preds[0]["height"] == 4.5
    assert preds[0]["datum"] == "CD"


async def test_get_observations_raises(ukho):
    with pytest.raises(NotImplementedError):
        await ukho.get_observations("0001")


async def test_get_latest_raises(ukho):
    with pytest.raises(NotImplementedError):
        await ukho.get_latest("0001")


def test_requires_api_key(ukho_no_key):
    with pytest.raises(ValueError, match="UKHO API key not configured"):
        ukho_no_key._require_key()


def test_auth_headers(ukho):
    headers = ukho._auth_headers()
    assert headers["Ocp-Apim-Subscription-Key"] == "test-key-123"
