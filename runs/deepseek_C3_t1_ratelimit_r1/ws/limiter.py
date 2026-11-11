"""Token-bucket rate limiter, one bucket per client id.

Each client may make up to `capacity` requests in a burst. Tokens refill
continuously at `rate` tokens per second, up to `capacity`.
"""
import threading
import time

# Tolerance for floating point error at exact token boundaries.
_EPSILON = 1e-9


class Bucket:
    def __init__(self, capacity, rate, now):
        self.capacity = capacity
        self.rate = rate
        self.tokens = capacity
        self.last = now
        # Fraction of a token earned since the last whole token was added.
        # Without this, frequent refills would repeatedly truncate the
        # fractional part and the bucket would never gain a token.
        self._fraction = 0.0

    def refill(self, now):
        elapsed = now - self.last
        if elapsed <= 0:
            return
        self.last = now

        if self.tokens >= self.capacity:
            # A full bucket cannot bank refill time.
            self._fraction = 0.0
            return

        amount = elapsed * self.rate + self._fraction
        whole = int(amount + _EPSILON)
        if whole:
            self.tokens = min(self.capacity, self.tokens + whole)
            amount -= whole
        if self.tokens >= self.capacity:
            self._fraction = 0.0
        else:
            self._fraction = max(0.0, amount)

    def try_take(self, now, cost=1):
        self.refill(now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def wait_time(self, now, cost=1):
        """Seconds until `cost` tokens will be available (0 if available now)."""
        self.refill(now)
        if self.tokens >= cost:
            return 0.0
        missing = cost - self.tokens
        # Part of the next token has already been earned.
        return max(0.0, missing - self._fraction) / self.rate


class RateLimiter:
    def __init__(self, capacity, rate, clock=time.monotonic):
        if capacity <= 0 or rate <= 0:
            raise ValueError("capacity and rate must be positive")
        self.capacity = capacity
        self.rate = rate
        self.clock = clock
        self._buckets = {}
        self._lock = threading.Lock()

    def _bucket(self, client_id, now):
        b = self._buckets.get(client_id)
        if b is None:
            b = Bucket(self.capacity, self.rate, now)
            self._buckets[client_id] = b
        return b

    def allow(self, client_id, cost=1):
        """Return True and consume tokens if the request is allowed."""
        if cost > self.capacity:
            return False
        with self._lock:
            now = self.clock()
            return self._bucket(client_id, now).try_take(now, cost)

    def retry_after(self, client_id, cost=1):
        """Seconds the client should wait before `cost` tokens are available."""
        with self._lock:
            now = self.clock()
            return self._bucket(client_id, now).wait_time(now, cost)

    def stats(self):
        with self._lock:
            now = self.clock()
            for b in self._buckets.values():
                b.refill(now)
            return {cid: b.tokens for cid, b in self._buckets.items()}
