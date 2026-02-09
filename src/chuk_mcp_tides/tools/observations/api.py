"""
Observation tools for chuk-mcp-tides.

Tools: tides_observations, tides_latest
"""

import logging

from ...core.tide_manager import TideManager
from ...models.responses import ErrorResponse, format_response

logger = logging.getLogger(__name__)


def register_observation_tools(mcp: object, manager: TideManager) -> None:
    """Register observation tools with the MCP server."""

    @mcp.tool  # type: ignore[union-attr]
    async def tides_observations(
        station_id: str,
        start_date: str = "today",
        end_date: str | None = None,
        product: str = "water_level",
        datum: str | None = None,
        provider: str | None = None,
        units: str = "metric",
        output_mode: str = "json",
    ) -> str:
        """Get observed (measured) water levels from a gauge station."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Observations not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_latest(
        station_id: str,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get the most recent water level reading from a station."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Latest reading not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
