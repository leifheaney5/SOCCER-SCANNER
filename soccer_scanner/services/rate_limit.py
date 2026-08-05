"""Request rate limiting primitives.

Production runs multiple gunicorn workers, so a process-local counter gives
each worker its own budget and the advertised limit is silently multiplied by
the worker count. The Redis-backed limiter below keeps one shared counter per
key and performs the whole check in a single atomic server-side operation.
"""

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
    limit: int = 0
    resetSeconds: int = 0


@dataclass(frozen=True)
class RateLimitPolicy:
    """A named budget so one noisy surface cannot exhaust another."""

    name: str
    limit: int
    window_seconds: int


RATE_LIMIT_POLICIES = {
    'fixtures': RateLimitPolicy('fixtures', limit=120, window_seconds=60),
    'calendar_range': RateLimitPolicy('calendar_range', limit=60, window_seconds=60),
    'search': RateLimitPolicy('search', limit=60, window_seconds=60),
    # Provider fan-out makes analysis by far the most expensive read.
    'team_analysis': RateLimitPolicy('team_analysis', limit=20, window_seconds=60),
    # Credential-stuffing resistance, not capacity protection.
    'authentication': RateLimitPolicy('authentication', limit=10, window_seconds=60),
    'account_export': RateLimitPolicy('account_export', limit=3, window_seconds=3600),
    'device_registration': RateLimitPolicy('device_registration', limit=10, window_seconds=3600),
    'notifications': RateLimitPolicy('notifications', limit=30, window_seconds=60),
    'operations': RateLimitPolicy('operations', limit=30, window_seconds=60),
    'default': RateLimitPolicy('default', limit=60, window_seconds=60),
}


class MemoryRateLimiter:
    """Bounded fixed-window limiter for development and as a degraded fallback."""

    def __init__(self, *, limit=60, window_seconds=60, max_keys=10_000, clock=time.monotonic):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self.max_keys = max(1, int(max_keys))
        self.clock = clock
        self.shared = False
        self._windows = OrderedDict()
        self._lock = Lock()

    def check(self, key, *, limit=None, window_seconds=None):
        effective_limit = max(1, int(limit if limit is not None else self.limit))
        window = max(1, int(window_seconds if window_seconds is not None else self.window_seconds))
        now = self.clock()
        with self._lock:
            started, count = self._windows.get(key, (now, 0))
            if now - started >= window:
                started, count = now, 0
            count += 1
            self._windows[key] = (started, count)
            self._windows.move_to_end(key)
            while len(self._windows) > self.max_keys:
                self._windows.popitem(last=False)
            allowed = count <= effective_limit
            reset_after = max(1, math.ceil(window - (now - started)))
            return RateLimitDecision(
                allowed=allowed,
                retryAfterSeconds=0 if allowed else reset_after,
                remaining=max(0, effective_limit - count),
                limit=effective_limit,
                resetSeconds=reset_after,
            )


class RedisRateLimiter:
    """Shared fixed-window limiter backed by a single atomic Redis script.

    The script is a fixed server-side Lua literal executed via the Redis
    ``EVAL`` command. It is not Python ``eval`` and never interpolates caller
    input: the key and window arrive as bound KEYS/ARGV parameters.

    Incrementing and setting the expiry together means concurrent workers can
    never both observe an under-limit count, and the expiry bounds key growth
    without a sweep.
    """

    _SCRIPT = (
        "local current = redis.call('INCR', KEYS[1]) "
        "if current == 1 then redis.call('PEXPIRE', KEYS[1], ARGV[1]) end "
        "return {current, redis.call('PTTL', KEYS[1])}"
    )

    def __init__(
        self,
        client,
        *,
        namespace='soccer-scanner',
        limit=60,
        window_seconds=60,
        fallback=None,
        metrics=None,
    ):
        self.client = client
        self.namespace = ''.join(
            character if character.isalnum() or character in '-_.' else '-'
            for character in str(namespace)
        )[:64]
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self.metrics = metrics
        self.shared = True
        self.degraded = False
        self._fallback = fallback or MemoryRateLimiter(
            limit=limit,
            window_seconds=window_seconds,
        )

    def _key(self, key):
        return f'{self.namespace}:ratelimit:{key}'

    def check(self, key, *, limit=None, window_seconds=None):
        effective_limit = max(1, int(limit if limit is not None else self.limit))
        window = max(1, int(window_seconds if window_seconds is not None else self.window_seconds))
        try:
            current, ttl_ms = self.client.eval(
                self._SCRIPT,
                1,
                self._key(key),
                window * 1000,
            )
            self.degraded = False
        except Exception:
            # Never fail a request because the limiter is unavailable; fall back
            # to a bounded local budget and surface the degradation.
            self.degraded = True
            if self.metrics is not None:
                self.metrics.increment('api.rate_limiter_degraded')
            return self._fallback.check(key, limit=effective_limit, window_seconds=window)

        count = int(current)
        reset_after = max(1, math.ceil(int(ttl_ms) / 1000)) if int(ttl_ms) > 0 else window
        allowed = count <= effective_limit
        return RateLimitDecision(
            allowed=allowed,
            retryAfterSeconds=0 if allowed else reset_after,
            remaining=max(0, effective_limit - count),
            limit=effective_limit,
            resetSeconds=reset_after,
        )


def build_rate_limiter(config, *, metrics=None):
    """Shared Redis limiter when Redis is configured, bounded memory otherwise."""
    fallback = MemoryRateLimiter(
        limit=config['RATE_LIMIT_MAX_REQUESTS'],
        window_seconds=config['RATE_LIMIT_WINDOW_SECONDS'],
        max_keys=config['RATE_LIMIT_MAX_KEYS'],
    )
    redis_url = config.get('REDIS_URL')
    if not redis_url:
        return fallback

    import redis

    client = redis.Redis.from_url(
        redis_url,
        socket_connect_timeout=config['REDIS_CONNECT_TIMEOUT'],
        socket_timeout=config['REDIS_READ_TIMEOUT'],
        health_check_interval=30,
    )
    return RedisRateLimiter(
        client,
        namespace=config.get('CACHE_NAMESPACE', 'soccer-scanner'),
        limit=config['RATE_LIMIT_MAX_REQUESTS'],
        window_seconds=config['RATE_LIMIT_WINDOW_SECONDS'],
        fallback=fallback,
        metrics=metrics,
    )
