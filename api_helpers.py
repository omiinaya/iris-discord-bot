import logging
from typing import Optional

from .async_http_client import aget

logger = logging.getLogger("red.cogfaithup.api_helpers")


async def fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Fetch JSON data from a URL, return dict or None on error."""
    try:
        response = await aget(url, timeout=timeout)
        content_type = response.headers.get("Content-Type", "")
        if response.status_code == 200 and "application/json" in content_type:
            return response.json()
        logger.warning(
            "Non-200 or non-JSON response from %s: %s", url, response.status_code
        )
    except Exception as e:
        logger.error("Error fetching %s: %s", url, e)
    return None
