"""Unit tests for rate limiting utilities."""

import asyncio
import time
import unittest
from unittest.mock import patch
import os

from rate_limiter import (
    RateLimiter,
    NonBlockingRateLimiter,
    RateLimitExceeded,
    get_limiter_from_env,
)


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter functionality."""

    def test_init_valid(self):
        """Test initialization with valid parameters."""
        limiter = RateLimiter(max_calls=5, period=1.0)
        self.assertEqual(limiter.max_calls, 5)
        self.assertEqual(limiter.period, 1.0)
        # remaining calls should be max_calls initially
        remaining = asyncio.run(limiter.get_remaining_calls())
        self.assertEqual(remaining, 5)

    def test_init_invalid(self):
        """Test initialization with invalid parameters raises ValueError."""
        with self.assertRaises(ValueError):
            RateLimiter(max_calls=0, period=1.0)
        with self.assertRaises(ValueError):
            RateLimiter(max_calls=5, period=0)
        with self.assertRaises(ValueError):
            RateLimiter(max_calls=-1, period=1.0)

    def test_acquire_no_wait(self):
        """Test acquiring a token when limit not reached."""
        limiter = RateLimiter(max_calls=2, period=10.0)

        async def test():
            await limiter.acquire()
            self.assertEqual(await limiter.get_remaining_calls(), 1)
            await limiter.acquire()
            self.assertEqual(await limiter.get_remaining_calls(), 0)

        asyncio.run(test())

    def test_acquire_wait(self):
        """Test that acquire waits when limit reached."""
        limiter = RateLimiter(max_calls=1, period=0.1)  # 1 call per 0.1 sec
        start = time.monotonic()

        async def test():
            await limiter.acquire()  # first call
            # second call should wait ~0.1 seconds
            await limiter.acquire()
            elapsed = time.monotonic() - start
            self.assertGreaterEqual(elapsed, 0.1)
            self.assertLess(elapsed, 0.2)  # some tolerance

        asyncio.run(test())

    def test_remaining_calls(self):
        """Test get_remaining_calls method."""
        limiter = RateLimiter(max_calls=3, period=5.0)

        async def test():
            self.assertEqual(await limiter.get_remaining_calls(), 3)
            await limiter.acquire()
            self.assertEqual(await limiter.get_remaining_calls(), 2)
            await limiter.acquire()
            self.assertEqual(await limiter.get_remaining_calls(), 1)
            await limiter.acquire()
            self.assertEqual(await limiter.get_remaining_calls(), 0)

        asyncio.run(test())

    def test_reset(self):
        """Test reset clears calls."""
        limiter = RateLimiter(max_calls=2, period=10.0)

        async def test():
            await limiter.acquire()
            self.assertEqual(await limiter.get_remaining_calls(), 1)
            await limiter.reset()
            self.assertEqual(await limiter.get_remaining_calls(), 2)

        asyncio.run(test())

    def test_concurrent_acquisitions(self):
        """Test multiple coroutines acquiring tokens concurrently."""
        limiter = RateLimiter(max_calls=3, period=2.0)
        acquired = []

        async def worker(idx):
            await limiter.acquire()
            acquired.append(idx)

        async def test():
            tasks = [asyncio.create_task(worker(i)) for i in range(5)]
            # first 3 should acquire immediately, next 2 should wait
            await asyncio.sleep(0.01)  # let tasks start
            # after a short time, first 3 should have acquired
            self.assertEqual(len(acquired), 3)
            # wait for period to expire
            await asyncio.sleep(2.1)
            # remaining tasks should have acquired
            self.assertEqual(len(acquired), 5)
            # Ensure tasks are done (optional)
            await asyncio.gather(*tasks)

        asyncio.run(test())

    def test_non_blocking_rate_limiter_acquire(self):
        """Test NonBlockingRateLimiter raises RateLimitExceeded."""
        limiter = NonBlockingRateLimiter(max_calls=1, period=10.0)

        async def test():
            await limiter.acquire()  # first call ok
            with self.assertRaises(RateLimitExceeded):
                await limiter.acquire()  # second call should raise

        asyncio.run(test())

    def test_non_blocking_rate_limiter_reset(self):
        """Test NonBlockingRateLimiter reset allows new calls."""
        limiter = NonBlockingRateLimiter(max_calls=1, period=10.0)

        async def test():
            await limiter.acquire()
            with self.assertRaises(RateLimitExceeded):
                await limiter.acquire()
            await limiter.reset()
            await limiter.acquire()  # should succeed after reset

        asyncio.run(test())


class TestGetLimiterFromEnv(unittest.TestCase):
    """Test get_limiter_from_env function."""

    @patch.dict(os.environ, {"YOUVERSION_MAX_CALLS": "20", "YOUVERSION_PERIOD": "30"})
    def test_with_env_vars(self):
        """Test with environment variables set."""
        limiter = get_limiter_from_env(
            "YOUVERSION", default_max_calls=10, default_period=60
        )
        self.assertEqual(limiter.max_calls, 20)
        self.assertEqual(limiter.period, 30.0)

    @patch.dict(os.environ, {}, clear=True)
    def test_without_env_vars(self):
        """Test without environment variables (uses defaults)."""
        limiter = get_limiter_from_env(
            "YOUVERSION", default_max_calls=10, default_period=60
        )
        self.assertEqual(limiter.max_calls, 10)
        self.assertEqual(limiter.period, 60.0)

    @patch.dict(os.environ, {"YOUVERSION_MAX_CALLS": "invalid"})
    def test_invalid_env_var(self):
        """Test with invalid environment variable (should raise ValueError)."""
        with self.assertRaises(ValueError):
            get_limiter_from_env("YOUVERSION", default_max_calls=10, default_period=60)


if __name__ == "__main__":
    unittest.main()
