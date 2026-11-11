"""Tests for limiter.py, including the frequent-poller regression."""
import math

from limiter import RateLimiter


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def approx(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def test_example_verbatim():
    # example.py's usage, with asserts instead of prints
    rl = RateLimiter(capacity=5, rate=2)  # bursts of 5, then 2 requests/second
    results = [rl.allow("alice") for _ in range(7)]
    assert results == [True, True, True, True, True, False, False]
    # Real clock elapses a little between calls, so allow tiny refill.
    assert 0.0 < rl.stats()["alice"] < 0.01
    assert 0.49 < rl.retry_after("alice") <= 0.5


def test_frequent_poller_recovers():
    # Regression: calling several times per second must not discard fractional refill.
    clock = FakeClock()
    rl = RateLimiter(capacity=5, rate=2, clock=clock)
    for _ in range(5):
        assert rl.allow("alice")
    assert not rl.allow("alice")

    # Poll every 10 ms (100 times per second) for just under half a second:
    # 0.49 s * 2 tokens/s = 0.98 tokens, still not enough.
    for _ in range(49):
        clock.advance(0.01)
        assert not rl.allow("alice")

    # The 50th poll reaches 1.0 token and must be allowed.
    clock.advance(0.01)
    assert rl.allow("alice")


def test_frequent_poller_after_slowing_down():
    clock = FakeClock()
    rl = RateLimiter(capacity=5, rate=2, clock=clock)
    assert rl.allow("alice", cost=5)

    # Frequent calls for a while, none earning a whole token per call.
    for _ in range(100):
        clock.advance(0.001)
        rl.allow("alice")
    assert approx(rl.retry_after("alice"), 0.4)
    assert approx(rl.stats()["alice"], 0.2)

    # Then slow down: the banked 0.2 tokens plus 0.4 s * 2 = 1.0.
    clock.advance(0.4)
    assert rl.allow("alice")


def test_fractional_tokens_are_reported():
    clock = FakeClock()
    rl = RateLimiter(capacity=5, rate=2, clock=clock)
    assert rl.allow("alice", cost=5)
    clock.advance(0.25)
    assert approx(rl.retry_after("alice"), 0.25)
    assert approx(rl.stats()["alice"], 0.5)


def test_capacity_is_capped():
    clock = FakeClock()
    rl = RateLimiter(capacity=5, rate=2, clock=clock)
    assert rl.allow("alice", cost=5)
    clock.advance(1000)
    assert rl.retry_after("alice", cost=5) == 0.0
    assert rl.stats()["alice"] == 5
    assert rl.allow("alice", cost=5)
    assert not rl.allow("alice")


def test_retry_after_reflects_cost():
    clock = FakeClock()
    rl = RateLimiter(capacity=5, rate=2, clock=clock)
    assert rl.allow("alice", cost=3)
    assert rl.allow("alice", cost=2)
    assert not rl.allow("alice", cost=3)
    assert approx(rl.retry_after("alice", cost=3), 1.5)
    clock.advance(1.5)
    assert rl.allow("alice", cost=3)
    assert approx(rl.stats()["alice"], 0.0)


def test_cost_above_capacity_never_allowed():
    clock = FakeClock()
    rl = RateLimiter(capacity=5, rate=2, clock=clock)
    assert rl.allow("alice")
    assert not rl.allow("alice", cost=6)
    assert rl.stats()["alice"] == 4  # unchanged
    clock.advance(1000)
    assert not rl.allow("alice", cost=6)
    assert rl.stats()["alice"] == 4


def test_clients_are_independent():
    clock = FakeClock()
    rl = RateLimiter(capacity=2, rate=1, clock=clock)
    assert rl.allow("alice")
    assert rl.allow("alice")
    assert not rl.allow("alice")
    assert rl.allow("bob")
    assert rl.stats() == {"alice": 0, "bob": 1}


def test_clock_going_backwards_is_safe():
    clock = FakeClock(10.0)
    rl = RateLimiter(capacity=2, rate=1, clock=clock)
    assert rl.allow("alice", cost=2)
    clock.advance(-5)
    assert not rl.allow("alice")
    assert rl.stats()["alice"] == 0


def test_invalid_configuration_rejected():
    for capacity, rate in [(0, 1), (-1, 1), (1, 0), (1, -1)]:
        try:
            RateLimiter(capacity=capacity, rate=rate)
        except ValueError:
            pass
        else:
            raise AssertionError((capacity, rate))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"{len(tests)} tests passed")
