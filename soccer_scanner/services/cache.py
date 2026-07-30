from collections import OrderedDict
from threading import Lock
from time import monotonic


class TTLCache:
    """Thread-safe in-process cache for short-lived provider responses."""

    def __init__(self, ttl_seconds=60, stale_ttl_seconds=0, max_entries=128):
        self.ttl_seconds = ttl_seconds
        self.stale_ttl_seconds = stale_ttl_seconds
        self.max_entries = max_entries
        self._items = OrderedDict()
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            fresh_until, stale_until, value = item
            if fresh_until <= monotonic():
                return None
            self._items.move_to_end(key)
            return value

    def get_stale(self, key):
        """Return fresh or recently expired data for outage fallback."""
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            _, stale_until, value = item
            if stale_until <= monotonic():
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key, value):
        with self._lock:
            now = monotonic()
            fresh_until = now + self.ttl_seconds
            self._items[key] = (
                fresh_until,
                fresh_until + self.stale_ttl_seconds,
                value,
            )
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
