"""
Prediction tools for chuk-mcp-tides.

Tools: tides_predict, tides_predict_local
"""

import logging

from ...core.tide_manager import TideManager
from ...models.responses import (
    ErrorResponse,
    LocalPredictionResponse,
    PredictionResponse,
    TidalEvent,
    format_response,
)

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
            tp = manager.resolve_provider(provider)
            raw = await manager.get_predictions(
                station_id, tp,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                datum=datum,
                units=units,
            )

            # Get station name (best effort)
            station_name = station_id
            try:
                detail = await manager.get_station_detail(station_id, tp)
                station_name = detail.get("name", station_id)
            except Exception:
                pass

            predictions = [
                TidalEvent(
                    datetime=str(p.get("datetime", p.get("time", ""))),
                    height=float(p.get("height", 0.0)),
                    event_type=p.get("event_type"),
                )
                for p in raw.get("predictions", [])
            ]

            response = PredictionResponse(
                station_id=station_id,
                station_name=station_name,
                provider=raw.get("provider", tp.value),
                datum=raw.get("datum", ""),
                units=raw.get("units", units),
                start_date=raw.get("start_date", start_date),
                end_date=raw.get("end_date", ""),
                interval=raw.get("interval", interval),
                event_count=len(predictions),
                predictions=predictions,
                message=f"{len(predictions)} predictions for {station_name}",
            )
            return format_response(response, output_mode)
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
            raw = await manager.predict_local(
                start_date=start_date,
                end_date=end_date,
                station_id=station_id,
                constituents=constituents,
                interval_minutes=interval_minutes,
                datum_offset=datum_offset,
            )

            predictions = [
                TidalEvent(
                    datetime=str(p.get("datetime", p.get("time", ""))),
                    height=float(p.get("height", 0.0)),
                    event_type=p.get("event_type"),
                )
                for p in raw.get("predictions", [])
            ]

            highs_lows = [
                TidalEvent(
                    datetime=str(hl.get("datetime", hl.get("time", ""))),
                    height=float(hl.get("height", 0.0)),
                    event_type=hl.get("event_type"),
                )
                for hl in raw.get("highs_lows", [])
            ]

            response = LocalPredictionResponse(
                station_id=station_id,
                constituent_count=int(raw.get("constituent_count", 0)),
                start_date=raw.get("start_date", start_date),
                end_date=raw.get("end_date", end_date),
                interval_minutes=interval_minutes,
                event_count=len(predictions),
                predictions=predictions,
                highs_lows=highs_lows,
                message=(
                    f"Local prediction: {len(predictions)} points, "
                    f"{len(highs_lows)} highs/lows"
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
