"""
Station discovery tools for chuk-mcp-tides.

Tools: tides_list_stations, tides_describe_station, tides_find_nearest
"""

import logging

from ...core.tide_manager import TideManager
from ...models.responses import ErrorResponse, format_response

logger = logging.getLogger(__name__)


def register_station_tools(mcp: object, manager: TideManager) -> None:
    """Register station discovery tools with the MCP server."""

    @mcp.tool  # type: ignore[union-attr]
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
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Station listing not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_describe_station(
        station_id: str,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get detailed metadata for a specific station."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Station description not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_find_nearest(
        lat: float,
        lon: float,
        provider: str | None = "all",
        max_results: int = 5,
        output_mode: str = "json",
    ) -> str:
        """Find the nearest tide station to a coordinate."""
        try:
            return format_response(
                ErrorResponse(error="Find nearest not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
