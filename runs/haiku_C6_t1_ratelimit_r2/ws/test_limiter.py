import unittest

from limiter import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class TestRateLimiter(unittest.TestCase):
    def make(self, capacity=5, rate=2):
        clock = FakeClock()
        return RateLimiter(capacity=capacity, rate=rate, clock=clock), clock

    # Example from example.py: burst of 5, then 2 requests/second.
    def test_example(self):
        rl, clock = self.make(capacity=5, rate=2)
        results = []
        for i in range(7):
            results.append(rl.allow("alice"))
        self.assertEqual(results, [True] * 5 + [False, False])
        self.assertAlmostEqual(rl.retry_after("alice"), 0.5)

    # Bug report: frequent pollers must recover at their average rate.
    def test_frequent_poller_not_locked_out(self):
        rl, clock = self.make(capacity=5, rate=2)
        for _ in range(5):
            self.assertTrue(rl.allow("p"))
        # Poll every 0.3s (faster than 1/rate = 0.5s). Average 2 req/s is
        # within the limit, so most polls must succeed.
        allowed = 0
        for _ in range(100):
            clock.t += 0.3
            if rl.allow("p"):
                allowed += 1
        # 30s at 2 tokens/s = ~60 tokens; allow a small rounding margin.
        self.assertGreaterEqual(allowed, 55)
        self.assertLessEqual(allowed, 61)

    def test_frequent_poller_rate_never_exceeded(self):
        rl, clock = self.make(capacity=3, rate=1)
        for _ in range(3):
            self.assertTrue(rl.allow("c"))
        allowed = 0
        for _ in range(1000):
            clock.t += 0.1  # 10 polls/s against a limit of 1/s
            if rl.allow("c"):
                allowed += 1
        # 100s at 1 token/s => about 100 tokens, never more than the rate allows.
        self.assertLessEqual(allowed, 101)
        self.assertGreaterEqual(allowed, 98)

    def test_refill_caps_at_capacity(self):
        rl, clock = self.make(capacity=5, rate=2)
        self.assertTrue(rl.allow("x", cost=5))
        clock.t += 1000
        self.assertTrue(rl.allow("x"))
        self.assertEqual(rl.stats()["x"], 4)
        for _ in range(4):
            self.assertTrue(rl.allow("x"))
        self.assertFalse(rl.allow("x"))

    def test_denied_request_does_not_consume(self):
        rl, clock = self.make(capacity=2, rate=1)
        self.assertTrue(rl.allow("d"))
        self.assertTrue(rl.allow("d"))
        self.assertFalse(rl.allow("d"))
        self.assertFalse(rl.allow("d"))
        clock.t += 1
        self.assertTrue(rl.allow("d"))
        self.assertFalse(rl.allow("d"))

    def test_cost_larger_than_capacity_denied(self):
        rl, _ = self.make(capacity=5, rate=2)
        self.assertFalse(rl.allow("y", cost=6))
        self.assertTrue(rl.allow("y", cost=5))

    def test_retry_after_zero_when_available(self):
        rl, _ = self.make(capacity=5, rate=2)
        self.assertEqual(rl.retry_after("z"), 0.0)

    def test_retry_after_is_accurate(self):
        rl, clock = self.make(capacity=1, rate=2)
        self.assertTrue(rl.allow("r"))
        clock.t += 0.2
        wait = rl.retry_after("r")
        self.assertAlmostEqual(wait, 0.3)
        clock.t += wait
        self.assertTrue(rl.allow("r"))

    def test_clients_are_independent(self):
        rl, _ = self.make(capacity=1, rate=1)
        self.assertTrue(rl.allow("a"))
        self.assertFalse(rl.allow("a"))
        self.assertTrue(rl.allow("b"))

    def test_invalid_args_rejected(self):
        for cap, rate in [(0, 1), (1, 0), (-1, 1), (1, -2)]:
            with self.assertRaises(ValueError):
                RateLimiter(capacity=cap, rate=rate)


if __name__ == "__main__":
    unittest.main()
