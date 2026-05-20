"""
Rate limiting utilities for API calls.

Provides a token-bucket style rate limiter that works asynchronously.
"""

import asyncio
import time
from collections import deque


class RateLimiter:
    """Asynchronous rate limiter using a sliding window.

    Limits the number of calls to a maximum of `max_calls` per `period`
    seconds. Thread-safe for async usage.

    Example:
        limiter = RateLimiter(max_calls=10, period=60)  # 10 calls per minute
        await limiter.acquire()
        # make API call
    """

    def __init__(self, max_calls: int, period: float):
        """
        Args:
            max_calls: Maximum number of calls allowed within the period.
            period: Time window in seconds.
        """
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if period <= 0:
            raise ValueError("period must be positive")

        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, sleeping if necessary to respect rate limit."""
        async with self._lock:
            now = time.monotonic()
            # Remove calls that are older than the period
            while self._calls and self._calls[0] <= now - self.period:
                self._calls.popleft()

            if len(self._calls) >= self.max_calls:
                # Need to wait until the oldest call expires
                sleep_time = self._calls[0] + self.period - now
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                # After sleeping, remove expired calls again
                now = time.monotonic()
                while self._calls and self._calls[0] <= now - self.period:
                    self._calls.popleft()

            # Record this call
            self._calls.append(now)

    async def reset(self) -> None:
        """Reset the rate limiter (clear all recorded calls)."""
        async with self._lock:
            self._calls.clear()

    async def get_remaining_calls(self) -> int:
        """Number of calls that can be made immediately without waiting."""
        now = time.monotonic()
        async with self._lock:
            # Remove expired calls
            while self._calls and self._calls[0] <= now - self.period:
                self._calls.popleft()
            return self.max_calls - len(self._calls)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded (non-blocking mode)."""

    pass


class NonBlockingRateLimiter(RateLimiter):
    """Rate limiter that raises RateLimitExceeded instead of blocking."""

    async def acquire(self) -> None:
        """Acquire a token; raise RateLimitExceeded if limit reached."""
        async with self._lock:
            now = time.monotonic()
            while self._calls and self._calls[0] <= now - self.period:
                self._calls.popleft()

            if len(self._calls) >= self.max_calls:
                raise RateLimitExceeded(
                    f"Rate limit exceeded: {self.max_calls} calls per "
                    f"{self.period} seconds"
                )
            self._calls.append(now)


def get_limiter_from_env(
    env_var_prefix: str, default_max_calls: int, default_period: float
) -> RateLimiter:
    """
    Create a RateLimiter from environment variables.

    Looks for:
        {env_var_prefix}_MAX_CALLS (int)
        {env_var_prefix}_PERIOD (float)

    If not set, uses defaults.

    Args:
        env_var_prefix: Prefix for environment variables (e.g., "YOUVERSION").
        default_max_calls: Default max calls.
        default_period: Default period in seconds.

    Returns:
        Configured RateLimiter instance.
    """
    import os

    max_calls = int(os.getenv(f"{env_var_prefix}_MAX_CALLS", default_max_calls))
    period = float(os.getenv(f"{env_var_prefix}_PERIOD", default_period))
    return RateLimiter(max_calls=max_calls, period=period)
