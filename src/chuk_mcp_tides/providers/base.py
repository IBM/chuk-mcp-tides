"""
Abstract base class for tide data providers.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTideProvider(ABC):
    """Common interface for all tide data providers."""

    @abstractmethod
    async def list_stations(self, **kwargs: Any) -> list[dict[str, Any]]:
        """List stations with optional filters."""

    @abstractmethod
    async def get_station_detail(self, station_id: str) -> dict[str, Any]:
        """Get detailed metadata for a station."""

    @abstractmethod
    async def get_predictions(self, station_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Get tidal predictions."""

    @abstractmethod
    async def get_observations(self, station_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Get observed water levels."""

    @abstractmethod
    async def get_latest(self, station_id: str, **kwargs: Any) -> dict[str, Any]:
        """Get the most recent reading."""
