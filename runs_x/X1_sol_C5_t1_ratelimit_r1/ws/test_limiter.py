import math
import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0

    def limiter(self, capacity=1, rate=1):
        return RateLimiter(capacity, rate, clock=lambda: self.now)

    def test_frequent_requests_preserve_fractional_refill(self):
        limiter = self.limiter()
        self.assertTrue(limiter.allow("alice"))
        for now in (0.25, 0.5, 0.75):
            self.now = now
            self.assertFalse(limiter.allow("alice"))
        self.now = 1.0
        self.assertTrue(limiter.allow("alice"))

    def test_retry_polling_does_not_delay_recovery(self):
        limiter = self.limiter(rate=0.5)
        self.assertTrue(limiter.allow("alice"))
        for now, expected in ((0.5, 1.5), (1.0, 1.0), (1.5, 0.5)):
            self.now = now
            self.assertAlmostEqual(limiter.retry_after("alice"), expected)
        self.now = 2.0
        self.assertEqual(limiter.retry_after("alice"), 0.0)
        self.assertTrue(limiter.allow("alice"))

    def test_fractional_remainder_survives_successful_requests(self):
        limiter = self.limiter(capacity=2, rate=2)
        self.assertTrue(limiter.allow("alice", cost=2))
        self.now = 0.75
        self.assertTrue(limiter.allow("alice"))
        self.now = 1.0
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))

    def test_idle_refill_is_capped_and_does_not_bank_extra_time(self):
        limiter = self.limiter(capacity=2)
        self.assertTrue(limiter.allow("alice", cost=2))
        self.now = 100.0
        self.assertTrue(limiter.allow("alice", cost=2))
        self.assertFalse(limiter.allow("alice"))
        self.assertEqual(limiter.retry_after("alice"), 1.0)

    def test_clients_have_independent_buckets(self):
        limiter = self.limiter()
        self.assertTrue(limiter.allow("alice"))
        self.assertTrue(limiter.allow("bob"))
        self.assertFalse(limiter.allow("alice"))
        self.assertFalse(limiter.allow("bob"))

    def test_oversized_request_never_becomes_available(self):
        limiter = self.limiter()
        self.assertFalse(limiter.allow("alice", cost=2))
        self.assertEqual(limiter.retry_after("alice", cost=2), math.inf)
        self.assertTrue(limiter.allow("alice"))

    def test_bucket_wait_time_for_oversized_cost_is_infinite(self):
        bucket = Bucket(1, 1, 0.0)
        self.assertEqual(bucket.wait_time(0.0, cost=2), math.inf)

    def test_backward_clock_does_not_refill_twice(self):
        limiter = self.limiter()
        self.assertTrue(limiter.allow("alice"))
        self.now = 0.5
        self.assertFalse(limiter.allow("alice"))
        self.now = 0.25
        self.assertFalse(limiter.allow("alice"))
        self.now = 0.5
        self.assertAlmostEqual(limiter.retry_after("alice"), 0.5)
        self.now = 1.0
        self.assertTrue(limiter.allow("alice"))


if __name__ == "__main__":
    unittest.main()
