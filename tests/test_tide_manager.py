"""Tests for TideManager."""

from chuk_mcp_tides.constants import TideProvider
from chuk_mcp_tides.core.tide_manager import TideManager


def test_default_provider(tide_manager: TideManager):
    assert tide_manager.default_provider == TideProvider.NOAA


def test_resolve_provider_none(tide_manager: TideManager):
    assert tide_manager.resolve_provider(None) == TideProvider.NOAA


def test_resolve_provider_valid(tide_manager: TideManager):
    assert tide_manager.resolve_provider("ea") == TideProvider.EA
    assert tide_manager.resolve_provider("ukho") == TideProvider.UKHO
    assert tide_manager.resolve_provider("local") == TideProvider.LOCAL


def test_resolve_provider_invalid(tide_manager: TideManager):
    assert tide_manager.resolve_provider("invalid") == TideProvider.NOAA


def test_cache_set_and_get(tide_manager: TideManager):
    tide_manager.set_cached("key1", {"data": 42})
    result = tide_manager.get_cached("key1")
    assert result == {"data": 42}


def test_cache_miss(tide_manager: TideManager):
    result = tide_manager.get_cached("nonexistent")
    assert result is None
