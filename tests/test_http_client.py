"""Tests for the resilient HTTP client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from chuk_mcp_tides.core.http_client import ResilientClient


@pytest.fixture
def client():
    return ResilientClient(timeout=5.0, max_retries=2, rate_limit=0)


async def test_successful_get(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(return_value=mock_resp)
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        resp = await client.get("https://example.com/api")
        assert resp.status_code == 200


async def test_retry_on_500(client):
    fail_resp = MagicMock()
    fail_resp.status_code = 500

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(side_effect=[fail_resp, ok_resp])
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with patch.object(client, "_backoff_delay", return_value=0):
            resp = await client.get("https://example.com/api")
            assert resp.status_code == 200
            assert mock_httpx.get.call_count == 2


async def test_retry_on_429(client):
    rate_resp = MagicMock()
    rate_resp.status_code = 429

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(side_effect=[rate_resp, ok_resp])
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with patch.object(client, "_backoff_delay", return_value=0):
            resp = await client.get("https://example.com/api")
            assert resp.status_code == 200


async def test_exhausted_retries_raises(client):
    fail_resp = MagicMock()
    fail_resp.status_code = 503
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=fail_resp
    )

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(return_value=fail_resp)
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with patch.object(client, "_backoff_delay", return_value=0):
            with pytest.raises(httpx.HTTPStatusError):
                await client.get("https://example.com/api")
            # 1 initial + 2 retries = 3 calls
            assert mock_httpx.get.call_count == 3


async def test_network_error_retries(client):
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(
        side_effect=[httpx.ConnectError("timeout"), ok_resp]
    )
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with patch.object(client, "_backoff_delay", return_value=0):
            resp = await client.get("https://example.com/api")
            assert resp.status_code == 200


async def test_network_error_exhausted(client):
    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(
        side_effect=httpx.ConnectError("connection refused")
    )
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with patch.object(client, "_backoff_delay", return_value=0):
            with pytest.raises(httpx.ConnectError):
                await client.get("https://example.com/api")


async def test_non_retryable_status_raises_immediately(client):
    fail_resp = MagicMock()
    fail_resp.status_code = 404
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=fail_resp
    )

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(return_value=fail_resp)
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://example.com/api")
        # No retries for 404
        assert mock_httpx.get.call_count == 1


def test_backoff_delay():
    c = ResilientClient(backoff_base=1.0, backoff_max=16.0)
    assert c._backoff_delay(0) == 1.0
    assert c._backoff_delay(1) == 2.0
    assert c._backoff_delay(2) == 4.0
    assert c._backoff_delay(10) == 16.0  # capped


async def test_rate_limiting():
    c = ResilientClient(rate_limit=100.0)  # 100 req/sec = 10ms interval
    assert c._min_interval == pytest.approx(0.01)


async def test_base_url_prepended():
    c = ResilientClient(base_url="https://api.example.com", rate_limit=0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(return_value=mock_resp)
    mock_httpx.is_closed = False

    with patch.object(c, "_ensure_client", return_value=mock_httpx):
        await c.get("/endpoint")
        mock_httpx.get.assert_called_once_with(
            "https://api.example.com/endpoint", params=None
        )


async def test_absolute_url_not_prepended():
    c = ResilientClient(base_url="https://api.example.com", rate_limit=0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(return_value=mock_resp)
    mock_httpx.is_closed = False

    with patch.object(c, "_ensure_client", return_value=mock_httpx):
        await c.get("https://other.com/api")
        mock_httpx.get.assert_called_once_with(
            "https://other.com/api", params=None
        )


async def test_close():
    c = ResilientClient(rate_limit=0)
    mock_httpx = AsyncMock()
    mock_httpx.is_closed = False
    c._client = mock_httpx

    await c.close()
    mock_httpx.aclose.assert_called_once()
    assert c._client is None


async def test_params_passed_through(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None

    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(return_value=mock_resp)
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        await client.get("https://example.com/api", params={"key": "val"})
        mock_httpx.get.assert_called_once_with(
            "https://example.com/api", params={"key": "val"}
        )
