"""API client for YouVersion Verse of the Day."""

import asyncio
import collections
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from async_http_client import get_async_client
from rate_limiter import get_limiter_from_env

from .auth import YouVersionAuthenticator

# Compiled regex patterns for performance
CONTENT_PATTERN = re.compile(r'<span class="content">(.*?)</span>', re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
VERSE_SPAN_PATTERN = re.compile(
    r'<span class="verse v(\d+)"[^>]*>(.*?)(?=<span class="verse v|\Z)', re.DOTALL
)
LABEL_CONTENT_PATTERN = re.compile(
    r'<span class="label">(\d+)</span>.*?<span class="content">(.*?)</span>', re.DOTALL
)
VERSE_SPAN_FALLBACK_PATTERN = re.compile(
    r'<span class="verse v(\d+)"[^>]*>(.*?)</span>', re.DOTALL
)

logger = logging.getLogger("red.cogfaithup.youversion")


class YouVersionClient:
    """Client for YouVersion API operations."""

    # API Endpoints
    VOTD_URL = "https://nodejs.bible.com/api/moments/votd/3.1"
    BIBLE_CHAPTER_URL = "https://bible.youversionapi.com/3.1/chapter.json"

    def __init__(self):
        """Initialize the YouVersion client."""
        self.authenticator = YouVersionAuthenticator()
        self._client = get_async_client
        self._votd_cache = collections.OrderedDict()  # day -> (ts, data)
        self._cache_ttl = 86400  # 24 hours in seconds
        self._cache_maxsize = 100  # maximum number of cached entries
        self._cache_lock = asyncio.Lock()
        # Rate limiter for YouVersion API calls
        self._rate_limiter = get_limiter_from_env(
            "YOUVERSION", default_max_calls=30, default_period=60
        )

    async def get_verse_of_the_day(self, day: Optional[int] = None) -> Dict[str, Any]:
        """Get the verse of the day.

        Args:
            day: Specific day number (1-365/366). Defaults to current day.

        Returns:
            Dictionary containing verse data

        Raises:
            ValueError: If API request fails or verse not found
        """
        if day is None:
            day = datetime.now().timetuple().tm_yday

        try:
            # VOTD endpoint doesn't require authentication
            # matches original package
            headers = {
                "Referer": "http://android.youversionapi.com/",
                "X-YouVersion-App-Platform": "android",
                "X-YouVersion-App-Version": "17114",
                "X-YouVersion-Client": "youversion",
            }
            # Apply rate limiting
            await self._rate_limiter.acquire()
            response = await self._client.get(
                self.VOTD_URL, headers=headers, timeout=10
            )

            if response.status_code != 200:
                raise ValueError(f"VOTD API request failed: {response.status_code}")

            data = response.json()
            votd_data = data.get("votd", [])

            # Find verse for the requested day - matches original package logic
            for verse in votd_data:
                if verse.get("day") == day:
                    return verse

            # Always fallback to first when available - matches original
            # package
            if votd_data:
                logger.warning(f"Verse for day {day} not found, using first available")
                return votd_data[0]

            # No data at all - matches original package
            day_value = day
            raise ValueError(f"No verse of the day found for day {day_value}")

        except httpx.RequestError as e:
            raise ValueError(f"VOTD API request failed: {e}")

    async def get_verse_text(
        self, usfm_reference: str, version_id: int = 1
    ) -> Dict[str, Any]:
        """Get the text for a Bible verse.

        Args:
            usfm_reference: USFM reference (e.g., "GEN.1.1")
            version_id: Bible version ID (default: 1 for KJV)

        Returns:
            Dictionary containing verse text and metadata

        Raises:
            ValueError: If API request fails
        """
        try:
            headers = await self.authenticator.get_auth_headers()

            # Extract chapter reference from verse reference
            # Convert "JHN.10.11" to "JHN.10"
            parts = usfm_reference.split(".")
            if len(parts) >= 2:
                chapter_reference = f"{parts[0]}.{parts[1]}"
            else:
                chapter_reference = usfm_reference

            params = {"id": version_id, "reference": chapter_reference}

            # Apply rate limiting
            await self._rate_limiter.acquire()
            response = await self._client.get(
                self.BIBLE_CHAPTER_URL, headers=headers, params=params, timeout=10
            )

            if response.status_code != 200:
                # Log the response for debugging
                logger.debug(
                    "API Response: %s - %s", response.status_code, response.text
                )
                raise ValueError(
                    f"Bible chapter API request failed: {response.status_code}"
                )

            return response.json()

        except httpx.RequestError as e:
            raise ValueError(f"Bible chapter API request failed: {e}")

    async def get_verse_texts(
        self, usfm_references: List[str], version_id: int = 1
    ) -> List[Dict[str, Any]]:
        """Get text for multiple Bible verses concurrently.

        Args:
            usfm_references: List of USFM references (e.g., ["GEN.1.1",
                "JHN.3.16"])
            version_id: Bible version ID (default: 1 for KJV)

        Returns:
            List of chapter data dictionaries in the same order as input.

        Raises:
            ValueError: If any API request fails (all-or-nothing).
        """
        # Create tasks for each reference
        tasks = [self.get_verse_text(ref, version_id) for ref in usfm_references]
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Handle errors
        chapter_data_list = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch verse %s: %s", usfm_references[i], result)
                raise ValueError(
                    f"Failed to fetch verse {usfm_references[i]}: {result}"
                ) from result
            chapter_data_list.append(result)
        return chapter_data_list

    async def get_formatted_verse_of_the_day(
        self, day: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get the verse of the day with formatted text.

        Args:
            day: Specific day number (1-365/366). Defaults to current day.

        Returns:
            Dictionary containing verse data with formatted text

        Raises:
            ValueError: If API requests fail
        """
        if day is None:
            day = datetime.now().timetuple().tm_yday

        async with self._cache_lock:
            # Check cache
            cached = self._votd_cache.get(day)
            if cached:
                timestamp, data = cached
                if time.time() - timestamp < self._cache_ttl:
                    logger.debug("Returning cached VOTD for day %s", day)
                    # Move to end to mark as recently used
                    self._votd_cache.move_to_end(day)
                    return data
                else:
                    # Remove expired entry
                    del self._votd_cache[day]

        # Get the verse reference
        votd_data = await self.get_verse_of_the_day(day)

        # Extract USFM reference
        usfm_refs = votd_data.get("usfm", [])
        if not usfm_refs:
            raise ValueError("No USFM reference found in VOTD data")

        # Use the first USFM reference (for backward compatibility)
        usfm_ref = usfm_refs[0]

        # Try to fetch all references concurrently for performance
        try:
            chapter_data_list = await self.get_verse_texts(usfm_refs)
            # Use the first successful result
            chapter_data = chapter_data_list[0]
        except ValueError:
            # If parallel fetch fails, fallback to sequential for robustness
            logger.warning("Parallel fetch failed, falling back to sequential")
            chapter_data = await self.get_verse_text(usfm_ref)

        # Extract the specific verse
        verse_number = self._extract_verse_number(usfm_ref)
        verse_text = self._extract_verse_text(chapter_data, verse_number)

        result = {
            "day": votd_data.get("day"),
            "usfm": usfm_ref,
            "human_reference": self._usfm_to_human(usfm_ref),
            "verse_text": verse_text,
            "version_id": 1,  # Default to KJV
            "image_id": votd_data.get("image_id"),
        }

        async with self._cache_lock:
            # Evict oldest if cache exceeds max size
            if len(self._votd_cache) >= self._cache_maxsize:
                self._votd_cache.popitem(last=False)  # remove oldest
            # Store in cache
            self._votd_cache[day] = (time.time(), result)
            logger.debug("Cached VOTD for day %s", day)

        return result

    def _extract_verse_number(self, usfm_ref: str) -> int:
        """Extract verse number from USFM reference.

        Args:
            usfm_ref: USFM reference (e.g., "GEN.1.1")

        Returns:
            Verse number
        """
        parts = usfm_ref.split(".")
        if len(parts) >= 3:
            try:
                return int(parts[2])
            except ValueError:
                pass
        return 1  # Default to first verse

    def _extract_verse_text(
        self, chapter_data: Dict[str, Any], verse_number: int
    ) -> str:
        """Extract specific verse text from chapter data."""
        # The API returns verses embedded in HTML content under response.data
        content = chapter_data.get("response", {}).get("data", {}).get("content", "")

        # Parse HTML to find the specific verse

        # Look for the specific verse pattern in the HTML
        # The structure is:
        # <span class="verse v{number}" ...>
        #   <span class="label">{number}</span>
        #   <span class="content">text</span>...
        # </span>
        # Use a pattern that captures everything until the next verse starts
        for match in VERSE_SPAN_PATTERN.finditer(content):
            if int(match.group(1)) == verse_number:
                verse_content = match.group(2).strip()

                # Extract all content spans within the verse
                content_matches = CONTENT_PATTERN.findall(verse_content)

                if content_matches:
                    # Combine all content spans
                    verse_text = "".join(content_matches)
                    # Clean up any remaining HTML tags and whitespace
                    verse_text = HTML_TAG_PATTERN.sub("", verse_text)
                    verse_text = WHITESPACE_PATTERN.sub(" ", verse_text)
                    verse_text = verse_text.strip()

                    if verse_text:
                        return verse_text
                break

        # Alternative pattern: look for verse content after the label
        for alt_match in LABEL_CONTENT_PATTERN.finditer(content):
            if int(alt_match.group(1)) == verse_number:
                verse_text = alt_match.group(2).strip()
                verse_text = HTML_TAG_PATTERN.sub("", verse_text)
                verse_text = WHITESPACE_PATTERN.sub(" ", verse_text)
                verse_text = verse_text.strip()

                if verse_text:
                    return verse_text
                break

        # Final fallback: extract all text within the verse span
        for fallback_match in VERSE_SPAN_FALLBACK_PATTERN.finditer(content):
            if int(fallback_match.group(1)) == verse_number:
                verse_content = fallback_match.group(2).strip()
                # Remove all HTML tags but keep the text
                verse_text = HTML_TAG_PATTERN.sub("", verse_content)
                verse_text = WHITESPACE_PATTERN.sub(" ", verse_text)
                verse_text = verse_text.strip()

                if verse_text:
                    return verse_text
                break

        # If nothing works, raise an error
        raise ValueError(f"Verse {verse_number} not found in chapter data")

    def _usfm_to_human(self, usfm_ref: str) -> str:
        """Convert USFM reference to human-readable format.

        Args:
            usfm_ref: USFM reference (e.g., "GEN.1.1")

        Returns:
            Human-readable reference (e.g., "Genesis 1:1")
        """
        # Simple mapping for common books
        book_mapping = {
            "GEN": "Genesis",
            "EXO": "Exodus",
            "LEV": "Leviticus",
            "NUM": "Numbers",
            "DEU": "Deuteronomy",
            "JOS": "Joshua",
            "JDG": "Judges",
            "RUT": "Ruth",
            "1SA": "1 Samuel",
            "2SA": "2 Samuel",
            "1KI": "1 Kings",
            "2KI": "2 Kings",
            "1CH": "1 Chronicles",
            "2CH": "2 Chronicles",
            "EZR": "Ezra",
            "NEH": "Nehemiah",
            "EST": "Esther",
            "JOB": "Job",
            "PSA": "Psalm",
            "PRO": "Proverbs",
            "ECC": "Ecclesiastes",
            "SNG": "Song of Solomon",
            "ISA": "Isaiah",
            "JER": "Jeremiah",
            "LAM": "Lamentations",
            "EZK": "Ezekiel",
            "DAN": "Daniel",
            "HOS": "Hosea",
            "JOL": "Joel",
            "AMO": "Amos",
            "OBA": "Obadiah",
            "JON": "Jonah",
            "MIC": "Micah",
            "NAM": "Nahum",
            "HAB": "Habakkuk",
            "ZEP": "Zephaniah",
            "HAG": "Haggai",
            "ZEC": "Zechariah",
            "MAL": "Malachi",
            "MAT": "Matthew",
            "MRK": "Mark",
            "LUK": "Luke",
            "JHN": "John",
            "ACT": "Acts",
            "ROM": "Romans",
            "1CO": "1 Corinthians",
            "2CO": "2 Corinthians",
            "GAL": "Galatians",
            "EPH": "Ephesians",
            "PHP": "Philippians",
            "COL": "Colossians",
            "1TH": "1 Thessalonians",
            "2TH": "2 Thessalonians",
            "1TI": "1 Timothy",
            "2TI": "2 Timothy",
            "TIT": "Titus",
            "PHM": "Philemon",
            "HEB": "Hebrews",
            "JAS": "James",
            "1PE": "1 Peter",
            "2PE": "2 Peter",
            "1JN": "1 John",
            "2JN": "2 John",
            "3JN": "3 John",
            "JUD": "Jude",
            "REV": "Revelation",
        }

        parts = usfm_ref.split(".")
        if len(parts) >= 3:
            book_abbr = parts[0]
            chapter = parts[1]
            verse = parts[2]

            book_name = book_mapping.get(book_abbr, book_abbr)
            return f"{book_name} {chapter}:{verse}"

        return usfm_ref  # Return original if parsing fails
