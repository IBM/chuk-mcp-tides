"""
Analysis tools for chuk-mcp-tides.

Tools: tides_threshold_exceedance, tides_project_flooding,
       tides_harmonic_analysis, tides_residual,
       tides_sea_level_trend, tides_extreme_levels
"""

import logging

from ...constants import DEFAULT_PROJECTION_SCENARIOS, DEFAULT_PROJECTION_YEARS
from ...core.tide_manager import TideManager
from ...models.responses import ErrorResponse, format_response

logger = logging.getLogger(__name__)


def register_analysis_tools(mcp: object, manager: TideManager) -> None:
    """Register analysis tools with the MCP server."""

    @mcp.tool  # type: ignore[union-attr]
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
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Threshold exceedance not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
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
            _ = manager.resolve_provider(provider)
            _years = years or DEFAULT_PROJECTION_YEARS
            _scenarios = scenarios or DEFAULT_PROJECTION_SCENARIOS
            return format_response(
                ErrorResponse(error="Flood projection not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
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
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Harmonic analysis not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
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
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Residual computation not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_sea_level_trend(
        station_id: str,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get the long-term sea level rise rate at a station."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Sea level trend not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_extreme_levels(
        station_id: str,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get historical extreme water level events at a station."""
        try:
            _ = manager.resolve_provider(provider)
            return format_response(
                ErrorResponse(error="Extreme levels not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
