"""Token-bucket rate limiter, one bucket per client id.

Each client may make up to `capacity` requests in a burst. Tokens refill
continuously at `rate` tokens per second, up to `capacity`.
"""
import threading
import time


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
        # Keep fractional tokens. Rounding down on every poll discards the
        # remainder and can prevent a frequently checked bucket from ever
        # refilling when each interval is shorter than one token's refill time.
        added = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + added)
        self.last = now

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
            return {cid: b.tokens for cid, b in self._buckets.items()}
