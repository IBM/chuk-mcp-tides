"""
Reference data cache for chuk-mcp-tides.

Two-tier cache: in-memory dict -> chuk-artifacts (SANDBOX scope).
Stores slow-changing reference data (station lists, station details,
sea level trends, extreme levels, flood outlook) so that new server
instances do not re-download everything from upstream APIs.

Follows the same pattern as ConstituentStorage.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_META_TYPE = "tides_reference_cache"


class ReferenceCache:
    """Two-tier reference data cache backed by chuk-artifacts.

    Tier 1: In-memory dict with TTL (fast, process-local).
    Tier 2: chuk-artifacts with SANDBOX scope (shared across servers).

    Parameters
    ----------
    artifact_store : ArtifactStore
        The chuk-artifacts store instance.
    """

    def __init__(self, artifact_store: Any) -> None:
        self._store = artifact_store
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._artifact_index: dict[str, str] = {}
        self._warmed = False

    @property
    def warmed(self) -> bool:
        """Whether warm() has been called."""
        return self._warmed

    def cached_count(self) -> int:
        """Number of entries currently in the memory cache."""
        with self._lock:
            return len(self._cache)

    def indexed_count(self) -> int:
        """Number of artifact index entries."""
        return len(self._artifact_index)

    # ── Startup: warm the index from artifact store ──────────────────

    async def warm(self) -> int:
        """Search the artifact store for existing reference data.

        Populates the artifact_index so that subsequent get() calls
        can retrieve data from artifacts without a full provider fetch.

        Returns the number of artifacts found.  Non-fatal on error.
        """
        try:
            results = await self._store.search(
                scope="sandbox",
                meta_filter={"type": _META_TYPE},
                limit=500,
            )
            for meta in results:
                cache_key = meta.meta.get("cache_key", "")
                if cache_key:
                    self._artifact_index[cache_key] = meta.artifact_id
            self._warmed = True
            logger.info(
                "Reference cache warmed: %d artifacts indexed",
                len(self._artifact_index),
            )
            return len(self._artifact_index)
        except Exception as exc:
            logger.warning("Reference cache warm failed (non-fatal): %s", exc)
            self._warmed = True
            return 0

    # ── Public API ───────────────────────────────────────────────────

    async def get(self, key: str, ttl: int) -> Any | None:
        """Look up a reference data item.

        Checks tier 1 (memory) first, then tier 2 (artifact store).
        Returns ``None`` on miss in both tiers.
        """
        if not self._warmed:
            await self.warm()

        # Tier 1: memory
        hit = self._mem_get(key, ttl)
        if hit is not None:
            return hit

        # Tier 2: artifact store
        hit = await self._artifact_get(key)
        if hit is not None:
            self._mem_put(key, hit)
            return hit

        return None

    async def put(self, key: str, data: Any, ttl: int) -> None:
        """Store a reference data item in both tiers."""
        self._mem_put(key, data)
        try:
            await self._artifact_put(key, data, ttl)
        except Exception as exc:
            logger.warning(
                "Failed to store reference artifact for '%s': %s",
                key,
                exc,
            )

    # ── Tier 1: in-memory ────────────────────────────────────────────

    def _mem_get(self, key: str, ttl: int) -> Any | None:
        with self._lock:
            if key in self._cache:
                data, ts = self._cache[key]
                if time.time() - ts < ttl:
                    return data
                del self._cache[key]
        return None

    def _mem_put(self, key: str, data: Any) -> None:
        with self._lock:
            self._cache[key] = (data, time.time())

    # ── Tier 2: artifact store ───────────────────────────────────────

    async def _artifact_get(self, key: str) -> Any | None:
        if key not in self._artifact_index:
            return None
        artifact_id = self._artifact_index[key]
        try:
            raw = await self._store.retrieve(artifact_id)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.warning(
                "Failed to retrieve reference artifact '%s' (%s): %s",
                key,
                artifact_id,
                exc,
            )
            del self._artifact_index[key]
            return None

    async def _artifact_put(self, key: str, data: Any, ttl: int) -> str:
        json_bytes = json.dumps(data).encode("utf-8")
        artifact_id = await self._store.store(
            data=json_bytes,
            mime="application/json",
            summary=f"Tides reference: {key}",
            filename=f"tides_ref/{key.replace('|', '/')}.json",
            meta={"type": _META_TYPE, "cache_key": key},
            ttl=ttl,
            scope="sandbox",
        )
        self._artifact_index[key] = artifact_id
        return artifact_id
