"""
UKHO Admiralty tide data provider.

Implements the BaseTideProvider interface for the UKHO
Admiralty Tidal API.
"""

from .base import BaseTideProvider


class UKHOProvider(BaseTideProvider):
    """UKHO Admiralty API client."""

    async def list_stations(self, **kwargs: object) -> list[dict[str, object]]:
        raise NotImplementedError("UKHO provider not yet implemented")

    async def get_station_detail(self, station_id: str) -> dict[str, object]:
        raise NotImplementedError("UKHO provider not yet implemented")

    async def get_predictions(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        raise NotImplementedError("UKHO provider not yet implemented")

    async def get_observations(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        raise NotImplementedError("UKHO provider not yet implemented")

    async def get_latest(self, station_id: str, **kwargs: object) -> dict[str, object]:
        raise NotImplementedError("UKHO provider not yet implemented")
