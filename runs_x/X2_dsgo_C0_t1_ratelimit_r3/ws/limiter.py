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
        added = elapsed * self.rate
        # Tolerate floating-point error when the clock advances in small
        # steps (e.g. ten 0.1s ticks should earn exactly one token).
        if added < 1 - 1e-9:
            # Not enough time has passed to earn a whole token. Keep `last`
            # where it is so this fraction is carried into the next refill
            # instead of being discarded on every call.
            return
        whole = int(added + 1e-9)
        if self.tokens + whole >= self.capacity:
            # Don't accumulate time while the bucket is full.
            self.tokens = self.capacity
            self.last = now
        else:
            self.tokens += whole
            # Only advance the clock by the time represented by the tokens
            # actually granted, preserving the leftover fraction.
            self.last += whole / self.rate

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
        # `last` trails `now` by the partial progress already made towards
        # the next token, so subtract that from the full wait.
        remaining = missing / self.rate - (now - self.last)
        return max(0.0, remaining)


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
