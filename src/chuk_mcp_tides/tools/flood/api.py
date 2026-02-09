"""
Flood risk tools for chuk-mcp-tides.

Tools: tides_flood_outlook, tides_flooding_calendar
"""

import logging
from typing import Any

from ...core.tide_manager import TideManager
from ...models.responses import (
    ErrorResponse,
    FloodCount,
    FloodDay,
    FloodingCalendarResponse,
    FloodOutlookResponse,
    FloodProjectionNOAA,
    MonthFloodSummary,
    format_response,
)

logger = logging.getLogger(__name__)


def register_flood_tools(mcp: Any, manager: TideManager) -> None:
    """Register flood risk tools with the MCP server."""

    @mcp.tool
    async def tides_flood_outlook(
        station_id: str,
        product: str = "htf_annual",
        flood_threshold: str = "minor",
        year: int | None = None,
        decade: int | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get high-tide flooding outlook (NOAA Derived Product API)."""
        try:
            raw = await manager.get_flood_outlook(
                station_id,
                product=product,
                threshold=flood_threshold,
            )

            counts = [
                FloodCount(
                    period=str(c.get("period", "")),
                    count=int(c.get("count", 0)),
                )
                for c in raw.get("counts", [])
            ]

            projection = None
            if raw.get("projection"):
                p = raw["projection"]
                projection = FloodProjectionNOAA(
                    year=p["year"],
                    expected=p["expected"],
                    low=p["low"],
                    high=p["high"],
                )

            response = FloodOutlookResponse(
                station_id=station_id,
                product=raw.get("product", product),
                flood_threshold=raw.get("threshold", flood_threshold),
                flood_level_m=float(raw.get("flood_level_m", 0.0)),
                counts=counts,
                projection=projection,
                message=f"Flood outlook for {station_id}: {len(counts)} periods",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
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
            tp = manager.resolve_provider(provider)
            raw = await manager.flooding_calendar(
                station_id,
                threshold,
                tp,
                year=year,
                slr_offset_mm=slr_offset_mm,
                datum=datum,
            )

            monthly = [
                MonthFloodSummary(
                    month=m["month"],
                    flood_days=m["flood_days"],
                    max_height=m["max_height"],
                    total_hours=m["total_hours"],
                )
                for m in raw.get("monthly_summary", [])
            ]

            flood_days = [
                FloodDay(
                    date=d["date"],
                    peak_height=d["peak_height"],
                    duration_hours=d["duration_hours"],
                    tides_above=d["tides_above"],
                )
                for d in raw.get("flood_days", [])
            ]

            response = FloodingCalendarResponse(
                station_id=station_id,
                year=raw.get("year", year or 0),
                threshold=raw.get("threshold", threshold),
                slr_offset_mm=raw.get("slr_offset_mm", slr_offset_mm),
                datum=raw.get("datum", ""),
                total_flood_days=raw.get("total_flood_days", 0),
                total_flood_hours=raw.get("total_flood_hours", 0.0),
                monthly_summary=monthly,
                flood_days=flood_days,
                message=(
                    f"Flooding calendar: {raw.get('total_flood_days', 0)} flood days "
                    f"in {raw.get('year', year or 'N/A')}"
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
