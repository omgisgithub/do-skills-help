"""Test token refill and retry estimates with a deterministic clock."""

import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    """Verify token accounting without wall-clock delays."""

    def test_allow_frequent_polling_preserves_fractional_refill(self) -> None:
        now = 0.0
        limiter = RateLimiter(1, 1, clock=lambda: now)
        self.assertTrue(limiter.allow("alice"))

        for tick in range(1, 4):
            now = tick / 4
            self.assertFalse(limiter.allow("alice"))
        now = 1.0

        self.assertTrue(limiter.allow("alice"))

    def test_retry_after_polling_preserves_fractional_refill(self) -> None:
        now = 0.0
        limiter = RateLimiter(1, 1, clock=lambda: now)
        self.assertTrue(limiter.allow("alice"))

        for tick in range(1, 5):
            now = tick / 4
            self.assertAlmostEqual(limiter.retry_after("alice"), 1 - now)

        self.assertTrue(limiter.allow("alice"))

    def test_refill_idle_bucket_caps_tokens_at_capacity(self) -> None:
        bucket = Bucket(2, 1, 0.0)
        self.assertTrue(bucket.try_take(0.0, 2))

        bucket.refill(100.0)

        self.assertEqual(bucket.tokens, 2)
        self.assertTrue(bucket.try_take(100.0, 2))
        self.assertFalse(bucket.try_take(100.0))

    def test_refill_nonincreasing_clock_does_not_add_tokens(self) -> None:
        bucket = Bucket(1, 1, 10.0)
        self.assertTrue(bucket.try_take(10.0))

        bucket.refill(9.0)
        bucket.refill(10.0)

        self.assertEqual(bucket.tokens, 0)
        self.assertTrue(bucket.try_take(11.0))

    def test_allow_clients_have_independent_buckets(self) -> None:
        limiter = RateLimiter(1, 1, clock=lambda: 0.0)

        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))
        self.assertTrue(limiter.allow("bob"))

    def test_retry_after_cost_above_capacity_returns_infinity(self) -> None:
        limiter = RateLimiter(1, 1, clock=lambda: 0.0)

        self.assertFalse(limiter.allow("alice", 2))
        self.assertEqual(limiter.retry_after("alice", 2), float("inf"))


if __name__ == "__main__":
    unittest.main()
