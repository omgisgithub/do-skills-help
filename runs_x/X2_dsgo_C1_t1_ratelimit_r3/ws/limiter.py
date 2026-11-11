"""Token-bucket rate limiter, one bucket per client id.

Each client may make up to `capacity` requests in a burst. Tokens refill
continuously at `rate` tokens per second, up to `capacity`.
"""
import threading
import time


# Allowance for floating-point drift when comparing token balances.
_TOKEN_EPSILON = 1e-9


class Bucket:
    def __init__(self, capacity, rate, now):
        self.capacity = capacity
        self.rate = rate
        self.tokens = capacity
        self.last = now

    def refill(self, now):
        elapsed = now - self.last
        if elapsed <= 0:
            return
        # Keep the fractional part instead of truncating it. Frequent callers
        # refill in small steps, so truncating here would silently throw away
        # most (or all) of the tokens they have earned.
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last = now

    def try_take(self, now, cost=1):
        self.refill(now)
        # Compare with a small tolerance so floating-point accumulation errors
        # do not deny a request that has earned exactly `cost` tokens.
        if self.tokens + _TOKEN_EPSILON >= cost:
            self.tokens = max(0.0, self.tokens - cost)
            return True
        return False

    def wait_time(self, now, cost=1):
        """Seconds until `cost` tokens will be available (0 if available now)."""
        self.refill(now)
        if self.tokens + _TOKEN_EPSILON >= cost:
            return 0.0
        missing = cost - self.tokens
        return missing / self.rate


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
