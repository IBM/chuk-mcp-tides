"""
Current tools for chuk-mcp-tides.

Tools: tides_currents_stations, tides_currents_predictions, tides_currents_latest
"""

import logging
from typing import Any

from ...core.tide_manager import TideManager
from ...models.responses import (
    CurrentPredictionEvent,
    CurrentPredictionResponse,
    CurrentStationListResponse,
    CurrentStationSummary,
    ErrorResponse,
    LatestCurrentResponse,
    format_response,
)

logger = logging.getLogger(__name__)


def register_currents_tools(mcp: Any, manager: TideManager) -> None:
    """Register tidal current tools with the MCP server."""

    @mcp.tool
    async def tides_currents_stations(
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float = 50.0,
        region: str | None = None,
        max_results: int = 20,
        output_mode: str = "json",
    ) -> str:
        """List NOAA tidal current prediction stations, optionally filtered by location."""
        try:
            raw = await manager.list_current_stations(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                region=region,
                max_results=max_results,
            )

            stations = [
                CurrentStationSummary(
                    station_id=str(s.get("station_id", "")),
                    name=str(s.get("name", "")),
                    lat=float(s.get("lat", 0.0)),
                    lon=float(s.get("lon", 0.0)),
                    type=s.get("type"),
                    depth=s.get("depth"),
                    depth_type=s.get("depth_type"),
                    bin_number=s.get("bin_number"),
                    provider=s.get("provider", "noaa"),
                )
                for s in raw
            ]

            search_loc = [lat, lon] if lat is not None and lon is not None else None
            response = CurrentStationListResponse(
                provider="noaa",
                station_count=len(stations),
                stations=stations,
                search_location=search_loc,
                search_radius_km=radius_km if search_loc else None,
                message=f"Found {len(stations)} current stations",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_currents_predictions(
        station_id: str,
        start_date: str = "today",
        end_date: str | None = None,
        interval: str = "MAX_SLACK",
        bin: str | None = None,
        units: str = "metric",
        output_mode: str = "json",
    ) -> str:
        """Get tidal current predictions (velocity, direction, event type) for a station."""
        try:
            # Resolve bin and station name from station metadata
            station_name = station_id
            resolved_bin = bin or "1"
            try:
                stations = await manager.list_current_stations(max_results=5000)
                for s in stations:
                    if s.get("station_id") == station_id:
                        station_name = s.get("name", station_id)
                        if bin is None and s.get("bin_number") is not None:
                            resolved_bin = str(s["bin_number"])
                        break
            except Exception:
                pass

            raw = await manager.get_current_predictions(
                station_id,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                units=units,
                bin=resolved_bin,
            )

            predictions = [
                CurrentPredictionEvent(
                    datetime=str(p.get("datetime", "")),
                    event_type=p.get("event_type"),
                    velocity_cm_s=float(p.get("velocity_cm_s", 0.0)),
                    mean_flood_dir=p.get("mean_flood_dir"),
                    mean_ebb_dir=p.get("mean_ebb_dir"),
                    depth=p.get("depth"),
                    bin_number=p.get("bin"),
                )
                for p in raw.get("predictions", [])
            ]

            response = CurrentPredictionResponse(
                station_id=station_id,
                station_name=station_name,
                provider=raw.get("provider", "noaa"),
                units=raw.get("units", "cm/s"),
                start_date=raw.get("start_date", start_date),
                end_date=raw.get("end_date", ""),
                interval=raw.get("interval", interval),
                event_count=len(predictions),
                predictions=predictions,
                message=f"{len(predictions)} current predictions for {station_name}",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_currents_latest(
        station_id: str,
        bin: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get the most recent tidal current observation from a station."""
        try:
            # Resolve bin and station name from station metadata
            station_name = station_id
            resolved_bin = bin or "1"
            try:
                stations = await manager.list_current_stations(max_results=5000)
                for s in stations:
                    if s.get("station_id") == station_id:
                        station_name = s.get("name", station_id)
                        if bin is None and s.get("bin_number") is not None:
                            resolved_bin = str(s["bin_number"])
                        break
            except Exception:
                pass

            raw = await manager.get_current_latest(station_id, bin=resolved_bin)

            velocity = float(raw.get("velocity_cm_s", 0.0))
            # Determine event type from velocity sign
            if velocity == 0.0:
                event_type = "slack"
            elif velocity > 0:
                event_type = "flood"
            else:
                event_type = "ebb"

            response = LatestCurrentResponse(
                station_id=station_id,
                station_name=station_name,
                datetime=str(raw.get("datetime", "")),
                velocity_cm_s=velocity,
                direction=raw.get("direction"),
                event_type=event_type,
                depth=raw.get("depth"),
                bin_number=raw.get("bin"),
                units=raw.get("units", "cm/s"),
                message=f"Latest current for {station_name}: {velocity:+.1f} cm/s ({event_type})",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
