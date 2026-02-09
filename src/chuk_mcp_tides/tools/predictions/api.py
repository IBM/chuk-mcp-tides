"""
Prediction tools for chuk-mcp-tides.

Tools: tides_predict, tides_predict_local
"""

import logging

from ...core.tide_manager import TideManager
from ...models.responses import ErrorResponse, format_response

logger = logging.getLogger(__name__)


def register_prediction_tools(mcp: object, manager: TideManager) -> None:
    """Register prediction tools with the MCP server."""

    @mcp.tool  # type: ignore[union-attr]
    async def tides_predict(
        station_id: str,
        start_date: str = "today",
        end_date: str | None = None,
        interval: str = "hilo",
        datum: str | None = None,
        provider: str | None = None,
        units: str = "metric",
        output_mode: str = "json",
    ) -> str:
        """Get tidal height predictions for a station over a date range."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Predictions not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_predict_local(
        start_date: str,
        end_date: str,
        station_id: str | None = None,
        constituents: dict | None = None,
        interval_minutes: int = 60,
        datum_offset: float = 0.0,
        output_mode: str = "json",
    ) -> str:
        """Compute tidal predictions offline using harmonic constituents."""
        try:
            return format_response(
                ErrorResponse(error="Local predictions not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
