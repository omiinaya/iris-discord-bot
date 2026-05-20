"""
HTTP client with connection pooling for the FaithUp Discord bot.

Provides a shared requests.Session configured with connection pooling
to reduce overhead of establishing new connections for each request.
"""

import os
import logging
from typing import Optional, Any, Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("red.cogfaithup.http_client")

# Configuration via environment variables
POOL_CONNECTIONS = int(os.getenv("HTTP_POOL_CONNECTIONS", "10"))
POOL_MAXSIZE = int(os.getenv("HTTP_POOL_MAXSIZE", "10"))
MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))


class HTTPClient:
    """Singleton HTTP client with connection pooling."""

    _instance: Optional["HTTPClient"] = None
    _session: Optional[requests.Session] = None

    def __new__(cls) -> "HTTPClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_session()
        return cls._instance

    def _init_session(self) -> None:
        """Initialize the session with pooling and retry configuration."""
        self._session = requests.Session()

        # Create adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=POOL_CONNECTIONS,
            pool_maxsize=POOL_MAXSIZE,
            max_retries=Retry(
                total=MAX_RETRIES,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            ),
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        logger.debug(
            "HTTP session initialized with pool_connections=%s, "
            "pool_maxsize=%s, max_retries=%s",
            POOL_CONNECTIONS,
            POOL_MAXSIZE,
            MAX_RETRIES,
        )

    @property
    def session(self) -> requests.Session:
        """Get the shared session."""
        if self._session is None:
            self._init_session()
        return self._session

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """Perform a GET request using the pooled session."""
        return self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout or TIMEOUT,
            **kwargs,
        )

    def post(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """Perform a POST request using the pooled session."""
        return self.session.post(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout or TIMEOUT,
            **kwargs,
        )

    def put(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """Perform a PUT request using the pooled session."""
        return self.session.put(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout or TIMEOUT,
            **kwargs,
        )

    def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """Perform a DELETE request using the pooled session."""
        return self.session.delete(
            url,
            headers=headers,
            timeout=timeout or TIMEOUT,
            **kwargs,
        )

    def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """Perform a generic request using the pooled session."""
        timeout = kwargs.pop("timeout", TIMEOUT)
        return self.session.request(method, url, timeout=timeout, **kwargs)


# Global instance for easy import
http_client = HTTPClient()
get_session = http_client.session
get = http_client.get
post = http_client.post
put = http_client.put
delete = http_client.delete
request = http_client.request
