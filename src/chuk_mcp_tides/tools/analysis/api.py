"""
Analysis tools for chuk-mcp-tides.

Tools: tides_threshold_exceedance, tides_project_flooding,
       tides_harmonic_analysis, tides_residual,
       tides_sea_level_trend, tides_extreme_levels
"""

import logging
from typing import Any

from ...constants import DEFAULT_PROJECTION_SCENARIOS, DEFAULT_PROJECTION_YEARS
from ...core.tide_manager import TideManager
from ...models.responses import (
    ConstituentResult,
    ErrorResponse,
    ExceedanceGroup,
    ExtremeEvent,
    ExtremeLevelsResponse,
    FloodProjection,
    FloodProjectionResponse,
    HarmonicAnalysisResponse,
    MonthlyMean,
    ResidualPoint,
    ResidualResponse,
    SeaLevelTrendResponse,
    SurgeEvent,
    ThresholdExceedanceResponse,
    TippingPoint,
    TrendInfo,
    format_response,
)

logger = logging.getLogger(__name__)


def register_analysis_tools(mcp: Any, manager: TideManager) -> None:
    """Register analysis tools with the MCP server."""

    @mcp.tool
    async def tides_threshold_exceedance(
        station_id: str,
        threshold: float,
        start_date: str,
        end_date: str,
        source: str = "predictions",
        datum: str | None = None,
        provider: str | None = None,
        group_by: str = "year",
        output_mode: str = "json",
    ) -> str:
        """Count how many times water levels exceed a threshold over a period."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.threshold_exceedance(
                station_id,
                threshold,
                start_date,
                end_date,
                tp,
                source=source,
                datum=datum,
                group_by=group_by,
            )

            groups = [
                ExceedanceGroup(
                    period=g["period"],
                    count=g["count"],
                    max_height=g["max_height"],
                    total_hours=g["total_hours"],
                )
                for g in raw.get("groups", [])
            ]

            trend = None
            if raw.get("trend"):
                t = raw["trend"]
                trend = TrendInfo(
                    slope=t["slope"],
                    intercept=t["intercept"],
                    r_squared=t["r_squared"],
                )

            response = ThresholdExceedanceResponse(
                station_id=station_id,
                threshold=raw.get("threshold", threshold),
                datum=raw.get("datum", ""),
                source=raw.get("source", source),
                total_exceedances=raw.get("total_exceedances", 0),
                total_hours_above=raw.get("total_hours_above", 0.0),
                groups=groups,
                trend=trend,
                message=(f"{raw.get('total_exceedances', 0)} exceedances above {threshold:.2f}m"),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_project_flooding(
        station_id: str,
        threshold: float,
        years: list[int] | None = None,
        scenarios: list[str] | None = None,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Project future flooding frequency under sea level rise scenarios."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.project_flooding(
                station_id,
                threshold,
                tp,
                years=years or DEFAULT_PROJECTION_YEARS,
                scenarios=scenarios or DEFAULT_PROJECTION_SCENARIOS,
                datum=datum,
            )

            projections = [
                FloodProjection(
                    year=p["year"],
                    scenario=p["scenario"],
                    slr_mm=p["slr_mm"],
                    projected_exceedances=p["projected_exceedances"],
                    projected_hours=p["projected_hours"],
                    delta_from_baseline=p["delta_from_baseline"],
                )
                for p in raw.get("projections", [])
            ]

            tipping_points = [
                TippingPoint(
                    scenario=t["scenario"],
                    double_year=t.get("double_year"),
                    tenfold_year=t.get("tenfold_year"),
                    daily_year=t.get("daily_year"),
                )
                for t in raw.get("tipping_points", [])
            ]

            response = FloodProjectionResponse(
                station_id=station_id,
                station_name=raw.get("station_name", station_id),
                threshold=raw.get("threshold", threshold),
                datum=raw.get("datum", ""),
                baseline_year=raw.get("baseline_year", 0),
                baseline_exceedances=raw.get("baseline_exceedances", 0),
                projections=projections,
                tipping_points=tipping_points,
                message=(
                    f"Flood projection for {raw.get('station_name', station_id)} "
                    f"at {threshold:.2f}m threshold"
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_harmonic_analysis(
        station_id: str,
        start_date: str,
        end_date: str,
        provider: str | None = None,
        store_constituents: bool = True,
        output_mode: str = "json",
    ) -> str:
        """Fit harmonic constituents to an observed water level time series."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.harmonic_analysis(
                station_id,
                start_date,
                end_date,
                tp,
                store_constituents=store_constituents,
            )

            constituents = [
                ConstituentResult(
                    name=c["name"],
                    amplitude=c["amplitude"],
                    phase=c["phase"],
                    frequency=c.get("frequency"),
                    snr=c.get("snr"),
                )
                for c in raw.get("constituents", [])
            ]

            response = HarmonicAnalysisResponse(
                station_id=station_id,
                observation_days=raw.get("observation_days", 0),
                constituent_count=len(constituents),
                constituents=constituents,
                mean_level=raw.get("mean_level", 0.0),
                form_number=raw.get("form_number", 0.0),
                tidal_type=raw.get("tidal_type", "unknown"),
                residual_std=raw.get("residual_std", 0.0),
                stored=raw.get("stored", False),
                message=f"Harmonic analysis: {len(constituents)} constituents resolved",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_residual(
        station_id: str,
        start_date: str,
        end_date: str,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Compute the non-tidal residual (observed minus predicted)."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.compute_residual(
                station_id,
                start_date,
                end_date,
                tp,
                datum=datum,
            )

            max_pos = raw.get("max_positive_surge", {})
            max_neg = raw.get("max_negative_surge", {})

            surge_events = [
                SurgeEvent(
                    start=s.get("start"),
                    end=s.get("end"),
                    peak_datetime=s["peak_datetime"],
                    peak_residual=s["peak_residual"],
                    duration_hours=s.get("duration_hours"),
                )
                for s in raw.get("surge_events", [])
            ]

            residuals = [
                ResidualPoint(
                    datetime=r["datetime"],
                    observed=r["observed"],
                    predicted=r["predicted"],
                    residual=r["residual"],
                )
                for r in raw.get("residuals", [])
            ]

            response = ResidualResponse(
                station_id=station_id,
                reading_count=raw.get("reading_count", 0),
                max_positive_surge=SurgeEvent(
                    peak_datetime=max_pos.get("peak_datetime", ""),
                    peak_residual=max_pos.get("peak_residual", 0.0),
                ),
                max_negative_surge=SurgeEvent(
                    peak_datetime=max_neg.get("peak_datetime", ""),
                    peak_residual=max_neg.get("peak_residual", 0.0),
                ),
                mean_residual=raw.get("mean_residual", 0.0),
                std_residual=raw.get("std_residual", 0.0),
                surge_events=surge_events,
                residuals=residuals,
                message=(
                    f"Residual analysis: {raw.get('reading_count', 0)} matched readings, "
                    f"{len(surge_events)} surge events"
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_sea_level_trend(
        station_id: str,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get the long-term sea level rise rate at a station."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.get_sea_level_trend(station_id, tp)

            monthly_means = None
            if raw.get("monthly_means"):
                monthly_means = [
                    MonthlyMean(
                        year=m["year"],
                        month=m["month"],
                        value=m["value"],
                    )
                    for m in raw["monthly_means"]
                ]

            response = SeaLevelTrendResponse(
                station_id=station_id,
                station_name=raw.get("station_name", station_id),
                trend_mm_per_year=raw.get("trend_mm_per_year", 0.0),
                trend_uncertainty=raw.get("trend_uncertainty", 0.0),
                first_year=raw.get("first_year", 0),
                last_year=raw.get("last_year", 0),
                record_length_years=raw.get("record_length_years", 0),
                monthly_means=monthly_means,
                data_source=raw.get("data_source", tp.value),
                message=(
                    f"Sea level trend at {raw.get('station_name', station_id)}: "
                    f"{raw.get('trend_mm_per_year', 0.0):+.2f} mm/yr"
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_extreme_levels(
        station_id: str,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get historical extreme water level events at a station."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.get_extreme_levels(station_id, tp, datum=datum)

            top_high = [
                ExtremeEvent(
                    date=e.get("date", ""),
                    height=float(e.get("height", 0.0)),
                    event_name=e.get("event_name"),
                )
                for e in raw.get("top_ten_high", [])
            ]

            top_low = [
                ExtremeEvent(
                    date=e.get("date", ""),
                    height=float(e.get("height", 0.0)),
                    event_name=e.get("event_name"),
                )
                for e in raw.get("top_ten_low", [])
            ]

            d = raw.get("datum", datum or manager.default_datum(tp))

            response = ExtremeLevelsResponse(
                station_id=station_id,
                top_ten_high=top_high,
                top_ten_low=top_low,
                datum=str(d),
                message=(
                    f"Extreme water levels at {station_id}: "
                    f"{len(top_high)} highs, {len(top_low)} lows"
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
