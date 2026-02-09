"""Tests for ReferenceCache (two-tier reference data cache)."""

import json
import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from chuk_mcp_tides.core.reference_cache import ReferenceCache


SAMPLE_STATIONS = [
    {"station_id": "8454000", "name": "Providence", "lat": 41.8, "lon": -71.4},
    {"station_id": "8461490", "name": "New London", "lat": 41.35, "lon": -72.09},
]

SAMPLE_TREND = {
    "station_id": "8454000",
    "trend_mm_per_year": 3.5,
    "first_year": 1938,
    "last_year": 2023,
}


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.store = AsyncMock(return_value="art-ref-001")
    store.retrieve = AsyncMock(
        return_value=json.dumps(SAMPLE_STATIONS).encode("utf-8")
    )
    store.search = AsyncMock(return_value=[])
    return store


@pytest.fixture
def cache(mock_store):
    return ReferenceCache(artifact_store=mock_store)


# ── warm ────────────────────────────────────────────────────────────


async def test_warm_empty_store(cache, mock_store):
    count = await cache.warm()
    assert count == 0
    assert cache.warmed is True


async def test_warm_finds_existing_artifacts(cache, mock_store):
    meta = MagicMock()
    meta.meta = {"type": "tides_reference_cache", "cache_key": "stations|noaa"}
    meta.artifact_id = "art-existing-001"
    mock_store.search.return_value = [meta]

    count = await cache.warm()
    assert count == 1
    assert cache.indexed_count() == 1


async def test_warm_handles_store_failure(cache, mock_store):
    mock_store.search.side_effect = RuntimeError("Store unavailable")
    count = await cache.warm()
    assert count == 0
    assert cache.warmed is True


# ── put and get ─────────────────────────────────────────────────────


async def test_put_stores_in_both_tiers(cache, mock_store):
    cache._warmed = True
    await cache.put("stations|noaa", SAMPLE_STATIONS, ttl=86400)

    assert cache.cached_count() == 1
    mock_store.store.assert_called_once()
    call_kwargs = mock_store.store.call_args[1]
    assert call_kwargs["scope"] == "sandbox"
    assert call_kwargs["meta"]["type"] == "tides_reference_cache"
    assert call_kwargs["meta"]["cache_key"] == "stations|noaa"


async def test_get_from_memory(cache):
    cache._warmed = True
    await cache.put("stations|noaa", SAMPLE_STATIONS, ttl=86400)
    result = await cache.get("stations|noaa", ttl=86400)
    assert result == SAMPLE_STATIONS


async def test_get_miss_returns_none(cache):
    cache._warmed = True
    result = await cache.get("nonexistent", ttl=86400)
    assert result is None


async def test_get_from_artifact_on_memory_miss(cache, mock_store):
    cache._warmed = True
    cache._artifact_index["stations|noaa"] = "art-ref-001"
    mock_store.retrieve.return_value = json.dumps(SAMPLE_STATIONS).encode("utf-8")

    result = await cache.get("stations|noaa", ttl=86400)
    assert result == SAMPLE_STATIONS
    mock_store.retrieve.assert_called_once_with("art-ref-001")
    # Promoted to memory cache
    assert cache.cached_count() == 1


async def test_get_memory_ttl_expiry_falls_to_artifact(cache, mock_store):
    cache._warmed = True
    await cache.put("stations|noaa", SAMPLE_STATIONS, ttl=86400)

    # Manually expire the memory entry
    with cache._lock:
        cache._cache["stations|noaa"] = (SAMPLE_STATIONS, time.time() - 100000)

    # Memory miss, fall through to artifact tier
    mock_store.retrieve.return_value = json.dumps(SAMPLE_TREND).encode("utf-8")
    result = await cache.get("stations|noaa", ttl=86400)
    assert result == SAMPLE_TREND


async def test_get_triggers_warm_on_first_call(cache, mock_store):
    assert cache.warmed is False
    result = await cache.get("nonexistent", ttl=86400)
    assert cache.warmed is True
    mock_store.search.assert_called_once()


# ── error handling ──────────────────────────────────────────────────


async def test_put_artifact_failure_still_caches_memory(cache, mock_store):
    cache._warmed = True
    mock_store.store.side_effect = RuntimeError("S3 down")
    await cache.put("stations|noaa", SAMPLE_STATIONS, ttl=86400)
    assert cache.cached_count() == 1


async def test_get_artifact_retrieve_failure_cleans_index(cache, mock_store):
    cache._warmed = True
    cache._artifact_index["stations|noaa"] = "art-ref-001"
    mock_store.retrieve.side_effect = RuntimeError("S3 down")

    result = await cache.get("stations|noaa", ttl=86400)
    assert result is None
    assert "stations|noaa" not in cache._artifact_index


# ── helpers ─────────────────────────────────────────────────────────


def test_cached_count_empty(mock_store):
    cache = ReferenceCache(artifact_store=mock_store)
    assert cache.cached_count() == 0
    assert cache.indexed_count() == 0


def test_warmed_default_false(mock_store):
    cache = ReferenceCache(artifact_store=mock_store)
    assert cache.warmed is False
