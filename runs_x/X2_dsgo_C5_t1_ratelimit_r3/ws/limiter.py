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
        added = int(elapsed * self.rate)
        if added <= 0:
            # Not enough time has passed for a whole token. Leave `last`
            # untouched so the partial token carries over to the next call
            # instead of being discarded.
            return
        self.tokens = min(self.capacity, self.tokens + added)
        if self.tokens >= self.capacity:
            # Bucket is full, so no leftover time needs to be carried.
            self.last = now
        else:
            # Advance the refill clock only by the time actually credited,
            # preserving the remainder for the next refill.
            self.last += added / self.rate

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
        # `now - self.last` is the time already banked toward the next token
        # (refill preserves it rather than discarding the fraction).
        banked = max(0.0, now - self.last)
        return max(0.0, missing / self.rate - banked)


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
