"""
Station discovery tools for chuk-mcp-tides.

Tools: tides_list_stations, tides_describe_station, tides_find_nearest
"""

import logging
from typing import Any

from ...core.tide_manager import TideManager
from ...models.responses import (
    ConstituentInfo,
    DatumInfo,
    ErrorResponse,
    FloodThresholdInfo,
    NearestStation,
    NearestStationResponse,
    StationDetailResponse,
    StationListResponse,
    StationSummary,
    format_response,
)

logger = logging.getLogger(__name__)


def register_station_tools(mcp: Any, manager: TideManager) -> None:
    """Register station discovery tools with the MCP server."""

    @mcp.tool
    async def tides_list_stations(
        provider: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float = 50.0,
        region: str | None = None,
        station_type: str | None = None,
        max_results: int = 20,
        output_mode: str = "json",
    ) -> str:
        """List tide gauge stations, optionally filtered by location or region."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.list_stations(
                tp,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                region=region,
                station_type=station_type,
                max_results=max_results,
            )

            stations = [
                StationSummary(
                    station_id=str(s.get("station_id", "")),
                    name=str(s.get("name", "")),
                    lat=float(s.get("lat", 0.0)),
                    lon=float(s.get("lon", 0.0)),
                    station_type=s.get("station_type"),
                    provider=s.get("provider", tp.value),
                    date_range=s.get("date_range"),
                )
                for s in raw
            ]

            search_loc = [lat, lon] if lat is not None and lon is not None else None
            response = StationListResponse(
                provider=tp.value,
                station_count=len(stations),
                stations=stations,
                search_location=search_loc,
                search_radius_km=radius_km if search_loc else None,
                message=f"Found {len(stations)} stations from {tp.value}",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_describe_station(
        station_id: str,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get detailed metadata for a specific station."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.get_station_detail(station_id, tp)

            # Map datums
            datums = [
                DatumInfo(
                    name=str(d.get("name", "")),
                    value=float(d.get("value", 0.0)),
                    description=d.get("description"),
                )
                for d in raw.get("datums", [])
            ]

            # Map harmonic constituents
            constituents = None
            harcon = raw.get("harcon")
            if harcon:
                constituents = [
                    ConstituentInfo(
                        name=str(c.get("name", "")),
                        amplitude=float(c.get("amplitude", 0.0)),
                        phase=float(c.get("phase_GMT", c.get("phase", 0.0))),
                        speed=c.get("speed"),
                    )
                    for c in harcon
                ]

            # Map flood thresholds
            flood_thresholds = None
            fl = raw.get("floodlevels")
            if fl and isinstance(fl, dict):
                flood_thresholds = FloodThresholdInfo(
                    minor=fl.get("minor"),
                    moderate=fl.get("moderate"),
                    major=fl.get("major"),
                )

            # Map sensors
            sensors = raw.get("sensors", [])
            if isinstance(sensors, list):
                sensors = [str(s) for s in sensors]

            response = StationDetailResponse(
                station_id=str(raw.get("station_id", station_id)),
                name=str(raw.get("name", "")),
                provider=str(raw.get("provider", tp.value)),
                lat=float(raw.get("lat", 0.0)),
                lon=float(raw.get("lon", 0.0)),
                datums=datums,
                sensors=sensors,
                data_range=raw.get("data_range"),
                tidal_type=raw.get("tidal_type"),
                harmonic_constituents=constituents,
                flood_thresholds=flood_thresholds,
                mean_sea_level_trend=raw.get("mean_sea_level_trend"),
                linked_station=raw.get("linked_station"),
                message=f"Station detail for {raw.get('name', station_id)}",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_find_nearest(
        lat: float,
        lon: float,
        provider: str | None = "all",
        max_results: int = 5,
        output_mode: str = "json",
    ) -> str:
        """Find the nearest tide station to a coordinate."""
        try:
            # Determine which providers to search
            if provider == "all" or provider is None:
                providers = None  # manager defaults to all
            else:
                tp = manager.resolve_provider(provider)
                providers = [tp]

            raw = await manager.find_nearest(
                lat,
                lon,
                providers=providers,
                max_results=max_results,
            )

            stations = [
                NearestStation(
                    station_id=str(s.get("station_id", "")),
                    name=str(s.get("name", "")),
                    lat=float(s.get("lat", 0.0)),
                    lon=float(s.get("lon", 0.0)),
                    provider=str(s.get("provider", "")),
                    distance_km=round(float(s.get("distance_km", 0.0)), 2),
                )
                for s in raw
            ]

            response = NearestStationResponse(
                search_location=[lat, lon],
                stations=stations,
                message=f"Found {len(stations)} stations near ({lat:.4f}, {lon:.4f})",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
