"""Tests for analysis tools."""

import json

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_tides.tools.analysis.api import register_analysis_tools


@pytest.fixture
def analysis_tools(mock_mcp, mock_manager):
    register_analysis_tools(mock_mcp, mock_manager)
    return mock_mcp


# ── tides_threshold_exceedance ─────────────────────────────────────────────


async def test_threshold_exceedance(analysis_tools, mock_manager):
    mock_manager.threshold_exceedance = AsyncMock(return_value={
        "groups": [
            {"period": "2023", "count": 15, "max_height": 1.8, "total_hours": 3.0},
            {"period": "2024", "count": 20, "max_height": 1.9, "total_hours": 4.5},
        ],
        "total_exceedances": 35,
        "total_hours_above": 7.5,
        "threshold": 1.5,
        "datum": "MLLW",
        "source": "predictions",
    })

    result = await analysis_tools.get_tool("tides_threshold_exceedance")(
        station_id="8454000", threshold=1.5,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    parsed = json.loads(result)
    assert parsed["total_exceedances"] == 35
    assert len(parsed["groups"]) == 2
    assert parsed["groups"][0]["period"] == "2023"


async def test_threshold_exceedance_with_trend(analysis_tools, mock_manager):
    mock_manager.threshold_exceedance = AsyncMock(return_value={
        "groups": [{"period": "2024", "count": 10, "max_height": 1.6, "total_hours": 2.0}],
        "total_exceedances": 10,
        "total_hours_above": 2.0,
        "trend": {"slope": 2.5, "intercept": -4990, "r_squared": 0.85},
    })

    result = await analysis_tools.get_tool("tides_threshold_exceedance")(
        station_id="8454000", threshold=1.5,
        start_date="2024-01-01", end_date="2024-12-31",
    )
    parsed = json.loads(result)
    assert parsed["trend"]["slope"] == 2.5
    assert parsed["trend"]["r_squared"] == 0.85


async def test_threshold_exceedance_error(analysis_tools, mock_manager):
    mock_manager.threshold_exceedance = AsyncMock(
        side_effect=ValueError("Not enough data"),
    )

    result = await analysis_tools.get_tool("tides_threshold_exceedance")(
        station_id="8454000", threshold=1.5,
        start_date="2024-01-01", end_date="2024-12-31",
    )
    parsed = json.loads(result)
    assert "Not enough data" in parsed["error"]


# ── tides_project_flooding ─────────────────────────────────────────────────


async def test_project_flooding(analysis_tools, mock_manager):
    mock_manager.project_flooding = AsyncMock(return_value={
        "station_name": "Providence",
        "threshold": 1.5,
        "datum": "MLLW",
        "baseline_year": 2024,
        "baseline_exceedances": 10,
        "projections": [
            {
                "year": 2050, "scenario": "low", "slr_mm": 150,
                "projected_exceedances": 20, "projected_hours": 4.0,
                "delta_from_baseline": 10,
            },
        ],
        "tipping_points": [
            {"scenario": "low", "double_year": 2045},
        ],
    })

    result = await analysis_tools.get_tool("tides_project_flooding")(
        station_id="8454000", threshold=1.5,
    )
    parsed = json.loads(result)
    assert parsed["baseline_exceedances"] == 10
    assert len(parsed["projections"]) == 1
    assert parsed["projections"][0]["year"] == 2050
    assert len(parsed["tipping_points"]) == 1
    assert parsed["tipping_points"][0]["double_year"] == 2045


async def test_project_flooding_error(analysis_tools, mock_manager):
    mock_manager.project_flooding = AsyncMock(
        side_effect=ValueError("Insufficient baseline data"),
    )

    result = await analysis_tools.get_tool("tides_project_flooding")(
        station_id="8454000", threshold=1.5,
    )
    parsed = json.loads(result)
    assert "Insufficient baseline" in parsed["error"]


# ── tides_harmonic_analysis ────────────────────────────────────────────────


async def test_harmonic_analysis(analysis_tools, mock_manager):
    mock_manager.harmonic_analysis = AsyncMock(return_value={
        "constituents": [
            {"name": "M2", "amplitude": 0.5, "phase": 123.4, "frequency": 0.0805, "snr": 50.0},
            {"name": "S2", "amplitude": 0.2, "phase": 45.0},
        ],
        "observation_days": 60,
        "mean_level": 0.1,
        "form_number": 0.15,
        "tidal_type": "semidiurnal",
        "residual_std": 0.05,
        "stored": True,
    })

    result = await analysis_tools.get_tool("tides_harmonic_analysis")(
        station_id="8454000", start_date="2024-01-01", end_date="2024-03-01",
    )
    parsed = json.loads(result)
    assert parsed["constituent_count"] == 2
    assert parsed["constituents"][0]["name"] == "M2"
    assert parsed["tidal_type"] == "semidiurnal"
    assert parsed["stored"] is True


async def test_harmonic_analysis_error(analysis_tools, mock_manager):
    mock_manager.harmonic_analysis = AsyncMock(
        side_effect=ImportError("utide not installed"),
    )

    result = await analysis_tools.get_tool("tides_harmonic_analysis")(
        station_id="8454000", start_date="2024-01-01", end_date="2024-03-01",
    )
    parsed = json.loads(result)
    assert "utide" in parsed["error"]


# ── tides_residual ─────────────────────────────────────────────────────────


async def test_residual(analysis_tools, mock_manager):
    mock_manager.compute_residual = AsyncMock(return_value={
        "reading_count": 100,
        "max_positive_surge": {"peak_datetime": "2024-01-01T12:00", "peak_residual": 0.5},
        "max_negative_surge": {"peak_datetime": "2024-01-02T06:00", "peak_residual": -0.3},
        "mean_residual": 0.01,
        "std_residual": 0.1,
        "surge_events": [
            {"peak_datetime": "2024-01-01T12:00", "peak_residual": 0.5,
             "start": "2024-01-01T10:00", "end": "2024-01-01T14:00",
             "duration_hours": 4.0},
        ],
        "residuals": [
            {"datetime": "2024-01-01T12:00", "observed": 1.5, "predicted": 1.0, "residual": 0.5},
        ],
    })

    result = await analysis_tools.get_tool("tides_residual")(
        station_id="8454000", start_date="2024-01-01", end_date="2024-01-31",
    )
    parsed = json.loads(result)
    assert parsed["reading_count"] == 100
    assert parsed["max_positive_surge"]["peak_residual"] == 0.5
    assert len(parsed["surge_events"]) == 1
    assert len(parsed["residuals"]) == 1


async def test_residual_error(analysis_tools, mock_manager):
    mock_manager.compute_residual = AsyncMock(
        side_effect=ValueError("No data"),
    )

    result = await analysis_tools.get_tool("tides_residual")(
        station_id="8454000", start_date="2024-01-01", end_date="2024-01-31",
    )
    parsed = json.loads(result)
    assert "No data" in parsed["error"]


# ── tides_sea_level_trend ──────────────────────────────────────────────────


async def test_sea_level_trend(analysis_tools, mock_manager):
    mock_manager.get_sea_level_trend = AsyncMock(return_value={
        "station_name": "Providence",
        "trend_mm_per_year": 3.5,
        "trend_uncertainty": 0.2,
        "first_year": 1930,
        "last_year": 2024,
        "record_length_years": 95,
        "data_source": "NOAA",
        "monthly_means": [
            {"year": 2024, "month": 6, "value": 0.15},
        ],
    })

    result = await analysis_tools.get_tool("tides_sea_level_trend")("8454000")
    parsed = json.loads(result)
    assert parsed["trend_mm_per_year"] == 3.5
    assert parsed["record_length_years"] == 95
    assert len(parsed["monthly_means"]) == 1


async def test_sea_level_trend_no_monthly(analysis_tools, mock_manager):
    mock_manager.get_sea_level_trend = AsyncMock(return_value={
        "station_name": "Test",
        "trend_mm_per_year": 2.0,
        "trend_uncertainty": 0.5,
        "first_year": 1950,
        "last_year": 2024,
        "record_length_years": 75,
    })

    result = await analysis_tools.get_tool("tides_sea_level_trend")("8454000")
    parsed = json.loads(result)
    assert parsed["monthly_means"] is None


async def test_sea_level_trend_error(analysis_tools, mock_manager):
    mock_manager.get_sea_level_trend = AsyncMock(
        side_effect=ValueError("No sea-level trend"),
    )

    result = await analysis_tools.get_tool("tides_sea_level_trend")("9999999")
    parsed = json.loads(result)
    assert "No sea-level trend" in parsed["error"]


# ── tides_extreme_levels ───────────────────────────────────────────────────


async def test_extreme_levels(analysis_tools, mock_manager):
    mock_manager.get_extreme_levels = AsyncMock(return_value={
        "top_ten_high": [
            {"date": "2012-10-29", "height": 2.87, "event_name": "Sandy"},
        ],
        "top_ten_low": [
            {"date": "1960-03-04", "height": -0.98},
        ],
        "datum": "MLLW",
    })

    result = await analysis_tools.get_tool("tides_extreme_levels")("8454000")
    parsed = json.loads(result)
    assert len(parsed["top_ten_high"]) == 1
    assert parsed["top_ten_high"][0]["event_name"] == "Sandy"
    assert len(parsed["top_ten_low"]) == 1
    assert parsed["datum"] == "MLLW"


async def test_extreme_levels_text(analysis_tools, mock_manager):
    mock_manager.get_extreme_levels = AsyncMock(return_value={
        "top_ten_high": [{"date": "2012-10-29", "height": 2.87, "event_name": "Sandy"}],
        "top_ten_low": [],
        "datum": "MLLW",
    })

    result = await analysis_tools.get_tool("tides_extreme_levels")(
        "8454000", output_mode="text",
    )
    assert "Sandy" in result
    assert "2012-10-29" in result


async def test_extreme_levels_error(analysis_tools, mock_manager):
    mock_manager.get_extreme_levels = AsyncMock(
        side_effect=ValueError("Extremes not available"),
    )

    result = await analysis_tools.get_tool("tides_extreme_levels")("8454000")
    parsed = json.loads(result)
    assert "Extremes not available" in parsed["error"]
