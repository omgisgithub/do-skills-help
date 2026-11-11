"""Test token refill behavior with a deterministic clock."""

import unittest

from limiter import Bucket, RateLimiter


class RefillTests(unittest.TestCase):
    """Verify refill credit survives frequent polling."""

    def test_allow_frequent_requests_preserves_fractional_credit(self) -> None:
        now = 0.0
        limiter = RateLimiter(capacity=1, rate=1, clock=lambda: now)
        self.assertTrue(limiter.allow("alice"))

        for now in (0.25, 0.5, 0.75):
            self.assertFalse(limiter.allow("alice"))
        now = 1.0

        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))

    def test_retry_after_frequent_queries_decreases_to_zero(self) -> None:
        now = 0.0
        limiter = RateLimiter(capacity=2, rate=2, clock=lambda: now)
        self.assertTrue(limiter.allow("alice", cost=2))

        for now in (0.125, 0.25, 0.375, 0.5):
            self.assertAlmostEqual(limiter.retry_after("alice"), max(0.0, 0.5 - now))

        self.assertTrue(limiter.allow("alice"))

    def test_refill_idle_bucket_caps_credit_at_capacity(self) -> None:
        bucket = Bucket(capacity=2, rate=1, now=0.0)
        self.assertTrue(bucket.try_take(0.0, cost=2))

        bucket.refill(100.0)

        self.assertEqual(bucket.tokens, 2)
        self.assertTrue(bucket.try_take(100.0, cost=2))
        self.assertFalse(bucket.try_take(100.0))

    def test_refill_nonincreasing_clock_does_not_duplicate_credit(self) -> None:
        bucket = Bucket(capacity=2, rate=1, now=1.0)
        self.assertTrue(bucket.try_take(1.0, cost=2))

        bucket.refill(0.0)
        bucket.refill(1.0)
        bucket.refill(1.5)

        self.assertEqual(bucket.tokens, 0.5)
        self.assertEqual(bucket.last, 1.5)

    def test_allow_clients_have_independent_buckets(self) -> None:
        limiter = RateLimiter(capacity=1, rate=1, clock=lambda: 0.0)

        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        self.assertTrue(limiter.allow("bob"))
