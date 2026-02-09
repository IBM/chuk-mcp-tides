"""Tests for discovery tools."""

import json

import pytest

from chuk_mcp_tides.core.tide_manager import TideManager
from chuk_mcp_tides.tools.discovery.api import register_discovery_tools


class MockMCPServer:
    def __init__(self):
        self._tools = {}

    def tool(self, fn):
        self._tools[fn.__name__] = fn
        return fn


@pytest.fixture
def discovery_tools():
    mcp = MockMCPServer()
    manager = TideManager()
    register_discovery_tools(mcp, manager)
    return mcp._tools


@pytest.mark.asyncio
async def test_tides_status(discovery_tools):
    result = await discovery_tools["tides_status"]()
    parsed = json.loads(result)
    assert parsed["server"] == "chuk-mcp-tides"
    assert parsed["version"] == "0.1.0"
    assert len(parsed["providers"]) == 4


@pytest.mark.asyncio
async def test_tides_status_text(discovery_tools):
    result = await discovery_tools["tides_status"](output_mode="text")
    assert "chuk-mcp-tides" in result
    assert "NOAA" in result
