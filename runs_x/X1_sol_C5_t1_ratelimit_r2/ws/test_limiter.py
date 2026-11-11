import unittest

from limiter import Bucket, RateLimiter


class BucketTests(unittest.TestCase):
    def test_fractional_refills_accumulate_between_attempts(self):
        bucket = Bucket(capacity=1, rate=1, now=0)
        self.assertTrue(bucket.try_take(0))
        for now in (0.25, 0.5, 0.75):
            self.assertFalse(bucket.try_take(now))
        self.assertTrue(bucket.try_take(1))

    def test_wait_time_preserves_fractional_progress(self):
        bucket = Bucket(capacity=1, rate=1, now=0)
        self.assertTrue(bucket.try_take(0))
        for now, expected in ((0.25, 0.75), (0.5, 0.5), (0.75, 0.25)):
            self.assertAlmostEqual(bucket.wait_time(now), expected)
        self.assertTrue(bucket.try_take(1))

    def test_refill_is_capped_and_does_not_bank_excess_time(self):
        bucket = Bucket(capacity=2, rate=1, now=0)
        self.assertTrue(bucket.try_take(100, cost=2))
        self.assertFalse(bucket.try_take(100))
        self.assertAlmostEqual(bucket.wait_time(100.25), 0.75)

    def test_non_increasing_time_does_not_create_or_remove_tokens(self):
        bucket = Bucket(capacity=1, rate=1, now=10)
        self.assertTrue(bucket.try_take(10))
        self.assertFalse(bucket.try_take(9))
        self.assertFalse(bucket.try_take(10))
        self.assertTrue(bucket.try_take(11))


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.limiter = RateLimiter(capacity=2, rate=1, clock=lambda: self.now)

    def test_frequent_requests_recover_after_burst(self):
        self.assertTrue(self.limiter.allow("alice", cost=2))
        for tick in range(1, 13):
            self.now = tick / 4
            self.assertEqual(self.limiter.allow("alice"), tick % 4 == 0)

    def test_retry_polling_does_not_delay_recovery(self):
        self.assertTrue(self.limiter.allow("alice", cost=2))
        for now, expected in ((0.25, 0.75), (0.5, 0.5), (0.75, 0.25), (1, 0)):
            self.now = now
            self.assertAlmostEqual(self.limiter.retry_after("alice"), expected)
        self.assertTrue(self.limiter.allow("alice"))

    def test_clients_have_independent_buckets(self):
        self.assertTrue(self.limiter.allow("alice", cost=2))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("bob", cost=2))
        self.assertFalse(self.limiter.allow("bob"))


if __name__ == "__main__":
    unittest.main()
