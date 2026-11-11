import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.limiter = RateLimiter(2, 1, clock=lambda: self.now)

    def test_frequent_requests_preserve_fractional_refills(self):
        self.assertTrue(self.limiter.allow("alice", 2))
        for tick in range(1, 8):
            self.now = tick / 8
            self.assertFalse(self.limiter.allow("alice"))
        self.now = 1.0
        self.assertTrue(self.limiter.allow("alice"))

    def test_retry_polling_preserves_fractional_refills(self):
        self.assertTrue(self.limiter.allow("alice", 2))
        for tick in range(1, 9):
            self.now = tick / 8
            self.assertAlmostEqual(
                self.limiter.retry_after("alice"), 1 - self.now
            )
        self.assertTrue(self.limiter.allow("alice"))

    def test_refill_is_continuous_and_capped(self):
        bucket = Bucket(2, 0.5, 0.0)
        self.assertTrue(bucket.try_take(0.0, 2))
        self.assertAlmostEqual(bucket.wait_time(0.5), 1.5)
        self.assertEqual(bucket.tokens, 0.25)
        bucket.refill(100.0)
        self.assertEqual(bucket.tokens, 2)
        self.assertTrue(bucket.try_take(100.0, 2))
        self.assertFalse(bucket.try_take(100.0))

    def test_clients_have_independent_buckets(self):
        self.assertTrue(self.limiter.allow("alice", 2))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("bob", 2))

    def test_impossible_cost_has_infinite_wait(self):
        self.assertFalse(self.limiter.allow("alice", 3))
        self.assertEqual(self.limiter.retry_after("alice", 3), float("inf"))
        self.assertTrue(self.limiter.allow("alice", 2))
        self.now = 100.0
        self.assertEqual(self.limiter.retry_after("alice", 3), float("inf"))


if __name__ == "__main__":
    unittest.main()
