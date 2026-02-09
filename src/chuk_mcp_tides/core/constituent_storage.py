"""
Constituent storage for chuk-mcp-tides.

Stores tidal harmonic constituents via chuk-artifacts, providing
pluggable backends (memory, filesystem, S3).  Designed for scalable
multi-server deployments where filesystem storage is not shared.

Each station's constituents are stored as a JSON artifact with an
in-memory index for fast station_id → artifact_id lookups.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConstituentStorage:
    """Manages tidal constituent storage via chuk-artifacts.

    Uses the configured artifact store backend (memory, filesystem, S3)
    for all persistence.  An in-memory cache provides fast lookups
    within the current process.

    Parameters
    ----------
    artifact_store : ArtifactStore
        The chuk-artifacts store instance.  Required.
    """

    def __init__(self, artifact_store: Any) -> None:
        self._store = artifact_store
        # In-memory cache: station_id → constituent dict
        self._cache: dict[str, dict[str, Any]] = {}
        # Artifact index: station_id → artifact_id
        self._artifact_index: dict[str, str] = {}

    @property
    def storage_provider(self) -> str:
        """Return a human-readable storage provider name."""
        return getattr(self._store, "storage_provider", "artifacts")

    # ── Save ──────────────────────────────────────────────────────────────

    async def save(self, station_id: str, data: dict[str, Any]) -> bool:
        """Save constituent data for a station.

        Stores to the artifact store and updates the in-memory cache.

        Returns True on success.
        """
        self._cache[station_id] = data

        try:
            json_bytes = json.dumps(data, indent=2).encode("utf-8")
            artifact_id = await self._store.store(
                data=json_bytes,
                mime="application/json",
                summary=f"Tidal constituents: {station_id}",
                filename=f"constituents/{station_id}.json",
                meta={"station_id": station_id, "type": "tidal_constituents"},
            )
            self._artifact_index[station_id] = artifact_id
            logger.info(
                "Stored constituents for %s (artifact_id=%s)",
                station_id, artifact_id,
            )
            return True
        except Exception as exc:
            logger.error(
                "Failed to store constituents for %s: %s",
                station_id, exc,
            )
            return False

    # ── Load ──────────────────────────────────────────────────────────────

    async def load(self, station_id: str) -> dict[str, Any]:
        """Load constituent data for a station.

        Checks in order: in-memory cache → artifact store.

        Raises FileNotFoundError if the station has no stored constituents.
        """
        # 1. In-memory cache
        if station_id in self._cache:
            return self._cache[station_id]

        # 2. Artifact store
        if station_id in self._artifact_index:
            artifact_id = self._artifact_index[station_id]
            try:
                raw = await self._store.retrieve(artifact_id)
                data = json.loads(raw.decode("utf-8"))
                self._cache[station_id] = data
                return data
            except Exception as exc:
                logger.warning(
                    "Failed to load constituents for %s from artifact store: %s",
                    station_id, exc,
                )

        raise FileNotFoundError(
            f"No stored constituents for station '{station_id}'.  "
            f"Run analyze_harmonics first."
        )

    # ── List ──────────────────────────────────────────────────────────────

    async def list_stations(self) -> list[dict[str, Any]]:
        """List all stations that have stored constituents."""
        stations: list[dict[str, Any]] = []
        for station_id, data in self._cache.items():
            stations.append(self._station_summary(station_id, data))
        return stations

    def stored_count(self) -> int:
        """Return the number of stations with stored constituents."""
        return len(self._cache)

    @staticmethod
    def _station_summary(station_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Build a summary dict from constituent data."""
        return {
            "station_id": data.get("station_id", station_id),
            "lat": data.get("lat"),
            "tidal_type": data.get("tidal_type", "unknown"),
            "form_number": data.get("form_number"),
            "constituent_count": len(
                data.get("constituents", {}).get("name", [])
            ),
            "fitted_date": data.get("fitted_date"),
        }
