"""Shared fixtures for chuk-mcp-tides tests."""

import pytest

from chuk_mcp_tides.core.tide_manager import TideManager

# ---------------------------------------------------------------------------
# Mock MCP server — collects registered tools without a real MCP runtime
# ---------------------------------------------------------------------------


class MockMCPServer:
    """Minimal MCP server mock that captures tools registered via @mcp.tool."""

    def __init__(self) -> None:
        self._tools: dict[str, object] = {}

    def tool(self, fn: object) -> object:
        """Decorator that registers the function and returns it unchanged."""
        self._tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    def get_tool(self, name: str) -> object:
        return self._tools[name]

    def get_tools(self) -> list[object]:
        return list(self._tools.values())


@pytest.fixture
def mock_mcp() -> MockMCPServer:
    return MockMCPServer()


# ---------------------------------------------------------------------------
# TideManager fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tide_manager() -> TideManager:
    """Fresh TideManager with no cached data."""
    return TideManager()
