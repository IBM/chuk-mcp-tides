"""
UKHO Admiralty tide data provider.

Implements the BaseTideProvider interface for the UKHO
Admiralty Tidal API (https://admiraltyapi.azure-api.net/uktidalapi/).

Provides tidal-event predictions (high/low water) for UK stations.
Requires an API key set in the ``UKHO_API_KEY`` environment variable.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from ..core.http_client import ResilientClient
from ..core.utils import haversine_km
from .base import BaseTideProvider

_BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"


class UKHOProvider(BaseTideProvider):
    """UKHO Admiralty Tidal API client.

    The API returns tidal-event predictions (high/low water times and
    heights).  It does **not** provide real-time observations -- for
    those, use the ``EAProvider``.

    Default vertical datum: CD (Chart Datum).
    """

    def __init__(self) -> None:
        self._api_key: str | None = os.environ.get("UKHO_API_KEY")
        self._http: ResilientClient | None = None

    # --------------------------------------------------------------------- #
    # helpers
    # --------------------------------------------------------------------- #
    def _require_key(self) -> str:
        """Return the API key or raise if unset."""
        if not self._api_key:
            raise ValueError(
                "UKHO API key not configured.  Set the UKHO_API_KEY "
                "environment variable to your Admiralty API subscription key."
            )
        return self._api_key

    def _auth_headers(self) -> dict[str, str]:
        """Build authentication headers."""
        return {"Ocp-Apim-Subscription-Key": self._require_key()}

    def _client(self) -> ResilientClient:
        """Return the shared resilient HTTP client (lazily created)."""
        if self._http is None:
            self._http = ResilientClient(
                timeout=30.0,
                rate_limit=5.0,
                headers=self._auth_headers(),
            )
        return self._http

    # --------------------------------------------------------------------- #
    # list_stations
    # --------------------------------------------------------------------- #
    async def list_stations(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return UKHO tidal stations.

        Keyword Args:
            lat:      Centre latitude for proximity search.
            lon:      Centre longitude for proximity search.
            radius_km: Max distance from (lat, lon).  Default 50 km.
        """
        url = f"{_BASE_URL}/Stations"
        try:
            resp = await self._client().get(url)
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(f"UKHO API error listing stations: {exc}") from exc

        features: list[dict] = data.get("features", [])

        stations: list[dict[str, Any]] = []
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [None, None])
            # GeoJSON order: [longitude, latitude]
            lon = coords[0] if len(coords) > 0 else None
            lat = coords[1] if len(coords) > 1 else None

            station: dict[str, Any] = {
                "station_id": props.get("Id", ""),
                "name": props.get("Name", ""),
                "country": props.get("Country", ""),
                "lat": lat,
                "lon": lon,
                "provider": "ukho",
                "datum": "CD",
            }
            stations.append(station)

        # Optional proximity filter ----------------------------------------
        centre_lat = kwargs.get("lat")
        centre_lon = kwargs.get("lon")
        if centre_lat is not None and centre_lon is not None:
            radius_km = float(kwargs.get("radius_km", 50))
            filtered: list[dict[str, Any]] = []
            for s in stations:
                s_lat = s.get("lat")
                s_lon = s.get("lon")
                if s_lat is None or s_lon is None:
                    continue
                dist = haversine_km(
                    float(centre_lat),
                    float(centre_lon),
                    float(s_lat),
                    float(s_lon),
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
    async def get_station_detail(self, station_id: str) -> dict[str, Any]:
        """Fetch detailed metadata for a single UKHO station."""
        url = f"{_BASE_URL}/Stations/{station_id}"
        try:
            resp = await self._client().get(url)
            feature = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(f"UKHO API error for station '{station_id}': {exc}") from exc

        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        lon = coords[0] if len(coords) > 0 else None
        lat = coords[1] if len(coords) > 1 else None

        return {
            "station_id": props.get("Id", station_id),
            "name": props.get("Name", ""),
            "country": props.get("Country", ""),
            "lat": lat,
            "lon": lon,
            "provider": "ukho",
            "datum": "CD",
        }

    # --------------------------------------------------------------------- #
    # get_predictions
    # --------------------------------------------------------------------- #
    async def get_predictions(self, station_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch tidal-event predictions (high/low water).

        Keyword Args:
            duration: Number of days from today (default 7, max 7 for
                      Discovery tier, 365 for Premium).
        """
        duration = int(kwargs.get("duration", 7))
        url = f"{_BASE_URL}/Stations/{station_id}/TidalEvents"
        params: dict[str, int] = {"duration": duration}
        try:
            resp = await self._client().get(url, params=params)
            events = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ValueError(
                f"UKHO API error fetching predictions for '{station_id}': {exc}"
            ) from exc

        if not isinstance(events, list):
            events = []

        predictions: list[dict[str, Any]] = []
        for evt in events:
            predictions.append(
                {
                    "time": evt.get("DateTime"),
                    "event_type": evt.get("EventType"),
                    "height": evt.get("Height"),
                    "is_approximate_time": evt.get("IsApproximateTime", False),
                    "is_approximate_height": evt.get("IsApproximateHeight", False),
                    "datum": "CD",
                }
            )
        return predictions

    # --------------------------------------------------------------------- #
    # get_observations
    # --------------------------------------------------------------------- #
    async def get_observations(self, station_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Not supported -- the UKHO API only publishes predictions.

        Raises:
            NotImplementedError: Always.  Use the ``ea`` provider for
                real-time tidal observations at UK stations.
        """
        raise NotImplementedError(
            "The UKHO Admiralty Tidal API does not provide real-time "
            "observations. Use the 'ea' provider (Environment Agency) "
            "for observed water levels at UK stations."
        )

    # --------------------------------------------------------------------- #
    # get_latest
    # --------------------------------------------------------------------- #
    async def get_latest(self, station_id: str, **kwargs: Any) -> dict[str, Any]:
        """Not supported -- the UKHO API does not provide latest readings.

        Raises:
            NotImplementedError: Always.  Use the ``ea`` provider for
                real-time latest readings at UK stations.
        """
        raise NotImplementedError(
            "The UKHO Admiralty Tidal API does not provide a latest-reading "
            "endpoint. Use the 'ea' provider (Environment Agency) for the "
            "most recent observed water level."
        )
