"""Authentication module for YouVersion API."""

import base64
import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from async_http_client import apost

# Load environment variables
load_dotenv()


class YouVersionAuthenticator:
    """Handles authentication for YouVersion API using OAuth2."""

    # API Configuration
    AUTH_URL = "https://auth.youversionapi.com/token"
    CLIENT_ID = base64.b64decode(
        "ODViNjFkOTdhNzliOTZiZTQ2NWViYWVlZTgzYjEzMTM="
    ).decode()
    CLIENT_SECRET = base64.b64decode(
        "NzVjZjBlMTQxY2JmNDFlZjQxMGFkY2U1YjY1MzdhNDk="
    ).decode()

    # Default headers for API requests
    DEFAULT_HEADERS = {
        "Referer": "http://android.youversionapi.com/",
        "X-YouVersion-App-Platform": "android",
        "X-YouVersion-App-Version": "17114",
        "X-YouVersion-Client": "youversion",
    }

    def __init__(self):
        """Initialize authenticator with credentials from environment."""
        self.username = os.getenv("YOUVERSION_USERNAME")
        self.password = os.getenv("YOUVERSION_PASSWORD")
        self._access_token = None
        self._token_expiry = None
        self._user_id = None

        if not self.username or not self.password:
            raise ValueError(
                "YOUVERSION_USERNAME and YOUVERSION_PASSWORD environment "
                "variables must be set. Create a .env file with these values."
            )

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            ValueError: If authentication fails
        """
        if self._is_token_valid():
            return self._access_token

        return await self._authenticate()

    def _is_token_valid(self) -> bool:
        """Check if the current token is still valid.

        Returns:
            True if token is valid and not expired
        """
        if not self._access_token or not self._token_expiry:
            return False

        # Add a 60-second buffer to avoid using tokens that are about to expire
        return time.time() < (self._token_expiry - 60)

    async def _authenticate(self) -> str:
        """Authenticate with YouVersion API and get access token.

        Returns:
            Access token

        Raises:
            ValueError: If authentication fails
        """
        try:
            response = await apost(
                self.AUTH_URL,
                data={
                    "client_id": self.CLIENT_ID,
                    "client_secret": self.CLIENT_SECRET,
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                },
                headers=self.DEFAULT_HEADERS,
                timeout=10,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )

            token_data = response.json()
            self._access_token = token_data["access_token"]

            # Set token expiry (default to 1 hour if not provided)
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in

            # Extract user_id from token if possible
            self._extract_user_info(token_data["access_token"])

            return self._access_token

        except httpx.RequestError as e:
            raise ValueError(f"Authentication request failed: {e}")

    def _extract_user_info(self, token: str) -> None:
        """Extract user information from JWT token.

        Args:
            token: JWT access token
        """
        try:
            # Simple extraction without full JWT validation
            # The token format is: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                return

            import base64
            import json

            # Decode the payload (middle part)
            payload = parts[1]
            # Add padding if needed
            payload += "=" * (4 - len(payload) % 4)
            decoded_payload = base64.b64decode(payload)
            payload_data = json.loads(decoded_payload)

            # Extract user_id from payload
            self._user_id = payload_data.get("user_id") or payload_data.get("sub")

        except Exception:
            # If extraction fails, continue without user_id
            pass

    async def get_auth_headers(self) -> dict:
        """Get headers with authentication for API requests.

        Returns:
            Dictionary with authentication headers
        """
        token = await self.get_access_token()
        return {**self.DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}

    @property
    def user_id(self) -> Optional[int]:
        """Get the authenticated user ID.

        Returns:
            User ID if available, None otherwise
        """
        return self._user_id
