"""Tests for TideManager."""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from chuk_mcp_tides.constants import TideProvider
from chuk_mcp_tides.core.tide_manager import TideManager


# ── Provider resolution ──────────────────────────────────────────────────


def test_default_provider(tide_manager: TideManager):
    assert tide_manager.default_provider == TideProvider.NOAA


def test_default_provider_custom():
    mgr = TideManager(default_provider=TideProvider.EA)
    assert mgr.default_provider == TideProvider.EA


def test_default_provider_from_env(monkeypatch):
    monkeypatch.setenv("TIDES_DEFAULT_PROVIDER", "ukho")
    mgr = TideManager()
    assert mgr.default_provider == TideProvider.UKHO


def test_default_provider_from_env_invalid(monkeypatch):
    monkeypatch.setenv("TIDES_DEFAULT_PROVIDER", "bogus")
    mgr = TideManager()
    assert mgr.default_provider == TideProvider.NOAA


def test_resolve_provider_none(tide_manager: TideManager):
    assert tide_manager.resolve_provider(None) == TideProvider.NOAA


def test_resolve_provider_valid(tide_manager: TideManager):
    assert tide_manager.resolve_provider("ea") == TideProvider.EA
    assert tide_manager.resolve_provider("ukho") == TideProvider.UKHO
    assert tide_manager.resolve_provider("local") == TideProvider.LOCAL


def test_resolve_provider_all(tide_manager: TideManager):
    assert tide_manager.resolve_provider("all") == TideProvider.NOAA


def test_resolve_provider_invalid(tide_manager: TideManager):
    assert tide_manager.resolve_provider("invalid") == TideProvider.NOAA


def test_resolve_provider_case_insensitive(tide_manager: TideManager):
    assert tide_manager.resolve_provider("NOAA") == TideProvider.NOAA
    assert tide_manager.resolve_provider("Ea") == TideProvider.EA


def test_default_datum(tide_manager: TideManager):
    assert tide_manager.default_datum(TideProvider.NOAA) == "MLLW"
    assert tide_manager.default_datum(TideProvider.UKHO) == "CD"
    assert tide_manager.default_datum(TideProvider.EA) == "AOD"


# ── Caching ──────────────────────────────────────────────────────────────


def test_cache_set_and_get(tide_manager: TideManager):
    tide_manager.set_cached("key1", {"data": 42})
    result = tide_manager.get_cached("key1")
    assert result == {"data": 42}


def test_cache_miss(tide_manager: TideManager):
    result = tide_manager.get_cached("nonexistent")
    assert result is None


def test_cache_key(tide_manager: TideManager):
    key = tide_manager._cache_key("stations", "noaa", "41.8", "-71.4")
    assert key == "stations|noaa|41.8|-71.4"


def test_cache_ttl_expiry(tide_manager: TideManager):
    """Expired entries should return None."""
    tide_manager._cache_ttl = 0  # zero TTL = always expired
    tide_manager.set_cached("key1", {"data": 42})
    time.sleep(0.01)
    assert tide_manager.get_cached("key1") is None


def test_cache_eviction():
    """Cache should evict oldest entries when full."""
    mgr = TideManager()
    mgr._cache_ttl = 9999
    # Fill to max
    for i in range(510):
        mgr.set_cached(f"key_{i}", i)
    # Oldest should be evicted
    assert mgr.get_cached("key_0") is None
    # Recent should still be there
    assert mgr.get_cached("key_509") == 509


# ── determine_tide_state ─────────────────────────────────────────────────


def test_determine_tide_state_rising():
    mgr = TideManager()
    preds = [
        {"datetime": "2024-01-01T12:00", "event_type": "high", "height": 1.5},
        {"datetime": "2024-01-01T18:00", "event_type": "low", "height": -0.3},
    ]
    state, nh, nl = mgr.determine_tide_state(0.5, preds, "2024-01-01T06:00")
    assert state == "rising"
    assert nh["event_type"] == "high"
    assert nl["event_type"] == "low"


def test_determine_tide_state_falling():
    mgr = TideManager()
    preds = [
        {"datetime": "2024-01-01T12:00", "event_type": "low", "height": -0.3},
        {"datetime": "2024-01-01T18:00", "event_type": "high", "height": 1.5},
    ]
    state, nh, nl = mgr.determine_tide_state(0.5, preds, "2024-01-01T06:00")
    assert state == "falling"


def test_determine_tide_state_only_high():
    mgr = TideManager()
    preds = [
        {"datetime": "2024-01-01T12:00", "event_type": "high", "height": 1.5},
    ]
    state, nh, nl = mgr.determine_tide_state(0.5, preds, "2024-01-01T06:00")
    assert state == "rising"
    assert nl is None


def test_determine_tide_state_only_low():
    mgr = TideManager()
    preds = [
        {"datetime": "2024-01-01T12:00", "event_type": "low", "height": -0.3},
    ]
    state, nh, nl = mgr.determine_tide_state(0.5, preds, "2024-01-01T06:00")
    assert state == "falling"
    assert nh is None


def test_determine_tide_state_no_future():
    mgr = TideManager()
    preds = [
        {"datetime": "2024-01-01T06:00", "event_type": "high", "height": 1.5},
    ]
    state, nh, nl = mgr.determine_tide_state(0.5, preds, "2024-01-01T12:00")
    assert state == "unknown"
    assert nh is None
    assert nl is None


def test_determine_tide_state_empty():
    mgr = TideManager()
    state, nh, nl = mgr.determine_tide_state(0.5, [], "2024-01-01T12:00")
    assert state == "unknown"


# ── _count_above ─────────────────────────────────────────────────────────


def test_count_above():
    mgr = TideManager()
    events = [
        {"height": 1.0},
        {"height": 2.0},
        {"height": 0.5},
        {"value": 1.8},
        {"height": None},
    ]
    assert mgr._count_above(events, 1.5) == 2


def test_count_above_empty():
    mgr = TideManager()
    assert mgr._count_above([], 1.0) == 0


# ── _compute_exceedance ─────────────────────────────────────────────────


def test_compute_exceedance_year_grouping():
    mgr = TideManager()
    events = [
        {"datetime": "2022-06-15T12:00", "height": 2.0},
        {"datetime": "2022-08-01T06:00", "height": 1.8},
        {"datetime": "2023-03-10T12:00", "height": 2.5},
        {"datetime": "2023-06-15T12:00", "height": 1.2},  # below threshold
    ]
    result = mgr._compute_exceedance(
        events,
        1.5,
        "MLLW",
        "predictions",
        "year",
        "2022-01-01",
        "2023-12-31",
    )
    assert result["total_exceedances"] == 3
    assert len(result["groups"]) == 2
    assert result["groups"][0]["period"] == "2022"
    assert result["groups"][0]["count"] == 2
    assert result["groups"][1]["period"] == "2023"
    assert result["groups"][1]["count"] == 1


def test_compute_exceedance_month_grouping():
    mgr = TideManager()
    events = [
        {"datetime": "2024-01-15T12:00", "height": 2.0},
        {"datetime": "2024-01-20T12:00", "height": 1.8},
        {"datetime": "2024-02-10T12:00", "height": 2.1},
    ]
    result = mgr._compute_exceedance(
        events,
        1.5,
        "MLLW",
        "predictions",
        "month",
        "2024-01-01",
        "2024-12-31",
    )
    assert len(result["groups"]) == 2
    assert result["groups"][0]["period"] == "2024-01"
    assert result["groups"][0]["count"] == 2


def test_compute_exceedance_season_grouping():
    mgr = TideManager()
    events = [
        {"datetime": "2024-01-15T12:00", "height": 2.0},  # Winter
        {"datetime": "2024-04-15T12:00", "height": 2.0},  # Spring
        {"datetime": "2024-07-15T12:00", "height": 2.0},  # Summer
        {"datetime": "2024-10-15T12:00", "height": 2.0},  # Autumn
    ]
    result = mgr._compute_exceedance(
        events,
        1.5,
        "MLLW",
        "predictions",
        "season",
        "2024-01-01",
        "2024-12-31",
    )
    assert len(result["groups"]) == 4
    periods = [g["period"] for g in result["groups"]]
    assert any("Winter" in p for p in periods)
    assert any("Spring" in p for p in periods)
    assert any("Summer" in p for p in periods)
    assert any("Autumn" in p for p in periods)


def test_compute_exceedance_no_events():
    mgr = TideManager()
    result = mgr._compute_exceedance(
        [],
        1.5,
        "MLLW",
        "predictions",
        "year",
        "2024-01-01",
        "2024-12-31",
    )
    assert result["total_exceedances"] == 0
    assert result["groups"] == []
    assert result["trend"] is None


def test_compute_exceedance_with_value_key():
    """Events from observations use 'value' instead of 'height'."""
    mgr = TideManager()
    events = [
        {"datetime": "2024-01-15T12:00", "value": 2.0},
        {"datetime": "2024-01-16T12:00", "value": 1.0},
    ]
    result = mgr._compute_exceedance(
        events,
        1.5,
        "MLLW",
        "observations",
        "year",
        "2024-01-01",
        "2024-12-31",
    )
    assert result["total_exceedances"] == 1


def test_compute_exceedance_trend_computed():
    """Trend should be computed when there are >2 year groups."""
    mgr = TideManager()
    events = []
    for year in range(2020, 2025):
        for i in range(year - 2019):  # increasing count per year
            events.append({"datetime": f"{year}-06-15T12:00", "height": 2.0})
    result = mgr._compute_exceedance(
        events,
        1.5,
        "MLLW",
        "predictions",
        "year",
        "2020-01-01",
        "2024-12-31",
    )
    assert result["trend"] is not None
    assert result["trend"]["slope"] > 0  # increasing trend


# ── Async dispatch methods with mocked providers ─────────────────────────


@pytest.fixture
def mgr_with_mock_provider():
    """TideManager with a mocked NOAA provider injected."""
    mgr = TideManager()
    mock_provider = AsyncMock()
    mgr._providers[TideProvider.NOAA] = mock_provider
    return mgr, mock_provider


async def test_list_stations_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.list_stations = AsyncMock(
        return_value=[
            {"station_id": "8454000", "name": "Providence", "lat": 41.8, "lon": -71.4},
        ]
    )

    result = await mgr.list_stations(TideProvider.NOAA)
    assert len(result) == 1
    assert result[0]["station_id"] == "8454000"


async def test_list_stations_uses_cache(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.list_stations = AsyncMock(return_value=[{"station_id": "123"}])

    result1 = await mgr.list_stations(TideProvider.NOAA)
    result2 = await mgr.list_stations(TideProvider.NOAA)
    assert result1 == result2
    mock_prov.list_stations.assert_called_once()  # second call hit cache


async def test_get_station_detail_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_station_detail = AsyncMock(
        return_value={
            "station_id": "8454000",
            "name": "Providence",
        }
    )

    result = await mgr.get_station_detail("8454000", TideProvider.NOAA)
    assert result["name"] == "Providence"


async def test_find_nearest_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.list_stations = AsyncMock(
        return_value=[
            {"station_id": "8454000", "name": "Providence", "lat": 41.8, "lon": -71.4},
        ]
    )

    result = await mgr.find_nearest(41.8, -71.4, providers=[TideProvider.NOAA])
    assert len(result) == 1
    assert "distance_km" in result[0]


async def test_find_nearest_skips_failing_provider():
    mgr = TideManager()
    good = AsyncMock()
    good.list_stations = AsyncMock(
        return_value=[
            {"station_id": "1", "name": "Good", "lat": 41.8, "lon": -71.4},
        ]
    )
    bad = AsyncMock()
    bad.list_stations = AsyncMock(side_effect=RuntimeError("fail"))
    mgr._providers[TideProvider.NOAA] = good
    mgr._providers[TideProvider.EA] = bad

    result = await mgr.find_nearest(41.8, -71.4, providers=[TideProvider.NOAA, TideProvider.EA])
    assert len(result) == 1


async def test_get_predictions_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_predictions = AsyncMock(
        return_value=[
            {"datetime": "2024-01-01T06:00", "height": 1.5, "event_type": "high"},
        ]
    )

    result = await mgr.get_predictions(
        "8454000",
        TideProvider.NOAA,
        start_date="2024-01-01",
        end_date="2024-01-07",
    )
    assert result["station_id"] == "8454000"
    assert result["provider"] == "noaa"
    assert len(result["predictions"]) == 1


async def test_get_observations_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_observations = AsyncMock(
        return_value=[
            {"datetime": "2024-01-01T12:00", "value": 0.5},
        ]
    )

    result = await mgr.get_observations(
        "8454000",
        TideProvider.NOAA,
        start_date="2024-01-01",
    )
    assert result["station_id"] == "8454000"
    assert len(result["readings"]) == 1


async def test_get_latest_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_latest = AsyncMock(
        return_value={
            "datetime": "2024-01-01T12:00",
            "value": 0.5,
        }
    )

    result = await mgr.get_latest("8454000", TideProvider.NOAA)
    assert result["value"] == 0.5


async def test_get_sea_level_trend_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_sea_level_trend = AsyncMock(
        return_value={
            "trend_mm_per_year": 3.5,
        }
    )

    result = await mgr.get_sea_level_trend("8454000", TideProvider.NOAA)
    assert result["trend_mm_per_year"] == 3.5


async def test_get_sea_level_trend_not_implemented(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    del mock_prov.get_sea_level_trend  # remove the attribute

    with pytest.raises(NotImplementedError):
        await mgr.get_sea_level_trend("8454000", TideProvider.NOAA)


async def test_get_extreme_levels_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_extremes = AsyncMock(
        return_value={
            "top_ten_high": [{"date": "2012-10-29", "height": 2.87}],
            "top_ten_low": [],
        }
    )

    result = await mgr.get_extreme_levels("8454000", TideProvider.NOAA)
    assert len(result["top_ten_high"]) == 1


async def test_get_extreme_levels_not_implemented():
    mgr = TideManager()
    mock_prov = MagicMock()
    del mock_prov.get_extremes
    mgr._providers[TideProvider.NOAA] = mock_prov

    with pytest.raises(NotImplementedError):
        await mgr.get_extreme_levels("8454000", TideProvider.NOAA)


async def test_get_flood_outlook_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_flood_outlook = AsyncMock(
        return_value={
            "counts": [{"period": "2023", "count": 5}],
            "flood_level_m": 1.04,
        }
    )

    result = await mgr.get_flood_outlook("8454000")
    assert result["flood_level_m"] == 1.04


async def test_get_flood_outlook_not_implemented():
    mgr = TideManager()
    mock_prov = MagicMock()
    del mock_prov.get_flood_outlook
    mgr._providers[TideProvider.NOAA] = mock_prov

    with pytest.raises(NotImplementedError):
        await mgr.get_flood_outlook("8454000")


async def test_flooding_calendar_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_predictions = AsyncMock(
        return_value=[
            {"datetime": "2024-01-15T06:00", "height": 2.0, "event_type": "high"},
            {"datetime": "2024-01-15T12:00", "height": -0.3, "event_type": "low"},
            {"datetime": "2024-02-10T06:00", "height": 1.8, "event_type": "high"},
        ]
    )

    result = await mgr.flooding_calendar(
        "8454000",
        1.5,
        TideProvider.NOAA,
        year=2024,
    )
    assert result["year"] == 2024
    assert result["total_flood_days"] >= 1
    assert len(result["monthly_summary"]) == 12
    assert result["monthly_summary"][0]["flood_days"] >= 1  # January


async def test_flooding_calendar_slr_offset(mgr_with_mock_provider):
    """SLR offset should lower the effective threshold."""
    mgr, mock_prov = mgr_with_mock_provider
    # Height of 1.45 is below 1.5 threshold but above 1.5 - 100mm/1000 = 1.4
    mock_prov.get_predictions = AsyncMock(
        return_value=[
            {"datetime": "2024-06-15T06:00", "height": 1.45, "event_type": "high"},
        ]
    )

    result = await mgr.flooding_calendar(
        "8454000",
        1.5,
        TideProvider.NOAA,
        year=2024,
        slr_offset_mm=100,
    )
    assert result["total_flood_days"] == 1


async def test_threshold_exceedance_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_predictions = AsyncMock(
        return_value=[
            {"datetime": "2024-06-15T12:00", "height": 2.0, "event_type": "high"},
            {"datetime": "2024-06-15T18:00", "height": 1.0, "event_type": "low"},
        ]
    )

    result = await mgr.threshold_exceedance(
        "8454000",
        1.5,
        "2024-01-01",
        "2024-12-31",
        TideProvider.NOAA,
    )
    assert result["total_exceedances"] == 1
    assert result["threshold"] == 1.5


async def test_compute_residual_dispatch(mgr_with_mock_provider):
    mgr, mock_prov = mgr_with_mock_provider
    mock_prov.get_observations = AsyncMock(
        return_value=[
            {"datetime": "2024-01-01T12:00", "value": 1.5},
            {"datetime": "2024-01-01T12:06", "value": 1.6},
        ]
    )
    mock_prov.get_predictions = AsyncMock(
        return_value=[
            {"datetime": "2024-01-01T12:00", "height": 1.2},
            {"datetime": "2024-01-01T12:06", "height": 1.3},
        ]
    )

    result = await mgr.compute_residual(
        "8454000",
        "2024-01-01",
        "2024-01-02",
        TideProvider.NOAA,
    )
    assert result["reading_count"] == 2
    assert result["max_positive_surge"]["peak_residual"] > 0
    assert len(result["residuals"]) == 2
