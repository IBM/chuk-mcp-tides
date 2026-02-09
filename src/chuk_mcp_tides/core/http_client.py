"""
Resilient HTTP client for chuk-mcp-tides.

Provides connection pooling, retry with exponential backoff,
and per-provider rate limiting.  All providers share a single
instance per provider type.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0  # seconds
DEFAULT_BACKOFF_MAX = 16.0  # seconds
DEFAULT_RATE_LIMIT_PER_SECOND = 5.0

# HTTP status codes that are safe to retry
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class ResilientClient:
    """HTTP client with retry, backoff, and rate limiting.

    Parameters
    ----------
    base_url : str, optional
        Common base URL prepended to all requests.
    timeout : float
        Request timeout in seconds.
    max_retries : int
        Maximum number of retry attempts for transient failures.
    backoff_base : float
        Base delay in seconds for exponential backoff.
    backoff_max : float
        Maximum backoff delay in seconds.
    rate_limit : float
        Maximum requests per second (0 = unlimited).
    headers : dict, optional
        Default headers sent with every request.
    """

    def __init__(
        self,
        base_url: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
        rate_limit: float = DEFAULT_RATE_LIMIT_PER_SECOND,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._min_interval = 1.0 / rate_limit if rate_limit > 0 else 0.0
        self._last_request_time = 0.0
        self._rate_lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._headers = headers or {}

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily create the shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self) -> None:
        """Enforce the per-provider rate limit."""
        if self._min_interval <= 0:
            return
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

    async def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Send a GET request with retry and rate limiting.

        Parameters
        ----------
        url : str
            The URL to fetch (absolute, or relative to *base_url*).
        params : dict, optional
            Query parameters.

        Returns
        -------
        httpx.Response
            The successful response.

        Raises
        ------
        httpx.HTTPStatusError
            If all retries are exhausted on a server error.
        httpx.RequestError
            If a network error occurs on all retries.
        """
        full_url = f"{self._base_url}{url}" if not url.startswith("http") else url
        client = await self._ensure_client()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            await self._rate_limit()

            try:
                resp = await client.get(full_url, params=params)

                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    if attempt < self._max_retries:
                        delay = self._backoff_delay(attempt)
                        logger.warning(
                            "HTTP %d from %s, retrying in %.1fs (attempt %d/%d)",
                            resp.status_code,
                            full_url,
                            delay,
                            attempt + 1,
                            self._max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue

                resp.raise_for_status()
                return resp

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Request error for %s: %s, retrying in %.1fs (attempt %d/%d)",
                        full_url,
                        exc,
                        delay,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        # If we exhausted retries on a server error status, raise
        if last_exc is not None:
            raise last_exc
        raise httpx.HTTPStatusError(
            f"Exhausted {self._max_retries} retries for {full_url}",
            request=httpx.Request("GET", full_url),
            response=resp,  # type: ignore[possibly-undefined]
        )

    def _backoff_delay(self, attempt: int) -> float:
        """Compute exponential backoff delay for an attempt."""
        delay = self._backoff_base * (2**attempt)
        return min(delay, self._backoff_max)
