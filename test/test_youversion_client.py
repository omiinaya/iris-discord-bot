"""Unit tests for YouVersion client parallelization."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from youversion.client import YouVersionClient


class TestYouVersionClientParallel(unittest.TestCase):
    """Test parallel API calls in YouVersionClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = YouVersionClient()
        # Mock the underlying async HTTP client
        self.mock_async_client = AsyncMock()
        self.client._client = self.mock_async_client
        # Mock authenticator
        self.client.authenticator = AsyncMock()
        self.client.authenticator.get_auth_headers.return_value = {
            "Authorization": "Bearer fake_token"
        }

    def test_get_verse_texts_single(self):
        """Test get_verse_texts with a single reference."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {"data": {"content": "<span>verse</span>"}}
        }
        self.mock_async_client.get.return_value = mock_response

        # Run async test
        async def test():
            results = await self.client.get_verse_texts(["GEN.1.1"])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0], mock_response.json.return_value)
            # Verify call
            self.mock_async_client.get.assert_called_once()
            call_args = self.mock_async_client.get.call_args
            self.assertIn("reference=GEN.1", call_args[1]["params"]["reference"])

        asyncio.run(test())

    def test_get_verse_texts_multiple(self):
        """Test get_verse_texts with multiple references (parallel)."""
        # Mock responses
        mock_responses = []
        for i in range(3):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": {"data": {"content": f"verse{i}"}}
            }
            mock_responses.append(mock_response)
        self.mock_async_client.get.side_effect = mock_responses

        async def test():
            refs = ["GEN.1.1", "EXO.1.1", "LEV.1.1"]
            results = await self.client.get_verse_texts(refs)
            self.assertEqual(len(results), 3)
            for i, result in enumerate(results):
                self.assertEqual(result, mock_responses[i].json.return_value)
            # Should have been called three times
            self.assertEqual(self.mock_async_client.get.call_count, 3)

        asyncio.run(test())

    def test_get_verse_texts_error(self):
        """Test get_verse_texts when one request fails."""
        # Mock one failure, one success
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "response": {"data": {"content": "verse"}}
        }
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.text = "Not Found"
        self.mock_async_client.get.side_effect = [success_response, error_response]

        async def test():
            with self.assertRaises(ValueError):
                await self.client.get_verse_texts(["GEN.1.1", "INVALID.1.1"])
            # Ensure both calls were attempted (parallel)
            self.assertEqual(self.mock_async_client.get.call_count, 2)

        asyncio.run(test())

    def test_get_formatted_verse_of_the_day_parallel_fallback(self):
        """Test that get_formatted_verse_of_the_day uses parallel fetch."""
        # Mock VOTD data with multiple USFM references
        votd_data = {"usfm": ["GEN.1.1", "EXO.1.1"], "day": 1, "image_id": "test"}
        with patch.object(self.client, "get_verse_of_the_day", return_value=votd_data):
            # Mock get_verse_texts to succeed
            chapter_data = {"response": {"data": {"content": "<span>verse</span>"}}}
            with patch.object(
                self.client, "get_verse_texts", return_value=[chapter_data]
            ) as mock_parallel:

                async def test():
                    result = await self.client.get_formatted_verse_of_the_day(day=1)
                    self.assertEqual(result["usfm"], "GEN.1.1")
                    mock_parallel.assert_called_once_with(["GEN.1.1", "EXO.1.1"])

                asyncio.run(test())

    def test_get_formatted_verse_of_the_day_parallel_fails_fallback(self):
        """Test that when parallel fetch fails, it falls back to sequential."""
        votd_data = {"usfm": ["GEN.1.1", "EXO.1.1"], "day": 1, "image_id": "test"}
        with patch.object(self.client, "get_verse_of_the_day", return_value=votd_data):
            # Mock get_verse_texts to raise ValueError
            with patch.object(
                self.client,
                "get_verse_texts",
                side_effect=ValueError("Parallel failed"),
            ):
                # Mock get_verse_text to succeed
                chapter_data = {"response": {"data": {"content": "<span>verse</span>"}}}
                with patch.object(
                    self.client, "get_verse_text", return_value=chapter_data
                ) as mock_seq:

                    async def test():
                        result = await self.client.get_formatted_verse_of_the_day(day=1)
                        self.assertEqual(result["usfm"], "GEN.1.1")
                        mock_seq.assert_called_once_with("GEN.1.1")

                    asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
