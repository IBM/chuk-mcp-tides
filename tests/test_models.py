"""Tests for Pydantic response models."""

import json

import pytest
from pydantic import ValidationError

from chuk_mcp_tides.models.responses import (
    CapabilitiesResponse,
    ConstituentInfo,
    ConstituentResult,
    DatumInfo,
    DatumInfoCapability,
    ErrorResponse,
    ExceedanceGroup,
    ExtremeEvent,
    ExtremeLevelsResponse,
    FloodCount,
    FloodDay,
    FloodingCalendarResponse,
    FloodOutlookResponse,
    FloodProjection,
    FloodProjectionNOAA,
    FloodProjectionResponse,
    FloodThresholdInfo,
    HarmonicAnalysisResponse,
    LatestReadingResponse,
    LocalPredictionResponse,
    MonthFloodSummary,
    MonthlyMean,
    NearestStation,
    NearestStationResponse,
    ObservationResponse,
    PredictionResponse,
    ProviderInfo,
    ProviderStatus,
    ResidualPoint,
    ResidualResponse,
    ScenarioInfo,
    SeaLevelTrendResponse,
    StationDetailResponse,
    StationListResponse,
    StationSummary,
    StatusResponse,
    SuccessResponse,
    SurgeEvent,
    ThresholdExceedanceResponse,
    TidalEvent,
    TippingPoint,
    TrendInfo,
    WaterLevelReading,
    WorkflowInfo,
    format_response,
)


# ── Common ──────────────────────────────────────────────────────────────────


def test_error_response():
    r = ErrorResponse(error="something broke")
    assert r.error == "something broke"
    assert r.to_text() == "Error: something broke"


def test_success_response():
    r = SuccessResponse(message="all good")
    assert r.message == "all good"
    assert r.to_text() == "all good"


def test_format_response_json():
    r = ErrorResponse(error="test")
    result = format_response(r, "json")
    parsed = json.loads(result)
    assert parsed["error"] == "test"


def test_format_response_text():
    r = ErrorResponse(error="test")
    result = format_response(r, "text")
    assert result == "Error: test"


def test_error_response_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ErrorResponse(error="test", extra_field="bad")


# ── Station Discovery ───────────────────────────────────────────────────────


def test_station_summary():
    s = StationSummary(station_id="8454000", name="Providence", lat=41.8, lon=-71.4)
    assert s.station_id == "8454000"
    assert s.station_type is None


def test_station_list_response_to_text():
    r = StationListResponse(
        provider="noaa",
        station_count=1,
        stations=[StationSummary(station_id="123", name="Test", lat=40.0, lon=-74.0)],
        message="Found 1 stations",
    )
    text = r.to_text()
    assert "Found 1 stations" in text
    assert "123" in text


def test_station_detail_response_to_text():
    r = StationDetailResponse(
        station_id="123",
        name="Test Station",
        provider="noaa",
        lat=40.0,
        lon=-74.0,
        message="Station detail",
        tidal_type="semidiurnal",
        datums=[DatumInfo(name="MLLW", value=0.0)],
        flood_thresholds=FloodThresholdInfo(minor=1.5, moderate=2.0, major=2.5),
        mean_sea_level_trend=3.5,
    )
    text = r.to_text()
    assert "Test Station" in text
    assert "semidiurnal" in text
    assert "minor=1.50m" in text
    assert "3.50 mm/yr" in text


def test_station_detail_minimal():
    r = StationDetailResponse(
        station_id="123",
        name="Minimal",
        provider="ea",
        lat=51.0,
        lon=-0.1,
        message="detail",
    )
    text = r.to_text()
    assert "Minimal" in text


def test_nearest_station_response_to_text():
    r = NearestStationResponse(
        search_location=[40.0, -74.0],
        stations=[
            NearestStation(
                station_id="123",
                name="Close",
                lat=40.01,
                lon=-74.01,
                provider="noaa",
                distance_km=1.5,
            ),
        ],
        message="Found 1 stations",
    )
    text = r.to_text()
    assert "1.5 km" in text
    assert "Close" in text


def test_datum_info():
    d = DatumInfo(name="MLLW", value=0.0, description="Mean Lower Low Water")
    assert d.name == "MLLW"


def test_constituent_info():
    c = ConstituentInfo(name="M2", amplitude=0.5, phase=123.4, speed=28.984)
    assert c.speed == 28.984


def test_flood_threshold_info():
    ft = FloodThresholdInfo(minor=1.5, moderate=2.0)
    assert ft.minor == 1.5
    assert ft.major is None


# ── Predictions ─────────────────────────────────────────────────────────────


def test_tidal_event():
    e = TidalEvent(datetime="2024-01-01T12:00:00", height=1.5, event_type="high")
    assert e.height == 1.5


def test_prediction_response_to_text():
    r = PredictionResponse(
        station_id="123",
        station_name="Test",
        provider="noaa",
        datum="MLLW",
        units="metric",
        start_date="2024-01-01",
        end_date="2024-01-07",
        interval="hilo",
        event_count=2,
        predictions=[
            TidalEvent(datetime="2024-01-01T06:00", height=1.5, event_type="high"),
            TidalEvent(datetime="2024-01-01T12:00", height=-0.3, event_type="low"),
        ],
        message="2 predictions",
    )
    text = r.to_text()
    assert "[high]" in text
    assert "[low]" in text


def test_prediction_response_truncation():
    preds = [TidalEvent(datetime=f"2024-01-{i:02d}T00:00", height=0.5) for i in range(1, 30)]
    r = PredictionResponse(
        station_id="123",
        station_name="Test",
        provider="noaa",
        datum="MLLW",
        units="metric",
        start_date="2024-01-01",
        end_date="2024-01-30",
        interval="hourly",
        event_count=29,
        predictions=preds,
        message="29 predictions",
    )
    text = r.to_text()
    assert "... and 9 more" in text


def test_local_prediction_response_to_text():
    r = LocalPredictionResponse(
        constituent_count=37,
        start_date="2024-01-01",
        end_date="2024-01-07",
        interval_minutes=60,
        event_count=168,
        predictions=[],
        highs_lows=[TidalEvent(datetime="2024-01-01T06:00", height=1.2, event_type="high")],
        message="Local prediction",
    )
    text = r.to_text()
    assert "37" in text
    assert "60 min" in text


# ── Observations ────────────────────────────────────────────────────────────


def test_water_level_reading():
    r = WaterLevelReading(datetime="2024-01-01T12:00:00", value=0.5, quality="v")
    assert r.value == 0.5


def test_observation_response_to_text():
    r = ObservationResponse(
        station_id="123",
        station_name="Test",
        provider="noaa",
        datum="MLLW",
        units="metric",
        product="water_level",
        reading_count=1,
        readings=[WaterLevelReading(datetime="2024-01-01T12:00", value=0.5)],
        message="1 observations",
    )
    text = r.to_text()
    assert "water_level" in text


def test_latest_reading_response_to_text():
    r = LatestReadingResponse(
        station_id="123",
        station_name="Test",
        datetime="2024-01-01T12:00",
        value=0.7,
        datum="MLLW",
        units="metric",
        tide_state="rising",
        next_high=TidalEvent(datetime="2024-01-01T18:00", height=1.5, event_type="high"),
        message="Latest",
    )
    text = r.to_text()
    assert "rising" in text
    assert "Next high" in text


# ── Analysis ────────────────────────────────────────────────────────────────


def test_exceedance_group():
    g = ExceedanceGroup(period="2024", count=15, max_height=1.8, total_hours=3.0)
    assert g.count == 15


def test_threshold_exceedance_response_to_text():
    r = ThresholdExceedanceResponse(
        station_id="123",
        threshold=1.5,
        datum="MLLW",
        source="predictions",
        total_exceedances=30,
        total_hours_above=6.0,
        groups=[ExceedanceGroup(period="2024", count=30, max_height=1.8, total_hours=6.0)],
        trend=TrendInfo(slope=2.5, intercept=-4990, r_squared=0.85),
        message="30 exceedances",
    )
    text = r.to_text()
    assert "30 exceedances" in text
    assert "0.850" in text


def test_flood_projection_response_to_text():
    r = FloodProjectionResponse(
        station_id="123",
        station_name="Test",
        threshold=1.5,
        datum="MLLW",
        baseline_year=2024,
        baseline_exceedances=10,
        projections=[
            FloodProjection(
                year=2050,
                scenario="low",
                slr_mm=150,
                projected_exceedances=20,
                projected_hours=4.0,
                delta_from_baseline=10,
            ),
        ],
        tipping_points=[TippingPoint(scenario="low", double_year=2045)],
        message="Flood projection",
    )
    text = r.to_text()
    assert "2050" in text
    assert "2x by 2045" in text


def test_harmonic_analysis_response_to_text():
    r = HarmonicAnalysisResponse(
        station_id="123",
        observation_days=60,
        constituent_count=2,
        constituents=[
            ConstituentResult(name="M2", amplitude=0.5, phase=123.4, snr=50.0),
            ConstituentResult(name="S2", amplitude=0.2, phase=45.0),
        ],
        mean_level=0.1,
        form_number=0.15,
        tidal_type="semidiurnal",
        residual_std=0.05,
        stored=True,
        message="Harmonic analysis",
    )
    text = r.to_text()
    assert "M2" in text
    assert "semidiurnal" in text
    assert "SNR=50.0" in text


def test_surge_event():
    s = SurgeEvent(peak_datetime="2024-01-01T12:00:00", peak_residual=0.5)
    assert s.start is None


def test_residual_response_to_text():
    r = ResidualResponse(
        station_id="123",
        reading_count=100,
        max_positive_surge=SurgeEvent(peak_datetime="2024-01-01", peak_residual=0.5),
        max_negative_surge=SurgeEvent(peak_datetime="2024-01-02", peak_residual=-0.3),
        mean_residual=0.01,
        std_residual=0.1,
        surge_events=[],
        residuals=[],
        message="Residual analysis",
    )
    text = r.to_text()
    assert "+0.500m" in text
    assert "-0.300m" in text


def test_sea_level_trend_response_to_text():
    r = SeaLevelTrendResponse(
        station_id="123",
        station_name="Test",
        trend_mm_per_year=3.5,
        trend_uncertainty=0.2,
        first_year=1900,
        last_year=2024,
        record_length_years=125,
        data_source="NOAA",
        message="Sea level trend",
    )
    text = r.to_text()
    assert "+3.50" in text
    assert "1900" in text


def test_extreme_levels_response_to_text():
    r = ExtremeLevelsResponse(
        station_id="123",
        top_ten_high=[ExtremeEvent(date="2012-10-29", height=2.87, event_name="Sandy")],
        top_ten_low=[ExtremeEvent(date="1960-03-04", height=-0.98)],
        datum="MLLW",
        message="Extreme levels",
    )
    text = r.to_text()
    assert "Sandy" in text
    assert "2012-10-29" in text


# ── Flood Risk ──────────────────────────────────────────────────────────────


def test_flood_outlook_response_to_text():
    r = FloodOutlookResponse(
        station_id="123",
        product="htf_annual",
        flood_threshold="minor",
        flood_level_m=1.04,
        counts=[FloodCount(period="2023", count=5)],
        projection=FloodProjectionNOAA(year=2025, expected=8, low=5, high=12),
        message="Flood outlook",
    )
    text = r.to_text()
    assert "5 flood events" in text
    assert "range: 5" in text


def test_flooding_calendar_response_to_text():
    r = FloodingCalendarResponse(
        station_id="123",
        year=2024,
        threshold=1.5,
        slr_offset_mm=50,
        datum="MLLW",
        total_flood_days=10,
        total_flood_hours=20.0,
        monthly_summary=[
            MonthFloodSummary(month=1, flood_days=3, max_height=1.8, total_hours=6.0),
        ],
        flood_days=[
            FloodDay(date="2024-01-15", peak_height=1.8, duration_hours=4.0, tides_above=2),
        ],
        message="Flooding calendar",
    )
    text = r.to_text()
    assert "10" in text
    assert "SLR offset" in text
    assert "Jan" in text


# ── Discovery ───────────────────────────────────────────────────────────────


def test_status_response():
    r = StatusResponse(
        server="chuk-mcp-tides",
        version="0.1.0",
        storage_provider="memory",
        providers=[
            ProviderStatus(name="NOAA", available=True, station_count=3000, auth_configured=True)
        ],
        harmonic_engine="utide",
        stored_constituents=0,
    )
    text = r.to_text()
    assert "NOAA" in text
    assert "available" in text


def test_capabilities_response_to_text():
    r = CapabilitiesResponse(
        server="chuk-mcp-tides",
        version="0.1.0",
        providers=[
            ProviderInfo(
                name="NOAA CO-OPS",
                short_name="noaa",
                coverage="US",
                auth_required=False,
                station_count=3000,
            ),
        ],
        datums=[DatumInfoCapability(name="MLLW", full_name="Mean Lower Low Water")],
        scenarios=[ScenarioInfo(name="low", rate_mm_yr=3.0, source="IPCC")],
        tool_count=17,
        cross_server_workflows=[
            WorkflowInfo(name="Test", description="A test", servers=["a", "b"]),
        ],
    )
    text = r.to_text()
    assert "17" in text
    assert "NOAA CO-OPS" in text
    assert "MLLW" in text


def test_monthly_mean():
    m = MonthlyMean(year=2024, month=6, value=0.15)
    assert m.year == 2024


def test_residual_point():
    r = ResidualPoint(datetime="2024-01-01", observed=1.0, predicted=0.9, residual=0.1)
    assert r.residual == 0.1
