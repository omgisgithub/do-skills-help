import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.limiter = RateLimiter(5, 2, clock=lambda: self.now)

    def test_frequent_requests_accumulate_fractional_refill(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        for self.now in (0.125, 0.25, 0.375):
            self.assertFalse(self.limiter.allow("alice"))
        self.now = 0.5
        self.assertTrue(self.limiter.allow("alice"))

    def test_retry_polling_preserves_refill_progress(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        for now, expected in ((0.125, 0.375), (0.25, 0.25), (0.375, 0.125)):
            self.now = now
            self.assertAlmostEqual(self.limiter.retry_after("alice"), expected)
        self.now = 0.5
        self.assertEqual(self.limiter.retry_after("alice"), 0.0)
        self.assertTrue(self.limiter.allow("alice"))

    def test_below_limit_requests_recover_after_burst(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        # One request per second is below the two-token-per-second limit.
        # Retry estimates are polled eight times per second between requests.
        for second in range(1, 6):
            for tick in range(1, 8):
                self.now = second - 1 + tick / 8
                self.limiter.retry_after("alice")
            self.now = float(second)
            self.assertTrue(self.limiter.allow("alice"))

    def test_fractional_rate_refills_continuously(self):
        limiter = RateLimiter(1, 0.25, clock=lambda: self.now)
        self.assertTrue(limiter.allow("alice"))
        for self.now in (1.0, 2.0, 3.0):
            self.assertFalse(limiter.allow("alice"))
        self.now = 4.0
        self.assertTrue(limiter.allow("alice"))

    def test_refill_is_capped_and_idle_time_is_not_banked(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.now = 100.0
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertEqual(self.limiter.retry_after("alice"), 0.5)

    def test_clients_have_independent_buckets(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("bob", cost=5))

    def test_nonincreasing_clock_does_not_refill_twice(self):
        bucket = Bucket(2, 1, now=10.0)
        self.assertTrue(bucket.try_take(10.0, cost=2))
        self.assertFalse(bucket.try_take(9.0))
        self.assertFalse(bucket.try_take(10.0))
        self.assertTrue(bucket.try_take(11.0))
        self.assertFalse(bucket.try_take(11.0))


if __name__ == "__main__":
    unittest.main()
