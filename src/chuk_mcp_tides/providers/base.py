"""
Abstract base class for tide data providers.
"""

from abc import ABC, abstractmethod


class BaseTideProvider(ABC):
    """Common interface for all tide data providers."""

    @abstractmethod
    async def list_stations(self, **kwargs: object) -> list[dict[str, object]]:
        """List stations with optional filters."""

    @abstractmethod
    async def get_station_detail(self, station_id: str) -> dict[str, object]:
        """Get detailed metadata for a station."""

    @abstractmethod
    async def get_predictions(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        """Get tidal predictions."""

    @abstractmethod
    async def get_observations(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        """Get observed water levels."""

    @abstractmethod
    async def get_latest(self, station_id: str, **kwargs: object) -> dict[str, object]:
        """Get the most recent reading."""
