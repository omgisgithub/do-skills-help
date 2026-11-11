import unittest

from limiter import RateLimiter


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


class TestRateLimiter(unittest.TestCase):
    def make(self, capacity=5, rate=2, t=0.0):
        clock = FakeClock(t)
        return RateLimiter(capacity=capacity, rate=rate, clock=clock), clock

    # --- spec example (example.py) ---
    def test_example_burst_then_block(self):
        rl, _ = self.make(capacity=5, rate=2)
        results = [rl.allow("alice") for _ in range(7)]
        self.assertEqual(results, [True] * 5 + [False, False])
        self.assertAlmostEqual(rl.retry_after("alice"), 0.5)

    # --- burst capacity ---
    def test_burst_allowed_up_to_capacity(self):
        rl, _ = self.make(capacity=3, rate=1)
        self.assertEqual([rl.allow("a") for _ in range(3)], [True] * 3)

    def test_burst_over_capacity_denied(self):
        rl, _ = self.make(capacity=3, rate=1)
        for _ in range(3):
            rl.allow("a")
        self.assertFalse(rl.allow("a"))

    def test_cost_greater_than_capacity_denied(self):
        rl, _ = self.make(capacity=3, rate=1)
        self.assertFalse(rl.allow("a", cost=4))
        self.assertEqual(rl.stats(), {})

    def test_cost_consumes_multiple_tokens(self):
        rl, _ = self.make(capacity=5, rate=1)
        self.assertTrue(rl.allow("a", cost=3))
        self.assertFalse(rl.allow("a", cost=3))
        self.assertTrue(rl.allow("a", cost=2))

    # --- refill ---
    def test_refill_after_full_interval(self):
        rl, clock = self.make(capacity=2, rate=1)
        rl.allow("a"); rl.allow("a")
        self.assertFalse(rl.allow("a"))
        clock.t = 1.0
        self.assertTrue(rl.allow("a"))
        self.assertFalse(rl.allow("a"))

    def test_refill_not_before_full_interval(self):
        rl, clock = self.make(capacity=1, rate=1)
        rl.allow("a")
        clock.t = 0.99
        self.assertFalse(rl.allow("a"))

    def test_refill_capped_at_capacity(self):
        rl, clock = self.make(capacity=2, rate=1)
        self.assertEqual([rl.allow("a") for _ in range(3)], [True, True, False])
        clock.t = 100.0  # long idle: refills to capacity, not beyond
        self.assertEqual([rl.allow("a") for _ in range(3)], [True, True, False])

    # --- frequent pollers (the reported bug) ---
    def test_poll_every_0_4s_at_rate_2_not_locked_out(self):
        # 40s elapsed at 2 tokens/s => about 80 tokens available to 100 calls.
        rl, clock = self.make(capacity=5, rate=2)
        for _ in range(5):
            rl.allow("a")
        allowed = 0
        for i in range(1, 101):
            clock.t = i * 0.4
            if rl.allow("a"):
                allowed += 1
        self.assertGreaterEqual(allowed, 78)
        self.assertLessEqual(allowed, 81)

    def test_poll_every_0_1s_at_rate_1_allows_one_per_second(self):
        rl, clock = self.make(capacity=1, rate=1)
        rl.allow("a")
        allowed = 0
        for i in range(1, 101):
            clock.t = i * 0.1
            if rl.allow("a"):
                allowed += 1
        # 10s elapsed at 1 token/s => about 10 allowed, never 0.
        self.assertGreaterEqual(allowed, 9)
        self.assertLessEqual(allowed, 10)

    def test_poll_every_0_9s_at_rate_1_capacity_1(self):
        # Capacity 1 can't bank tokens: one take needs 1s of accrual after the
        # previous take, and polls land every 0.9s, so one allow per 1.8s
        # poll pair. 27s / 1.8s = 15.
        rl, clock = self.make(capacity=1, rate=1)
        rl.allow("a")
        allowed = 0
        for i in range(1, 31):
            clock.t = i * 0.9
            if rl.allow("a"):
                allowed += 1
        self.assertEqual(allowed, 15)

    def test_fractional_time_accumulates_across_calls(self):
        rl, clock = self.make(capacity=10, rate=1)
        for _ in range(10):
            rl.allow("a")
        allowed = []
        for i in range(1, 11):
            clock.t = i * 0.5  # 10 calls over 5s at 1 token/s
            allowed.append(rl.allow("a"))
        self.assertEqual(sum(allowed), 5)
        self.assertEqual(allowed, [False, True] * 5)

    # --- retry_after ---
    def test_retry_after_zero_when_available(self):
        rl, _ = self.make(capacity=2, rate=1)
        self.assertEqual(rl.retry_after("a"), 0.0)

    def test_retry_after_accounts_for_partial_progress(self):
        rl, clock = self.make(capacity=1, rate=2)
        rl.allow("a")
        clock.t = 0.3  # 0.3s into a 0.5s token period
        self.assertAlmostEqual(rl.retry_after("a"), 0.2)

    def test_retry_after_positive_when_empty(self):
        rl, _ = self.make(capacity=1, rate=2)
        rl.allow("a")
        self.assertGreater(rl.retry_after("a"), 0.0)
        self.assertLessEqual(rl.retry_after("a"), 0.5)

    # --- validation / isolation / stats ---
    def test_invalid_capacity_or_rate_rejected(self):
        for cap, rate in [(0, 1), (1, 0), (-1, 1), (1, -1)]:
            with self.assertRaises(ValueError):
                RateLimiter(capacity=cap, rate=rate)

    def test_clients_are_isolated(self):
        rl, _ = self.make(capacity=1, rate=1)
        self.assertTrue(rl.allow("a"))
        self.assertFalse(rl.allow("a"))
        self.assertTrue(rl.allow("b"))

    def test_stats_returns_int_tokens(self):
        rl, _ = self.make(capacity=5, rate=2)
        rl.allow("a", cost=2)
        self.assertEqual(rl.stats(), {"a": 3})
        self.assertIsInstance(rl.stats()["a"], int)


if __name__ == "__main__":
    unittest.main()
