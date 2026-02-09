"""Tests for the NOAA CO-OPS provider with mocked HTTP."""

import pytest

from chuk_mcp_tides.providers.noaa import NOAAProvider


@pytest.fixture
def noaa():
    return NOAAProvider()


async def test_list_stations(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "stations": [
                        {
                            "id": "8454000",
                            "name": "Providence",
                            "lat": 41.8,
                            "lng": -71.4,
                            "state": "RI",
                        },
                        {
                            "id": "8510560",
                            "name": "Montauk",
                            "lat": 41.0,
                            "lng": -71.9,
                            "state": "NY",
                        },
                    ]
                }
            ),
        ]
    )

    stations = await noaa.list_stations()
    assert len(stations) == 2
    assert stations[0]["station_id"] == "8454000"
    assert stations[0]["provider"] == "noaa"


async def test_list_stations_region_filter(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "stations": [
                        {
                            "id": "8454000",
                            "name": "Providence",
                            "lat": 41.8,
                            "lng": -71.4,
                            "state": "RI",
                        },
                        {
                            "id": "8510560",
                            "name": "Montauk",
                            "lat": 41.0,
                            "lng": -71.9,
                            "state": "NY",
                        },
                    ]
                }
            ),
        ]
    )

    stations = await noaa.list_stations(region="NY")
    assert len(stations) == 1
    assert stations[0]["station_id"] == "8510560"


async def test_list_stations_proximity_filter(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "stations": [
                        {"id": "8454000", "name": "Providence", "lat": 41.8, "lng": -71.4},
                        {"id": "9999999", "name": "Far Away", "lat": 10.0, "lng": 10.0},
                    ]
                }
            ),
        ]
    )

    stations = await noaa.list_stations(lat=41.8, lon=-71.4, radius_km=10)
    assert len(stations) == 1
    assert "distance_km" in stations[0]


async def test_list_stations_max_results(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "stations": [
                        {"id": str(i), "name": f"S{i}", "lat": 40.0, "lng": -74.0}
                        for i in range(10)
                    ]
                }
            ),
        ]
    )

    stations = await noaa.list_stations(max_results=3)
    assert len(stations) == 3


async def test_get_station_detail(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "stations": [
                        {
                            "id": "8454000",
                            "name": "Providence",
                            "lat": 41.8,
                            "lng": -71.4,
                            "datums": {"datums": [{"name": "MLLW", "value": 0.0}]},
                            "harmonicConstituents": {
                                "HarmonicConstituents": [
                                    {
                                        "name": "M2",
                                        "amplitude": 0.5,
                                        "phase_GMT": 123.4,
                                        "speed": 28.984,
                                    },
                                ]
                            },
                            "floodlevels": {
                                "floodlevels": [{"minor": 1.5, "moderate": 2.0, "major": 2.5}]
                            },
                            "sensors": {"sensors": [{"name": "Water Level"}]},
                            "products": {"products": [{"name": "Predictions"}]},
                        }
                    ],
                }
            ),
        ]
    )

    detail = await noaa.get_station_detail("8454000")
    assert detail["station_id"] == "8454000"
    assert len(detail["datums"]) == 1
    assert detail["harmonic_constituents"][0]["name"] == "M2"
    assert detail["flood_thresholds"]["minor"] == 1.5
    assert "Water Level" in detail["sensors"]


async def test_get_predictions(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "predictions": [
                        {"t": "2024-01-01 06:00", "v": "1.500", "type": "H"},
                        {"t": "2024-01-01 12:00", "v": "-0.300", "type": "L"},
                    ]
                }
            ),
        ]
    )

    preds = await noaa.get_predictions("8454000", start_date="20240101", end_date="20240107")
    assert len(preds) == 2
    assert preds[0]["height"] == 1.5
    assert preds[0]["event_type"] == "high"
    assert preds[1]["event_type"] == "low"


async def test_get_observations_water_level(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {"data": [{"t": "2024-01-01 12:00", "v": "0.500", "q": "v", "f": "0,0,0,0"}]}
            ),
        ]
    )

    obs = await noaa.get_observations("8454000", start_date="20240101")
    assert len(obs) == 1
    assert obs[0]["value"] == 0.5


async def test_get_observations_empty_value_skipped(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "data": [
                        {"t": "2024-01-01 12:00", "v": ""},
                        {"t": "2024-01-01 12:06", "v": "0.5"},
                    ]
                }
            ),
        ]
    )

    obs = await noaa.get_observations("8454000")
    assert len(obs) == 1


async def test_get_latest(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response({"data": [{"t": "2024-01-01 12:00", "v": "0.750", "q": "v"}]}),
        ]
    )

    latest = await noaa.get_latest("8454000")
    assert latest["value"] == 0.75
    assert latest["datum"] == "MLLW"


async def test_get_latest_no_data(noaa, mock_resilient, make_response):
    mock_resilient([make_response({"data": []})])

    with pytest.raises(ValueError, match="No recent observations"):
        await noaa.get_latest("8454000")


async def test_get_extremes(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "topTenWaterLevels": [
                        {
                            "peakDate": "2012-10-29",
                            "height": 2.87,
                            "event": "Sandy",
                            "datum": "MLLW",
                        },
                        {
                            "peakDate": "1992-12-11",
                            "height": 2.10,
                            "event": "Nor'easter",
                            "datum": "MLLW",
                        },
                    ]
                }
            ),
        ]
    )

    extremes = await noaa.get_extremes("8454000")
    assert len(extremes["top_ten_high"]) == 2
    assert extremes["top_ten_high"][0]["event_name"] == "Sandy"
    assert extremes["top_ten_high"][0]["height"] == 2.87


async def test_get_sea_level_trend(noaa, mock_resilient, make_response):
    # Real API returns inches/decade; parser converts ×2.54 to mm/year
    # 1.378 in/decade * 2.54 = 3.50 mm/year
    mock_resilient(
        [
            make_response(
                {
                    "SeaLvlTrends": [
                        {
                            "stationId": "8454000",
                            "stationName": "Providence",
                            "trend": 1.378,
                            "trendError": 0.079,
                            "startDate": "01/01/1930",
                            "endDate": "12/31/2024",
                        }
                    ]
                }
            ),
        ]
    )

    trend = await noaa.get_sea_level_trend("8454000")
    assert trend["trend_mm_per_year"] == 3.5
    assert trend["record_length_years"] == 95


async def test_get_sea_level_trend_not_found(noaa, mock_resilient, make_response):
    mock_resilient([make_response({"SeaLvlTrends": []})])

    with pytest.raises(ValueError, match="No sea-level trend"):
        await noaa.get_sea_level_trend("9999999")


async def test_get_flood_outlook(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "AnnualFloodCount": [
                        {"year": 2022, "minCount": 3, "modCount": 1, "majCount": 0},
                        {"year": 2023, "minCount": 5, "modCount": 2, "majCount": None},
                    ],
                    "floodLevel": 1.04,
                }
            ),
        ]
    )

    outlook = await noaa.get_flood_outlook("8454000", threshold="minor")
    assert len(outlook["counts"]) == 2
    assert outlook["counts"][0]["count"] == 3
    assert outlook["counts"][1]["count"] == 5
    assert outlook["flood_level_m"] == 1.04


async def test_get_flood_outlook_moderate(noaa, mock_resilient, make_response):
    mock_resilient(
        [
            make_response(
                {
                    "AnnualFloodCount": [
                        {"year": 2023, "minCount": 5, "modCount": 2, "majCount": 0},
                    ],
                }
            ),
        ]
    )

    outlook = await noaa.get_flood_outlook("8454000", threshold="moderate")
    assert outlook["counts"][0]["count"] == 2


def test_check_error_dict():
    with pytest.raises(ValueError, match="NOAA API error"):
        NOAAProvider._check_error({"error": {"message": "Not found"}})


def test_check_error_string():
    with pytest.raises(ValueError, match="NOAA API error"):
        NOAAProvider._check_error({"error": "Bad"})


def test_check_error_no_error():
    NOAAProvider._check_error({"data": []})


def test_resolve_interval():
    assert NOAAProvider._resolve_interval("hilo") == "hilo"
    assert NOAAProvider._resolve_interval("6min") == "6"
    assert NOAAProvider._resolve_interval(None) == "hilo"


def test_resolve_units():
    assert NOAAProvider._resolve_units("metric") == "metric"
    assert NOAAProvider._resolve_units(None) == "metric"
