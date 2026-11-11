import unittest

from limiter import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.limiter = RateLimiter(5, 2, clock=lambda: self.now)

    def drain(self):
        self.assertTrue(self.limiter.allow("alice", cost=5))

    def test_frequent_denied_requests_preserve_fractional_refill(self):
        self.drain()
        for tick in range(1, 4):
            self.now = tick / 8
            self.assertFalse(self.limiter.allow("alice"))
        self.now = 0.5
        self.assertTrue(self.limiter.allow("alice"))
        self.assertFalse(self.limiter.allow("alice"))

    def test_retry_polling_preserves_refill_without_consuming_tokens(self):
        self.drain()
        for tick in range(1, 5):
            self.now = tick / 8
            self.assertAlmostEqual(
                self.limiter.retry_after("alice"), 0.5 - self.now
            )
        self.assertTrue(self.limiter.allow("alice"))

    def test_refill_is_capped_and_clients_are_independent(self):
        self.drain()
        self.assertTrue(self.limiter.allow("bob", cost=5))
        self.now = 100
        self.assertTrue(self.limiter.allow("alice", cost=5))
        self.assertFalse(self.limiter.allow("alice"))

    def test_oversized_request_can_never_be_satisfied(self):
        self.assertFalse(self.limiter.allow("alice", cost=6))
        self.assertEqual(self.limiter.retry_after("alice", cost=6), float("inf"))

    def test_clock_going_backwards_does_not_create_tokens(self):
        self.drain()
        self.now = -1
        self.assertFalse(self.limiter.allow("alice"))
        self.now = 0.5
        self.assertTrue(self.limiter.allow("alice"))
        self.assertFalse(self.limiter.allow("alice"))


if __name__ == "__main__":
    unittest.main()
