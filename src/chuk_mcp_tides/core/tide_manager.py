"""
TideManager — central orchestrator for chuk-mcp-tides.

Dispatches requests to the appropriate provider, manages caching,
and handles artifact storage for time series data.
"""

import logging
import os
import threading
import time

from ..constants import (
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_PROVIDER,
    EnvVar,
    TideProvider,
)

logger = logging.getLogger(__name__)


class TideManager:
    """Central orchestrator for tide data operations."""

    def __init__(
        self,
        default_provider: TideProvider = DEFAULT_PROVIDER,
    ) -> None:
        self._default_provider = default_provider
        self._cache: dict[str, tuple[object, float]] = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl = int(
            os.environ.get(EnvVar.CACHE_TTL, str(DEFAULT_CACHE_TTL_SECONDS))
        )

    @property
    def default_provider(self) -> TideProvider:
        return self._default_provider

    def resolve_provider(self, provider: str | None) -> TideProvider:
        """Resolve a provider name string to a TideProvider enum."""
        if provider is None:
            return self._default_provider
        try:
            return TideProvider(provider.lower())
        except ValueError:
            logger.warning(f"Unknown provider '{provider}', falling back to default")
            return self._default_provider

    def _cache_key(self, *parts: str) -> str:
        return "|".join(parts)

    def get_cached(self, key: str) -> object | None:
        """Get a cached value if it exists and hasn't expired."""
        with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._cache_ttl:
                    return value
                del self._cache[key]
        return None

    def set_cached(self, key: str, value: object) -> None:
        """Store a value in the cache."""
        with self._cache_lock:
            self._cache[key] = (value, time.time())
