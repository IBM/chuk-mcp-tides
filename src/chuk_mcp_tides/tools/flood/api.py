"""
Flood risk tools for chuk-mcp-tides.

Tools: tides_flood_outlook, tides_flooding_calendar
"""

import logging

from ...core.tide_manager import TideManager
from ...models.responses import ErrorResponse, format_response

logger = logging.getLogger(__name__)


def register_flood_tools(mcp: object, manager: TideManager) -> None:
    """Register flood risk tools with the MCP server."""

    @mcp.tool  # type: ignore[union-attr]
    async def tides_flood_outlook(
        station_id: str,
        product: str = "annual",
        flood_threshold: str = "minor",
        year: int | None = None,
        decade: int | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get high-tide flooding outlook (NOAA Derived Product API)."""
        try:
            return format_response(
                ErrorResponse(error="Flood outlook not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_flooding_calendar(
        station_id: str,
        threshold: float,
        year: int | None = None,
        slr_offset_mm: float = 0.0,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Generate a day-by-day flooding calendar for a location."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Flooding calendar not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
