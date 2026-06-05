"""
Analysis tools for chuk-mcp-tides.

Tools: tides_threshold_exceedance, tides_project_flooding,
       tides_harmonic_analysis, tides_residual,
       tides_sea_level_trend, tides_extreme_levels
"""

import datetime as _dt
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
    TidalStage,
    TidalStageResponse,
    TippingPoint,
    TrendInfo,
    format_response,
)

logger = logging.getLogger(__name__)


def _parse_dt(s: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _classify_stages(series_by_day, datetimes, low_below, high_above):
    """Pure stage classification. series_by_day: {YYYY-MM-DD: [(datetime, height), ...]}."""
    out = []
    for ts in datetimes:
        series = series_by_day.get(ts[:10])
        if not series:
            out.append({"datetime": ts, "height": None, "stage_norm": None, "stage": "unknown"})
            continue
        target = _parse_dt(ts)
        h = float(min(series, key=lambda p: abs((p[0] - target).total_seconds()))[1])
        heights = [p[1] for p in series]
        lo, hi = min(heights), max(heights)
        rng = (hi - lo) or 1.0
        sn = (h - lo) / rng
        stage = "low" if sn < low_below else ("high" if sn > high_above else "mid")
        out.append(
            {
                "datetime": ts,
                "height": round(h, 3),
                "stage_norm": round(float(sn), 3),
                "stage": stage,
            }
        )
    return out


def register_analysis_tools(mcp: Any, manager: TideManager) -> None:
    """Register analysis tools with the MCP server."""

    @mcp.tool
    async def tides_classify_stage(
        datetimes: list[str],
        station_id: str,
        provider: str | None = None,
        low_below: float = 0.33,
        high_above: float = 0.66,
        fit_window_days: int = 35,
        output_mode: str = "json",
    ) -> str:
        """Classify timestamps by tidal stage — enables tide-stratified imagery selection.

        Given acquisition timestamps (e.g. Sentinel-2 scene datetimes) and a tide station,
        return the predicted tide HEIGHT and within-day stage (0 = that day's low water,
        1 = high water) for each. Keep only same-tide scenes across epochs so multi-epoch
        coastal change is real signal, not tide — the fix for the attrition-register confound
        where clear-sky scenes happen to sample different tides in different years.

        Uses the harmonic engine: if the station has no stored constituents, they are fitted
        from the most recent ~fit_window_days of observations (pass provider='ea' for UK
        gauges so the right observations are fetched).

        Args:
            datetimes: ISO timestamps to classify, e.g. ["2019-08-25T11:06:58Z", ...].
            station_id: Tide gauge id (e.g. an EA station from tides_find_nearest).
            provider: 'ea' (UK) or 'noaa'; used when constituents must be fitted.
            low_below: stage_norm strictly below this is "low" (default 0.33).
            high_above: stage_norm strictly above this is "high" (default 0.66).
            fit_window_days: recent-observation window used to fit constituents if needed.
            output_mode: "json" or "text".

        Returns:
            Per-timestamp tide height + stage; band your scenes (e.g. stage=='low') for a
            tide-stratified composite/time-series.
        """
        try:
            if not datetimes:
                return format_response(
                    ErrorResponse(error="Provide a non-empty list of ISO datetimes"), output_mode
                )
            days = sorted({ts[:10] for ts in datetimes})

            async def _series(day: str):
                nxt = (_dt.date.fromisoformat(day) + _dt.timedelta(days=1)).isoformat()
                res = await manager.predict_local(
                    start_date=day, end_date=nxt, station_id=station_id, interval_minutes=15
                )
                return [
                    (_parse_dt(p["datetime"]), float(p["height"]))
                    for p in res.get("predictions", [])
                ]

            fitted = False
            try:
                series_by_day = {days[0]: await _series(days[0])}
            except FileNotFoundError:
                tp = manager.resolve_provider(provider)
                today = _dt.datetime.now(_dt.timezone.utc).date()
                await manager.harmonic_analysis(
                    station_id,
                    (today - _dt.timedelta(days=fit_window_days)).isoformat(),
                    today.isoformat(),
                    tp,
                    store_constituents=True,
                )
                fitted = True
                series_by_day = {days[0]: await _series(days[0])}
            for day in days[1:]:
                series_by_day[day] = await _series(day)

            records = _classify_stages(series_by_day, datetimes, low_below, high_above)
            stages = [TidalStage(**r) for r in records]
            n_low = sum(1 for s in stages if s.stage == "low")
            msg = (
                f"Classified {len(stages)} timestamp(s) at {station_id}"
                f"{' (constituents freshly fitted)' if fitted else ''}; {n_low} at low stage"
            )
            return format_response(
                TidalStageResponse(
                    station_id=station_id,
                    count=len(stages),
                    fitted=fitted,
                    stages=stages,
                    message=msg,
                ),
                output_mode,
            )
        except FileNotFoundError:
            return format_response(
                ErrorResponse(
                    error=(
                        f"No stored constituents for '{station_id}' and could not fit from recent "
                        "observations. Run tides_harmonic_analysis first, or pass provider='ea' for "
                        "a UK gauge with recent data."
                    )
                ),
                output_mode,
            )
        except Exception as e:
            logger.error(f"tides_classify_stage failed: {e}")
            return format_response(ErrorResponse(error=str(e)), output_mode)

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
