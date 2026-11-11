import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.limiter = RateLimiter(5, 2, clock=lambda: self.now)

    def test_example_burst_and_refill(self):
        self.assertEqual(
            [self.limiter.allow("alice") for _ in range(7)],
            [True, True, True, True, True, False, False],
        )
        self.assertEqual(self.limiter.retry_after("alice"), 0.5)
        self.now = 0.5
        self.assertTrue(self.limiter.allow("alice"))
        self.assertFalse(self.limiter.allow("alice"))

    def test_frequent_rejected_requests_preserve_refill(self):
        limiter = RateLimiter(1, 1, clock=lambda: self.now)
        self.assertTrue(limiter.allow("alice"))
        for tick in range(1, 8):
            self.now = tick / 8
            self.assertFalse(limiter.allow("alice"))
        self.now = 1.0
        self.assertTrue(limiter.allow("alice"))

    def test_retry_polling_preserves_fractional_refill(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        for tick in range(1, 4):
            self.now = tick / 8
            self.assertEqual(
                self.limiter.retry_after("alice"), 0.5 - self.now
            )
        self.now = 0.5
        self.assertEqual(self.limiter.retry_after("alice"), 0.0)
        self.assertTrue(self.limiter.allow("alice"))

    def test_refill_is_capped_and_clients_are_independent(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("bob", cost=5))
        self.now = 100
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertFalse(self.limiter.allow("alice"))

    def test_impossible_cost_never_becomes_available(self):
        self.assertFalse(self.limiter.allow("alice", cost=6))
        self.assertEqual(self.limiter.retry_after("alice", cost=6), float("inf"))

    def test_nonincreasing_clock_does_not_duplicate_refill(self):
        bucket = Bucket(1, 1, 10)
        self.assertTrue(bucket.try_take(10))
        self.assertFalse(bucket.try_take(9))
        self.assertFalse(bucket.try_take(10))
        self.assertTrue(bucket.try_take(11))

    def test_capacity_and_rate_must_be_positive(self):
        for capacity, rate in [(0, 1), (-1, 1), (1, 0), (1, -1)]:
            with self.subTest(capacity=capacity, rate=rate):
                with self.assertRaises(ValueError):
                    RateLimiter(capacity, rate)


if __name__ == "__main__":
    unittest.main()
