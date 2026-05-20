"""
Async HTTP client with connection pooling for the FaithUp Discord bot.

Provides a shared httpx.AsyncClient configured with connection pooling
to reduce overhead of establishing new connections for each request.
"""

import os
import logging
from typing import Optional, Any, Dict
import httpx
from httpx import AsyncClient, Limits, Timeout

logger = logging.getLogger("red.cogfaithup.async_http_client")

# Configuration via environment variables
POOL_CONNECTIONS = int(os.getenv("HTTP_POOL_CONNECTIONS", "10"))
POOL_MAXSIZE = int(os.getenv("HTTP_POOL_MAXSIZE", "10"))
MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))


class AsyncHTTPClient:
    """Singleton async HTTP client with connection pooling."""

    _instance: Optional["AsyncHTTPClient"] = None
    _client: Optional[AsyncClient] = None

    def __new__(cls) -> "AsyncHTTPClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self) -> None:
        """Initialize the async client with pooling and retry configuration."""
        limits = Limits(
            max_connections=POOL_MAXSIZE,
            max_keepalive_connections=POOL_CONNECTIONS,
            keepalive_expiry=300,
        )
        timeout = Timeout(TIMEOUT)
        self._client = AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
        )

        logger.debug(
            "Async HTTP client initialized with max_connections=%s, "
            "max_keepalive_connections=%s",
            POOL_MAXSIZE,
            POOL_CONNECTIONS,
        )

    @property
    def client(self) -> AsyncClient:
        """Get the shared async client."""
        if self._client is None:
            self._init_client()
        return self._client

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> httpx.Response:
        """Perform an async GET request using the pooled client."""
        timeout = timeout or TIMEOUT
        return await self.client.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def post(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> httpx.Response:
        """Perform an async POST request using the pooled client."""
        timeout = timeout or TIMEOUT
        return await self.client.post(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def put(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> httpx.Response:
        """Perform an async PUT request using the pooled client."""
        timeout = timeout or TIMEOUT
        return await self.client.put(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> httpx.Response:
        """Perform an async DELETE request using the pooled client."""
        timeout = timeout or TIMEOUT
        return await self.client.delete(
            url,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Perform a generic async request using the pooled client."""
        timeout = kwargs.pop("timeout", TIMEOUT)
        return await self.client.request(method, url, timeout=timeout, **kwargs)

    async def close(self) -> None:
        """Close the underlying client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global instance for easy import
async_http_client = AsyncHTTPClient()
get_async_client = async_http_client.client
aget = async_http_client.get
apost = async_http_client.post
aput = async_http_client.put
adelete = async_http_client.delete
arequest = async_http_client.request
