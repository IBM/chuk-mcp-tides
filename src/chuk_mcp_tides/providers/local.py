"""
Local harmonic engine provider.

Implements offline tidal predictions from harmonic constituents
via utide. No network required.
"""

from .base import BaseTideProvider


class LocalProvider(BaseTideProvider):
    """Local harmonic engine using utide."""

    async def list_stations(self, **kwargs: object) -> list[dict[str, object]]:
        raise NotImplementedError("Local provider not yet implemented")

    async def get_station_detail(self, station_id: str) -> dict[str, object]:
        raise NotImplementedError("Local provider not yet implemented")

    async def get_predictions(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        raise NotImplementedError("Local provider not yet implemented")

    async def get_observations(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        raise NotImplementedError("Local provider does not support observations")

    async def get_latest(self, station_id: str, **kwargs: object) -> dict[str, object]:
        raise NotImplementedError("Local provider does not support latest readings")
