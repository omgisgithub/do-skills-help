import math
from limiter import RateLimiter


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def drain(rl, cid):
    while rl.allow(cid):
        pass


def test_frequent_polling_refills():
    c = Clock()
    rl = RateLimiter(capacity=5, rate=2, clock=c)
    drain(rl, "a")
    # poll every 0.125 s for 3 s at 2 tokens/s -> exactly 6 requests get through
    ok = 0
    for _ in range(24):
        c.t += 0.125
        if rl.allow("a"):
            ok += 1
    assert ok == 6, ok


def test_uneven_poll_interval_keeps_remainder():
    c = Clock()
    rl = RateLimiter(capacity=5, rate=2, clock=c)
    drain(rl, "g")
    ok = 0
    for _ in range(8):  # 3 s in 0.375 s steps -> 0.75 token per step, 6 tokens total
        c.t += 0.375
        if rl.allow("g"):
            ok += 1
    assert ok == 6, ok


def test_fractional_rate_frequent():
    c = Clock()
    rl = RateLimiter(capacity=1, rate=0.5, clock=c)  # one request every 2 s
    assert rl.allow("b")
    ok = 0
    for _ in range(80):  # 10 seconds in 0.125 s steps
        c.t += 0.125
        if rl.allow("b"):
            ok += 1
    assert ok == 5, ok


def test_retry_after_accurate():
    c = Clock()
    rl = RateLimiter(capacity=2, rate=4, clock=c)
    drain(rl, "c")
    c.t += 0.125  # 0.5 tokens accrued
    w = rl.retry_after("c")
    assert math.isclose(w, 0.125, abs_tol=1e-9), w
    c.t += 0.125
    assert rl.allow("c")
    assert not rl.allow("c")


def test_rare_callers_unchanged():
    c = Clock()
    rl = RateLimiter(capacity=3, rate=1, clock=c)
    for _ in range(3):
        assert rl.allow("d")
    assert not rl.allow("d")
    c.t += 1.0
    assert rl.allow("d")
    assert not rl.allow("d")
    c.t += 100
    for _ in range(3):
        assert rl.allow("d")
    assert not rl.allow("d")


def test_retry_after_does_not_leak_tokens():
    c = Clock()
    rl = RateLimiter(capacity=1, rate=1, clock=c)
    assert rl.allow("e")
    for _ in range(7):
        c.t += 0.125
        rl.retry_after("e")
    c.t += 0.125
    assert rl.allow("e")


def test_cost_and_capacity():
    c = Clock()
    rl = RateLimiter(capacity=4, rate=1, clock=c)
    assert not rl.allow("f", cost=5)
    assert rl.allow("f", cost=4)
    c.t += 2.5
    assert rl.allow("f", cost=2)
    assert not rl.allow("f", cost=1)
    c.t += 0.5
    assert rl.allow("f", cost=1)


def test_clients_independent():
    c = Clock()
    rl = RateLimiter(capacity=1, rate=1, clock=c)
    assert rl.allow("x")
    assert not rl.allow("x")
    assert rl.allow("y")


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, e)
    sys.exit(1 if fails else 0)
