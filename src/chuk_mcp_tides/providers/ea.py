"""
UK Environment Agency tide data provider.

Implements the BaseTideProvider interface for the EA
Flood Monitoring API (https://environment.data.gov.uk/flood-monitoring/).

Provides real-time tidal observations from UK coastal stations.
No API key required. Predictions are not available -- use the
'local' provider for harmonic predictions at EA station locations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from ..core.http_client import ResilientClient
from ..core.utils import haversine_km
from .base import BaseTideProvider

_BASE_URL = "https://environment.data.gov.uk/flood-monitoring"


class EAProvider(BaseTideProvider):
    """UK Environment Agency Flood Monitoring API client.

    The EA API exposes tidal-level observations from a network of coastal
    gauges.  It does **not** publish tidal predictions; for those, use the
    ``LocalProvider`` (harmonic engine) or ``UKHOProvider``.

    Default vertical datum: AOD (Above Ordnance Datum).
    """

    def __init__(self) -> None:
        self._http = ResilientClient(timeout=30.0, rate_limit=10.0)

    # --------------------------------------------------------------------- #
    # list_stations
    # --------------------------------------------------------------------- #
    async def list_stations(self, **kwargs: object) -> list[dict[str, object]]:
        """Return EA tidal-level stations.

        Keyword Args:
            lat:      Centre latitude for proximity search.
            lon:      Centre longitude for proximity search.
            radius_km: Max distance from (lat, lon).  Default 50 km.
        """
        url = f"{_BASE_URL}/id/stations"
        params: dict[str, str | int] = {
            "type": "TideGauge",
            "_limit": 500,
        }
        try:
            resp = await self._http.get(url, params=params)
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(f"EA API error listing stations: {exc}") from exc

        items: list[dict] = data.get("items", [])

        stations: list[dict[str, object]] = []
        for item in items:
            lat = item.get("lat")
            lon = item.get("long")
            station: dict[str, object] = {
                "station_id": item.get("stationReference", ""),
                "name": item.get("label", ""),
                "lat": lat,
                "lon": lon,
                "date_opened": item.get("dateOpened"),
                "provider": "ea",
                "datum": "AOD",
            }
            stations.append(station)

        # Optional proximity filter ----------------------------------------
        centre_lat = kwargs.get("lat")
        centre_lon = kwargs.get("lon")
        if centre_lat is not None and centre_lon is not None:
            radius_km = float(kwargs.get("radius_km", 50))
            filtered: list[dict[str, object]] = []
            for s in stations:
                s_lat = s.get("lat")
                s_lon = s.get("lon")
                if s_lat is None or s_lon is None:
                    continue
                dist = haversine_km(
                    float(centre_lat), float(centre_lon),
                    float(s_lat), float(s_lon),
                )
                if dist <= radius_km:
                    s["distance_km"] = round(dist, 2)
                    filtered.append(s)
            filtered.sort(key=lambda x: x.get("distance_km", 0))
            return filtered

        return stations

    # --------------------------------------------------------------------- #
    # get_station_detail
    # --------------------------------------------------------------------- #
    async def get_station_detail(self, station_id: str) -> dict[str, object]:
        """Fetch detailed metadata for a single EA station."""
        url = f"{_BASE_URL}/id/stations/{station_id}"
        try:
            resp = await self._http.get(url)
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(f"EA API error for station '{station_id}': {exc}") from exc

        item: dict = data.get("items", {})
        if isinstance(item, list):
            item = item[0] if item else {}

        measures = item.get("measures", [])
        if isinstance(measures, dict):
            measures = [measures]

        return {
            "station_id": item.get("stationReference", station_id),
            "name": item.get("label", ""),
            "lat": item.get("lat"),
            "lon": item.get("long"),
            "date_opened": item.get("dateOpened"),
            "measures": measures,
            "provider": "ea",
            "datum": "AOD",
        }

    # --------------------------------------------------------------------- #
    # get_predictions
    # --------------------------------------------------------------------- #
    async def get_predictions(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        """Not supported -- the EA API only publishes observations.

        Raises:
            NotImplementedError: Always.  Use the ``local`` provider for
                harmonic tidal predictions at EA station locations.
        """
        raise NotImplementedError(
            "The EA Flood Monitoring API does not provide tidal predictions. "
            "Use the 'local' provider (harmonic engine) to compute predictions "
            "at this station's coordinates."
        )

    # --------------------------------------------------------------------- #
    # get_observations
    # --------------------------------------------------------------------- #
    async def get_observations(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        """Fetch observed tidal-level readings.

        Keyword Args:
            since: ISO-8601 datetime string.  Defaults to 24 h ago.
            limit: Maximum number of readings (default 2000).
        """
        since = kwargs.get("since")
        if since is None:
            since = (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

        limit = int(kwargs.get("limit", 2000))

        url = f"{_BASE_URL}/id/stations/{station_id}/readings"
        params: dict[str, str | int] = {
            "_sorted": "",
            "_limit": limit,
            "since": str(since),
        }
        try:
            resp = await self._http.get(url, params=params)
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(
                f"EA API error fetching observations for '{station_id}': {exc}"
            ) from exc

        items: list[dict] = data.get("items", [])
        readings: list[dict[str, object]] = []
        for r in items:
            readings.append({
                "time": r.get("dateTime"),
                "value": r.get("value"),
                "datum": "AOD",
            })
        return readings

    # --------------------------------------------------------------------- #
    # get_latest
    # --------------------------------------------------------------------- #
    async def get_latest(self, station_id: str, **kwargs: object) -> dict[str, object]:
        """Fetch the most recent tidal-level reading for a station."""
        url = f"{_BASE_URL}/id/stations/{station_id}/readings"
        params: dict[str, str | int] = {
            "_sorted": "",
            "_limit": 1,
        }
        try:
            resp = await self._http.get(url, params=params)
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(
                f"EA API error fetching latest reading for '{station_id}': {exc}"
            ) from exc

        items: list[dict] = data.get("items", [])
        if not items:
            raise ValueError(
                f"No readings available for EA station '{station_id}'."
            )

        reading = items[0]
        return {
            "station_id": station_id,
            "time": reading.get("dateTime"),
            "value": reading.get("value"),
            "datum": "AOD",
            "provider": "ea",
        }
