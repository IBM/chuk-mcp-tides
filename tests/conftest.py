"""Shared fixtures for chuk-mcp-tides tests."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from chuk_mcp_tides.constants import TideProvider
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


# ---------------------------------------------------------------------------
# HTTP mocking helpers
# ---------------------------------------------------------------------------


def make_mock_response(json_data, status_code=200):
    """Create a mock httpx.Response with the given JSON data."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data) if isinstance(json_data, (dict, list)) else str(json_data)
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def mock_httpx():
    """Fixture that patches httpx.AsyncClient to return canned responses.

    Usage::

        def test_something(mock_httpx):
            set_responses, mock_client = mock_httpx
            set_responses([make_mock_response({...})])
            # call async provider methods
    """
    responses: list = []
    call_index = [0]

    async def _mock_get(*args, **kwargs):
        if call_index[0] < len(responses):
            resp = responses[call_index[0]]
            call_index[0] += 1
            return resp
        return make_mock_response({})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=_mock_get)

    with patch("httpx.AsyncClient") as MockClient:
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_cm

        def set_responses(resps):
            responses.clear()
            responses.extend(resps)
            call_index[0] = 0

        yield set_responses, mock_client


@pytest.fixture
def mock_resilient():
    """Fixture that patches ResilientClient.get to return canned responses.

    All providers now use ResilientClient for HTTP.  This fixture replaces
    mock_httpx for provider-level tests.

    Usage::

        def test_something(mock_resilient, make_response):
            mock_resilient([make_response({...})])
            # call async provider methods
    """
    from chuk_mcp_tides.core.http_client import ResilientClient

    responses: list = []
    call_index = [0]

    async def _mock_get(self, url, params=None):
        if call_index[0] < len(responses):
            resp = responses[call_index[0]]
            call_index[0] += 1
            return resp
        return make_mock_response({})

    def set_responses(resps):
        responses.clear()
        responses.extend(resps)
        call_index[0] = 0

    with patch.object(ResilientClient, "get", _mock_get):
        yield set_responses


# ---------------------------------------------------------------------------
# Mock TideManager for tool tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_manager():
    """A MagicMock that quacks like TideManager for tool tests."""
    mgr = MagicMock(spec=TideManager)
    mgr.resolve_provider.return_value = TideProvider.NOAA
    mgr.default_datum.return_value = "MLLW"
    mgr.determine_tide_state.return_value = ("rising", None, None)

    # Async methods default to empty returns — override per test
    mgr.list_stations = AsyncMock(return_value=[])
    mgr.get_station_detail = AsyncMock(return_value={})
    mgr.find_nearest = AsyncMock(return_value=[])
    mgr.get_predictions = AsyncMock(return_value={"predictions": []})
    mgr.predict_local = AsyncMock(
        return_value={"predictions": [], "highs_lows": [], "constituent_count": 0}
    )
    mgr.get_observations = AsyncMock(return_value={"readings": []})
    mgr.get_latest = AsyncMock(return_value={})
    mgr.threshold_exceedance = AsyncMock(
        return_value={"groups": [], "total_exceedances": 0, "total_hours_above": 0.0}
    )
    mgr.project_flooding = AsyncMock(return_value={"projections": [], "tipping_points": []})
    mgr.harmonic_analysis = AsyncMock(return_value={"constituents": []})
    mgr.compute_residual = AsyncMock(
        return_value={
            "residuals": [],
            "surge_events": [],
            "max_positive_surge": {},
            "max_negative_surge": {},
        }
    )
    mgr.get_sea_level_trend = AsyncMock(return_value={})
    mgr.get_extreme_levels = AsyncMock(return_value={"top_ten_high": [], "top_ten_low": []})
    mgr.get_flood_outlook = AsyncMock(return_value={"counts": []})
    mgr.flooding_calendar = AsyncMock(return_value={"monthly_summary": [], "flood_days": []})
    mgr.list_current_stations = AsyncMock(return_value=[])
    mgr.get_current_predictions = AsyncMock(return_value={"predictions": []})
    mgr.get_current_latest = AsyncMock(return_value={})
    return mgr


# ---------------------------------------------------------------------------
# Convenience fixture for accessing the helper function
# ---------------------------------------------------------------------------


@pytest.fixture
def make_response():
    """Expose make_mock_response as a fixture for test modules."""
    return make_mock_response
