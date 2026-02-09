"""Tests for ConstituentStorage (artifacts-only)."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from chuk_mcp_tides.core.constituent_storage import ConstituentStorage


SAMPLE_DATA = {
    "station_id": "TEST001",
    "lat": 41.8,
    "constituents": {
        "name": ["M2", "S2", "K1"],
        "A": [0.5, 0.2, 0.1],
        "g": [120.0, 150.0, 30.0],
        "aux": {"freq": [0.0805, 0.0833, 0.0418]},
    },
    "mean_level": 1.23,
    "form_number": 0.3,
    "tidal_type": "semidiurnal",
    "fitted_date": "2025-01-01T00:00:00Z",
}


@pytest.fixture
def mock_store():
    """Mock chuk-artifacts ArtifactStore."""
    store = MagicMock()
    store.store = AsyncMock(return_value="art-12345")
    store.retrieve = AsyncMock(
        return_value=json.dumps(SAMPLE_DATA).encode("utf-8")
    )
    store.storage_provider = "memory"
    return store


@pytest.fixture
def storage(mock_store):
    """ConstituentStorage backed by a mock artifact store."""
    return ConstituentStorage(artifact_store=mock_store)


# ── Basic operations ─────────────────────────────────────────────────────


async def test_save_stores_to_artifact_store(storage, mock_store):
    ok = await storage.save("TEST001", SAMPLE_DATA)
    assert ok is True

    mock_store.store.assert_called_once()
    call_kwargs = mock_store.store.call_args[1]
    assert call_kwargs["mime"] == "application/json"
    assert call_kwargs["filename"] == "constituents/TEST001.json"
    assert call_kwargs["meta"]["station_id"] == "TEST001"
    assert call_kwargs["meta"]["type"] == "tidal_constituents"


async def test_save_updates_cache(storage):
    await storage.save("TEST001", SAMPLE_DATA)
    assert "TEST001" in storage._cache


async def test_load_from_cache(storage):
    """After save, load returns cached data (no artifact store call)."""
    await storage.save("TEST001", SAMPLE_DATA)

    mock_store = storage._store
    mock_store.retrieve.reset_mock()

    loaded = await storage.load("TEST001")
    assert loaded["station_id"] == "TEST001"
    assert loaded["lat"] == 41.8
    mock_store.retrieve.assert_not_called()


async def test_load_from_artifact_store(storage, mock_store):
    """When cache is cleared, load fetches from artifact store."""
    await storage.save("TEST001", SAMPLE_DATA)
    storage._cache.clear()

    loaded = await storage.load("TEST001")
    assert loaded["station_id"] == "TEST001"
    mock_store.retrieve.assert_called_once_with("art-12345")


async def test_load_not_found(storage):
    with pytest.raises(FileNotFoundError, match="No stored constituents"):
        await storage.load("NONEXISTENT")


async def test_list_stations(storage):
    await storage.save("A001", {**SAMPLE_DATA, "station_id": "A001"})
    await storage.save("A002", {**SAMPLE_DATA, "station_id": "A002"})

    stations = await storage.list_stations()
    ids = {s["station_id"] for s in stations}
    assert "A001" in ids
    assert "A002" in ids


async def test_stored_count(storage):
    assert storage.stored_count() == 0
    await storage.save("A001", SAMPLE_DATA)
    assert storage.stored_count() == 1


async def test_storage_provider(storage):
    assert storage.storage_provider == "memory"


# ── Cache behaviour ──────────────────────────────────────────────────────


async def test_cache_hit_returns_same_object(storage):
    await storage.save("TEST001", SAMPLE_DATA)
    loaded1 = await storage.load("TEST001")
    loaded2 = await storage.load("TEST001")
    assert loaded1 is loaded2


# ── Error handling ───────────────────────────────────────────────────────


async def test_save_failure_returns_false(storage, mock_store):
    mock_store.store.side_effect = RuntimeError("Store unavailable")

    ok = await storage.save("TEST001", SAMPLE_DATA)
    assert ok is False
    # Data is still cached in memory even if artifact store failed
    assert "TEST001" in storage._cache


async def test_load_artifact_failure_raises(storage, mock_store):
    """If artifact store fails during load and no cache, raise."""
    await storage.save("TEST001", SAMPLE_DATA)
    storage._cache.clear()

    mock_store.retrieve.side_effect = RuntimeError("Retrieve failed")

    with pytest.raises(FileNotFoundError):
        await storage.load("TEST001")


# ── Station summary ──────────────────────────────────────────────────────


async def test_station_summary_fields(storage):
    await storage.save("TEST001", SAMPLE_DATA)

    stations = await storage.list_stations()
    assert len(stations) == 1
    s = stations[0]
    assert s["station_id"] == "TEST001"
    assert s["lat"] == 41.8
    assert s["tidal_type"] == "semidiurnal"
    assert s["form_number"] == 0.3
    assert s["constituent_count"] == 3
    assert s["fitted_date"] == "2025-01-01T00:00:00Z"
