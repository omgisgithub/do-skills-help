import unittest

from limiter import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class RateLimiterTest(unittest.TestCase):
    def test_frequent_poller_recovers_at_rate(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, rate=4, clock=clock)  # one token per 0.25 s
        self.assertTrue(rl.allow("a"))
        granted = 0
        for i in range(1, 17):  # poll every 0.125 s for 2 s
            clock.t = i * 0.125
            granted += rl.allow("a")
        self.assertEqual(granted, 8)

    def test_retry_after_is_exact(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, rate=10, clock=clock)
        rl.allow("a")
        clock.t = 0.05
        self.assertFalse(rl.allow("a"))
        self.assertAlmostEqual(rl.retry_after("a"), 0.05)
        clock.t = 0.1
        self.assertTrue(rl.allow("a"))

    def test_tokens_capped_at_capacity(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=3, rate=10, clock=clock)
        rl.allow("a")
        clock.t = 100.0  # long idle must not bank more than capacity
        self.assertEqual([rl.allow("a") for _ in range(4)], [True, True, True, False])


if __name__ == "__main__":
    unittest.main()
