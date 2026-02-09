"""
Observation tools for chuk-mcp-tides.

Tools: tides_observations, tides_latest
"""

import logging
from typing import Any

from ...core.tide_manager import TideManager
from ...models.responses import (
    ErrorResponse,
    LatestReadingResponse,
    ObservationResponse,
    TidalEvent,
    WaterLevelReading,
    format_response,
)

logger = logging.getLogger(__name__)


def _find_previous_reading(readings: list[dict], current_dt: str) -> dict | None:
    """Find the reading immediately before *current_dt* in a list."""
    sorted_r = sorted(
        readings,
        key=lambda r: r.get("datetime", r.get("time", "")),
    )
    prev = None
    for r in sorted_r:
        r_dt = r.get("datetime", r.get("time", ""))
        if r_dt >= current_dt:
            break
        prev = r
    return prev


def register_observation_tools(mcp: Any, manager: TideManager) -> None:
    """Register observation tools with the MCP server."""

    @mcp.tool
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
            tp = manager.resolve_provider(provider)
            raw = await manager.get_observations(
                station_id,
                tp,
                start_date=start_date,
                end_date=end_date,
                product=product,
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

            readings = [
                WaterLevelReading(
                    datetime=str(r.get("datetime", r.get("time", ""))),
                    value=float(r.get("value", 0.0)),
                    quality=r.get("quality"),
                    anomaly=r.get("anomaly"),
                )
                for r in raw.get("readings", [])
            ]

            response = ObservationResponse(
                station_id=station_id,
                station_name=station_name,
                provider=raw.get("provider", tp.value),
                datum=raw.get("datum", ""),
                units=raw.get("units", units),
                product=raw.get("product", product),
                reading_count=len(readings),
                readings=readings,
                message=f"{len(readings)} observations for {station_name}",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool
    async def tides_latest(
        station_id: str,
        datum: str | None = None,
        provider: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Get the most recent water level reading from a station."""
        try:
            tp = manager.resolve_provider(provider)
            raw = await manager.get_latest(station_id, tp, datum=datum)

            # Get station name
            station_name = station_id
            try:
                detail = await manager.get_station_detail(station_id, tp)
                station_name = detail.get("name", station_id)
            except Exception:
                pass

            dt = str(raw.get("datetime", raw.get("time", "")))
            value = float(raw.get("value", 0.0))
            tide_state = "unknown"
            next_high = None
            next_low = None

            # Get current tide state from predictions
            try:
                pred_data = await manager.get_predictions(
                    station_id,
                    tp,
                    start_date="today",
                    interval="hilo",
                    datum=datum,
                )
                state, nh, nl = manager.determine_tide_state(
                    value,
                    pred_data.get("predictions", []),
                    dt,
                )
                tide_state = state
                if nh:
                    next_high = TidalEvent(
                        datetime=str(nh.get("datetime", nh.get("time", ""))),
                        height=float(nh.get("height", 0.0)),
                        event_type="high",
                    )
                if nl:
                    next_low = TidalEvent(
                        datetime=str(nl.get("datetime", nl.get("time", ""))),
                        height=float(nl.get("height", 0.0)),
                        event_type="low",
                    )
            except Exception:
                # Fallback: infer tide state from recent observations
                try:
                    obs = await manager.get_observations(
                        station_id,
                        tp,
                        start_date="today",
                    )
                    readings = obs.get("readings", [])
                    if len(readings) >= 2:
                        prev = _find_previous_reading(readings, dt)
                        if prev is not None:
                            prev_val = float(prev.get("value", prev.get("height", 0.0)))
                            if value > prev_val:
                                tide_state = "rising"
                            elif value < prev_val:
                                tide_state = "falling"
                except Exception:
                    pass

            d = raw.get("datum", datum or manager.default_datum(tp))

            response = LatestReadingResponse(
                station_id=station_id,
                station_name=station_name,
                datetime=dt,
                value=value,
                datum=str(d),
                units="metric",
                next_high=next_high,
                next_low=next_low,
                tide_state=tide_state,
                message=f"Latest reading for {station_name}: {value:+.3f}m ({tide_state})",
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
