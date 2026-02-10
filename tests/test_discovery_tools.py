"""Tests for discovery tools."""

import json

import pytest

from chuk_mcp_tides.constants import TideProvider
from chuk_mcp_tides.core.tide_manager import TideManager
from chuk_mcp_tides.tools.discovery.api import register_discovery_tools


@pytest.fixture
def discovery_tools(mock_mcp):
    manager = TideManager()
    register_discovery_tools(mock_mcp, manager)
    return mock_mcp


async def test_tides_status(discovery_tools):
    result = await discovery_tools.get_tool("tides_status")()
    parsed = json.loads(result)
    assert parsed["server"] == "chuk-mcp-tides"
    assert parsed["version"] == "0.4.0"
    assert len(parsed["providers"]) == 4


async def test_tides_status_text(discovery_tools):
    result = await discovery_tools.get_tool("tides_status")(output_mode="text")
    assert "chuk-mcp-tides" in result
    assert "NOAA" in result


async def test_tides_status_has_harmonic_engine(discovery_tools):
    result = await discovery_tools.get_tool("tides_status")()
    parsed = json.loads(result)
    assert "harmonic_engine" in parsed
    assert "utide" in parsed["harmonic_engine"]


async def test_tides_capabilities(discovery_tools):
    result = await discovery_tools.get_tool("tides_capabilities")()
    parsed = json.loads(result)
    assert parsed["server"] == "chuk-mcp-tides"
    assert parsed["tool_count"] == 17
    assert len(parsed["providers"]) == 4
    assert any(p["short_name"] == "noaa" for p in parsed["providers"])
    assert len(parsed["datums"]) > 0
    assert len(parsed["scenarios"]) > 0
    assert len(parsed["cross_server_workflows"]) == 2


async def test_tides_capabilities_text(discovery_tools):
    result = await discovery_tools.get_tool("tides_capabilities")(output_mode="text")
    assert "18" in result
    assert "NOAA" in result
    assert "MLLW" in result


async def test_tides_capabilities_providers(discovery_tools):
    result = await discovery_tools.get_tool("tides_capabilities")()
    parsed = json.loads(result)
    noaa = next(p for p in parsed["providers"] if p["short_name"] == "noaa")
    assert noaa["auth_required"] is False
    assert noaa["station_count"] > 0
    ukho = next(p for p in parsed["providers"] if p["short_name"] == "ukho")
    assert ukho["auth_required"] is True


async def test_tides_status_storage_unavailable(mock_mcp, monkeypatch):
    """When local provider storage is unavailable, falls back to env var."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("CHUK_ARTIFACTS_PROVIDER", "s3")
    manager = TideManager()
    register_discovery_tools(mock_mcp, manager)

    # Inject a mock local provider whose storage attribute raises
    mock_local = MagicMock()
    mock_local.storage = property(lambda self: (_ for _ in ()).throw(RuntimeError("no storage")))
    type(mock_local).storage = property(lambda self: (_ for _ in ()).throw(RuntimeError("broken")))
    manager._providers[TideProvider.LOCAL] = mock_local

    result = await mock_mcp.get_tool("tides_status")()
    parsed = json.loads(result)
    assert parsed["server"] == "chuk-mcp-tides"
    # storage_provider should fall back to env var "s3"
    assert parsed["storage_provider"] == "s3"


async def test_tides_status_utide_not_installed(mock_mcp, monkeypatch):
    """When utide is not importable, harmonic_engine shows 'not installed'."""
    import builtins
    import sys

    # Remove utide from sys.modules so it gets re-imported
    utide_mod = sys.modules.pop("utide", None)

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "utide":
            raise ImportError("No module named 'utide'")
        return original_import(name, *args, **kwargs)

    manager = TideManager()
    register_discovery_tools(mock_mcp, manager)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    result = await mock_mcp.get_tool("tides_status")()
    parsed = json.loads(result)
    assert "not installed" in parsed["harmonic_engine"]

    # Restore utide module
    if utide_mod is not None:
        sys.modules["utide"] = utide_mod


async def test_tides_status_stored_count_fails(mock_mcp):
    """When stored_count raises, stored_constituents should be 0."""
    from unittest.mock import MagicMock

    manager = TideManager()
    register_discovery_tools(mock_mcp, manager)

    # Mock the local provider to have storage that fails on stored_count
    mock_local = MagicMock()
    mock_local.storage.storage_provider = "memory"
    mock_local.storage.stored_count.side_effect = RuntimeError("storage error")
    manager._providers[TideProvider.LOCAL] = mock_local

    result = await mock_mcp.get_tool("tides_status")()
    parsed = json.loads(result)
    assert parsed["stored_constituents"] == 0
