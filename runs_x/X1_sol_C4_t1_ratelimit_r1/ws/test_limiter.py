"""Test continuous token refills without relying on wall-clock time."""

import unittest
from unittest.mock import Mock

from limiter import Bucket, RateLimiter


class LimiterTests(unittest.TestCase):
    """Verify token accounting for frequent callers."""

    def test_allow_frequent_requests_accumulate_fractional_tokens(self) -> None:
        clock = Mock(return_value=0.0)
        limiter = RateLimiter(capacity=1, rate=2, clock=clock)
        self.assertTrue(limiter.allow("alice"))

        for now in (0.125, 0.25, 0.375):
            clock.return_value = now
            self.assertFalse(limiter.allow("alice"))

        clock.return_value = 0.5
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))

    def test_retry_after_frequent_polls_preserve_refill_progress(self) -> None:
        clock = Mock(return_value=0.0)
        limiter = RateLimiter(capacity=1, rate=2, clock=clock)
        self.assertTrue(limiter.allow("alice"))

        for now in (0.125, 0.25, 0.375, 0.5):
            clock.return_value = now
            self.assertAlmostEqual(limiter.retry_after("alice"), 0.5 - now)

        self.assertTrue(limiter.allow("alice"))

    def test_refill_long_idle_period_caps_tokens(self) -> None:
        bucket = Bucket(capacity=2, rate=1, now=0.0)
        self.assertTrue(bucket.try_take(0.0, cost=2))

        self.assertTrue(bucket.try_take(100.0, cost=2))
        self.assertFalse(bucket.try_take(100.0))

    def test_refill_backward_time_does_not_duplicate_tokens(self) -> None:
        bucket = Bucket(capacity=1, rate=1, now=1.0)
        self.assertTrue(bucket.try_take(1.0))

        self.assertFalse(bucket.try_take(0.5))
        self.assertFalse(bucket.try_take(1.0))
        self.assertTrue(bucket.try_take(2.0))

    def test_allow_clients_have_independent_buckets(self) -> None:
        limiter = RateLimiter(capacity=1, rate=1, clock=lambda: 0.0)

        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        self.assertTrue(limiter.allow("bob"))


if __name__ == "__main__":
    unittest.main()
