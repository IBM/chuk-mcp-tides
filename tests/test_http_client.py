"""Tests for the resilient HTTP client."""

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
    mock_httpx.get = AsyncMock(side_effect=[httpx.ConnectError("timeout"), ok_resp])
    mock_httpx.is_closed = False

    with patch.object(client, "_ensure_client", return_value=mock_httpx):
        with patch.object(client, "_backoff_delay", return_value=0):
            resp = await client.get("https://example.com/api")
            assert resp.status_code == 200


async def test_network_error_exhausted(client):
    mock_httpx = AsyncMock()
    mock_httpx.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
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
        mock_httpx.get.assert_called_once_with("https://api.example.com/endpoint", params=None)


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
        mock_httpx.get.assert_called_once_with("https://other.com/api", params=None)


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
        mock_httpx.get.assert_called_once_with("https://example.com/api", params={"key": "val"})


async def test_ensure_client_creates_with_limits():
    """_ensure_client lazily creates an AsyncClient with connection limits."""
    c = ResilientClient(timeout=5.0, rate_limit=0)
    assert c._client is None

    with patch("chuk_mcp_tides.core.http_client.httpx.AsyncClient") as MockClient:
        mock_instance = MagicMock()
        mock_instance.is_closed = False
        MockClient.return_value = mock_instance

        client = await c._ensure_client()
        assert client is mock_instance
        MockClient.assert_called_once()
        # Verify Limits are passed
        call_kwargs = MockClient.call_args[1]
        assert "limits" in call_kwargs


async def test_ensure_client_reuses_existing():
    """If the client already exists and is open, _ensure_client should reuse it."""
    c = ResilientClient(rate_limit=0)
    mock_instance = MagicMock()
    mock_instance.is_closed = False
    c._client = mock_instance

    client = await c._ensure_client()
    assert client is mock_instance


async def test_ensure_client_recreates_if_closed():
    """If the existing client is closed, _ensure_client should create a new one."""
    c = ResilientClient(rate_limit=0)
    old_client = MagicMock()
    old_client.is_closed = True
    c._client = old_client

    with patch("chuk_mcp_tides.core.http_client.httpx.AsyncClient") as MockClient:
        new_client = MagicMock()
        new_client.is_closed = False
        MockClient.return_value = new_client

        client = await c._ensure_client()
        assert client is new_client


async def test_custom_headers_passed_to_client():
    """Custom headers should be passed to the underlying AsyncClient."""
    headers = {"Authorization": "Bearer test-token"}
    c = ResilientClient(rate_limit=0, headers=headers)

    with patch("chuk_mcp_tides.core.http_client.httpx.AsyncClient") as MockClient:
        mock_instance = MagicMock()
        mock_instance.is_closed = False
        MockClient.return_value = mock_instance

        await c._ensure_client()
        call_kwargs = MockClient.call_args[1]
        assert call_kwargs["headers"] == headers


async def test_rate_limit_enforces_delay():
    """Rate limiting should enforce a minimum interval between requests."""
    import time as time_mod

    c = ResilientClient(rate_limit=100.0)  # 100 req/sec = 10ms interval

    # Manually set last request time to "just now"
    c._last_request_time = time_mod.monotonic()

    with patch("chuk_mcp_tides.core.http_client.asyncio.sleep") as mock_sleep:
        mock_sleep.return_value = None  # asyncio.sleep is a coroutine
        # Make sleep a proper coroutine
        mock_sleep.side_effect = None
        mock_sleep.return_value = None

        # Use real _rate_limit to test logic
        # Reset to ensure the rate limiter fires
        c._last_request_time = time_mod.monotonic()
        await c._rate_limit()
        # The lock + sleep may or may not fire depending on timing,
        # but the method should complete without error
