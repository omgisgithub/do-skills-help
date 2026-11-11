import unittest

from limiter import Bucket, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.limiter = RateLimiter(5, 2, clock=lambda: self.now)

    def test_example_burst_and_retry(self):
        self.assertEqual(
            [self.limiter.allow("alice") for _ in range(7)],
            [True, True, True, True, True, False, False],
        )
        self.assertEqual(self.limiter.retry_after("alice"), 0.5)

    def test_frequent_requests_preserve_fractional_refill(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        for tick in range(1, 4):
            self.now = tick / 8
            self.assertFalse(self.limiter.allow("alice"))
        self.now = 0.5
        self.assertTrue(self.limiter.allow("alice"))
        self.assertFalse(self.limiter.allow("alice"))

    def test_retry_polling_preserves_fractional_refill(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        for tick in range(1, 5):
            self.now = tick / 8
            self.assertEqual(
                self.limiter.retry_after("alice"), 0.5 - self.now
            )
        self.assertTrue(self.limiter.allow("alice"))

    def test_below_limit_requests_continue_to_succeed(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        for tick in range(1, 41):
            self.now = tick / 8
            if tick % 5 == 0:
                self.assertTrue(self.limiter.allow("alice"))
            else:
                self.limiter.retry_after("alice")

    def test_refill_is_capped_and_clients_are_independent(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertTrue(self.limiter.allow("bob", cost=5))
        self.now = 100
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertFalse(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("bob", cost=5))
        self.assertFalse(self.limiter.allow("bob", cost=6))

    def test_nonadvancing_clock_does_not_add_tokens(self):
        bucket = Bucket(5, 2, 1)
        self.assertTrue(bucket.try_take(1, 5))
        self.assertFalse(bucket.try_take(1))
        self.assertFalse(bucket.try_take(0))
        self.assertTrue(bucket.try_take(1.5))


if __name__ == "__main__":
    unittest.main()
