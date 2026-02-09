"""Tests for discovery tools."""

import json

import pytest

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
