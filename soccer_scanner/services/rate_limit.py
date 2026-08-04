"""Bounded request rate limiting primitives."""

from collections import OrderedDict
from dataclasses import dataclass
import math
from threading import Lock
import time


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retryAfterSeconds: int
    remaining: int


class MemoryRateLimiter:
    def __init__(self, *, limit=60, window_seconds=60, max_keys=10_000, clock=time.monotonic):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self.max_keys = max(1, int(max_keys))
        self.clock = clock
        self._windows = OrderedDict()
        self._lock = Lock()

    def check(self, key):
        now = self.clock()
        with self._lock:
            started, count = self._windows.get(key, (now, 0))
            if now - started >= self.window_seconds:
                started, count = now, 0
            count += 1
            self._windows[key] = (started, count)
            self._windows.move_to_end(key)
            while len(self._windows) > self.max_keys:
                self._windows.popitem(last=False)
            allowed = count <= self.limit
            retry_after = 0 if allowed else max(
                1,
                math.ceil(self.window_seconds - (now - started)),
            )
            return RateLimitDecision(
                allowed=allowed,
                retryAfterSeconds=retry_after,
                remaining=max(0, self.limit - count),
            )
