import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.limiter = RateLimiter(2, 1, clock=lambda: self.now)

    def test_frequent_denials_preserve_fractional_refills(self):
        self.assertTrue(self.limiter.allow("alice", 2))
        for tick in range(1, 8):
            self.now = tick / 8
            self.assertFalse(self.limiter.allow("alice"))
        self.now = 1.0
        self.assertTrue(self.limiter.allow("alice"))

    def test_retry_polling_preserves_progress(self):
        self.limiter.allow("alice", 2)
        for tick in range(1, 9):
            self.now = tick / 8
            self.assertAlmostEqual(
                self.limiter.retry_after("alice"), 1 - self.now
            )
        self.assertTrue(self.limiter.allow("alice"))

    def test_refill_is_capped_and_clients_are_independent(self):
        self.limiter.allow("alice", 2)
        self.assertTrue(self.limiter.allow("bob", 2))
        self.now = 10
        self.assertTrue(self.limiter.allow("alice", 2))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("bob", 2))

    def test_impossible_cost_has_infinite_wait(self):
        self.assertFalse(self.limiter.allow("alice", 3))
        self.assertEqual(self.limiter.retry_after("alice", 3), float("inf"))

    def test_fractional_rates_and_costs(self):
        bucket = Bucket(1, 0.5, 0)
        self.assertTrue(bucket.try_take(0))
        self.assertFalse(bucket.try_take(0.5, 0.5))
        self.assertTrue(bucket.try_take(1, 0.5))
        self.assertEqual(bucket.wait_time(1), 2)


if __name__ == "__main__":
    unittest.main()
