"""Bounded in-memory and Redis cache backends with single-flight fills."""

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from threading import Event, Lock
import time
from uuid import uuid4


@dataclass(frozen=True)
class CacheLookup:
    status: str
    value: object = None
    ageSeconds: float | None = None


class _Flight:
    def __init__(self):
        self.event = Event()
        self.error = None


class CacheBackendUnavailable(RuntimeError):
    """Raised only for cache coordination failures, never loader failures."""


class MemoryCacheBackend:
    def __init__(
        self,
        *,
        default_ttl_seconds=60,
        default_stale_ttl_seconds=900,
        max_entries=128,
        max_key_length=256,
        max_value_bytes=1_000_000,
        clock=time.monotonic,
        metrics=None,
        health_status='development',
    ):
        self.default_ttl_seconds = max(0, float(default_ttl_seconds))
        self.default_stale_ttl_seconds = max(0, float(default_stale_ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.max_key_length = max(1, int(max_key_length))
        self.max_value_bytes = max(1, int(max_value_bytes))
        self.clock = clock
        self.metrics = metrics
        self.health_status = health_status
        self._items = OrderedDict()
        self._lock = Lock()
        self._flights = {}
        self._flights_lock = Lock()

    def get(self, key, *, allow_stale=False):
        self._validate_key(key)
        now = self.clock()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return self._miss()
            fresh_until, stale_until, stored_at, encoded = item
            if stale_until <= now:
                self._items.pop(key, None)
                return self._miss()
            if fresh_until <= now and not allow_stale:
                return self._miss()
            self._items.move_to_end(key)
            status = 'fresh' if fresh_until > now else 'stale'
            self._increment('cache.hit' if status == 'fresh' else 'cache.stale_hit')
            return CacheLookup(
                status=status,
                value=json.loads(encoded),
                ageSeconds=max(0, now - stored_at),
            )

    def set(self, key, value, *, ttl_seconds=None, stale_ttl_seconds=None):
        self._validate_key(key)
        encoded = self._encode(value)
        ttl = self.default_ttl_seconds if ttl_seconds is None else max(0, float(ttl_seconds))
        stale_ttl = (
            self.default_stale_ttl_seconds
            if stale_ttl_seconds is None
            else max(0, float(stale_ttl_seconds))
        )
        now = self.clock()
        with self._lock:
            self._items[key] = (now + ttl, now + ttl + stale_ttl, now, encoded)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
                self._increment('cache.eviction')

    def get_or_load(
        self,
        key,
        loader,
        *,
        ttl_seconds=None,
        stale_ttl_seconds=None,
    ):
        cached = self.get(key)
        if cached.status == 'fresh':
            return cached

        with self._flights_lock:
            flight = self._flights.get(key)
            owner = flight is None
            if owner:
                flight = _Flight()
                self._flights[key] = flight

        if not owner:
            flight.event.wait()
            if flight.error is not None:
                raise flight.error
            return self.get(key)

        started = self.clock()
        try:
            cached = self.get(key)
            if cached.status == 'fresh':
                return cached
            value = loader()
            self.set(
                key,
                value,
                ttl_seconds=ttl_seconds,
                stale_ttl_seconds=stale_ttl_seconds,
            )
            self._observe_fill(started)
            return CacheLookup(status='filled', value=value, ageSeconds=0)
        except Exception as error:
            flight.error = error
            raise
        finally:
            with self._flights_lock:
                self._flights.pop(key, None)
            flight.event.set()

    def health(self):
        return {'backend': 'memory', 'shared': False, 'status': self.health_status}

    def _validate_key(self, key):
        if not isinstance(key, str) or not key or len(key) > self.max_key_length:
            raise ValueError('Cache key is invalid or exceeds the configured limit.')

    def _encode(self, value):
        try:
            encoded = json.dumps(value, separators=(',', ':'), sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError('Cache values must be JSON serializable.') from error
        if len(encoded.encode('utf-8')) > self.max_value_bytes:
            raise ValueError('Cache value exceeds the configured size limit.')
        return encoded

    def _miss(self):
        self._increment('cache.miss')
        return CacheLookup(status='miss')

    def _increment(self, name):
        if self.metrics is not None:
            self.metrics.increment(name)

    def _observe_fill(self, started):
        if self.metrics is not None:
            self.metrics.observe_ms('cache.fill_ms', (self.clock() - started) * 1000)


class RedisCacheBackend:
    _UNLOCK_SCRIPT = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )

    def __init__(
        self,
        client,
        *,
        namespace='soccer-scanner',
        default_ttl_seconds=60,
        default_stale_ttl_seconds=900,
        max_key_length=256,
        max_value_bytes=1_000_000,
        lock_ttl_seconds=15,
        lock_wait_seconds=5,
        lock_poll_seconds=0.05,
        wall_clock=time.time,
        monotonic_clock=time.monotonic,
        sleep=time.sleep,
        metrics=None,
    ):
        self.client = client
        self.namespace = ''.join(
            character if character.isalnum() or character in '-_.' else '-'
            for character in namespace
        )[:64]
        self.default_ttl_seconds = max(0, float(default_ttl_seconds))
        self.default_stale_ttl_seconds = max(0, float(default_stale_ttl_seconds))
        self.max_key_length = max(1, int(max_key_length))
        self.max_value_bytes = max(1, int(max_value_bytes))
        self.lock_ttl_seconds = max(1, int(lock_ttl_seconds))
        self.lock_wait_seconds = max(0, float(lock_wait_seconds))
        self.lock_poll_seconds = max(0.001, float(lock_poll_seconds))
        self.wall_clock = wall_clock
        self.monotonic_clock = monotonic_clock
        self.sleep = sleep
        self.metrics = metrics

    def get(self, key, *, allow_stale=False):
        cache_key = self._cache_key(key)
        raw = self._call(self.client.get, cache_key)
        if raw is None:
            return self._miss()
        try:
            record = json.loads(raw.decode('utf-8') if isinstance(raw, bytes) else raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            return self._miss()
        now = self.wall_clock()
        if record.get('staleUntil', 0) <= now:
            return self._miss()
        fresh = record.get('freshUntil', 0) > now
        if not fresh and not allow_stale:
            return self._miss()
        status = 'fresh' if fresh else 'stale'
        self._increment('cache.hit' if fresh else 'cache.stale_hit')
        return CacheLookup(
            status=status,
            value=record.get('value'),
            ageSeconds=max(0, now - record.get('storedAt', now)),
        )

    def set(self, key, value, *, ttl_seconds=None, stale_ttl_seconds=None):
        cache_key = self._cache_key(key)
        ttl = self.default_ttl_seconds if ttl_seconds is None else max(0, float(ttl_seconds))
        stale_ttl = (
            self.default_stale_ttl_seconds
            if stale_ttl_seconds is None
            else max(0, float(stale_ttl_seconds))
        )
        now = self.wall_clock()
        encoded = json.dumps({
            'storedAt': now,
            'freshUntil': now + ttl,
            'staleUntil': now + ttl + stale_ttl,
            'value': value,
        }, separators=(',', ':'), sort_keys=True)
        if len(encoded.encode('utf-8')) > self.max_value_bytes:
            raise ValueError('Cache value exceeds the configured size limit.')
        self._call(
            self.client.setex,
            cache_key,
            max(1, math.ceil(ttl + stale_ttl)),
            encoded,
        )

    def get_or_load(
        self,
        key,
        loader,
        *,
        ttl_seconds=None,
        stale_ttl_seconds=None,
    ):
        cached = self.get(key)
        if cached.status == 'fresh':
            return cached
        lock_key = self._cache_key(key) + ':lock'
        token = uuid4().hex
        deadline = self.monotonic_clock() + self.lock_wait_seconds

        while True:
            acquired = self._call(
                self.client.set,
                lock_key,
                token,
                nx=True,
                ex=self.lock_ttl_seconds,
            )
            if acquired:
                started = self.monotonic_clock()
                try:
                    cached = self.get(key)
                    if cached.status == 'fresh':
                        return cached
                    value = loader()
                    self.set(
                        key,
                        value,
                        ttl_seconds=ttl_seconds,
                        stale_ttl_seconds=stale_ttl_seconds,
                    )
                    if self.metrics is not None:
                        self.metrics.observe_ms(
                            'cache.fill_ms',
                            (self.monotonic_clock() - started) * 1000,
                        )
                    return CacheLookup(status='filled', value=value, ageSeconds=0)
                finally:
                    self._call(self.client.eval, self._UNLOCK_SCRIPT, 1, lock_key, token)

            cached = self.get(key)
            if cached.status == 'fresh':
                return cached
            if self.monotonic_clock() >= deadline:
                raise TimeoutError('Timed out waiting for distributed cache fill.')
            self.sleep(self.lock_poll_seconds)

    def health(self):
        try:
            self.client.ping()
        except Exception:
            return {'backend': 'redis', 'shared': True, 'status': 'degraded'}
        return {'backend': 'redis', 'shared': True, 'status': 'ready'}

    def _cache_key(self, key):
        if not isinstance(key, str) or not key or len(key) > self.max_key_length:
            raise ValueError('Cache key is invalid or exceeds the configured limit.')
        digest = sha256(key.encode('utf-8')).hexdigest()
        return f'{self.namespace}:{digest}'

    def _miss(self):
        self._increment('cache.miss')
        return CacheLookup(status='miss')

    def _increment(self, name):
        if self.metrics is not None:
            self.metrics.increment(name)

    @staticmethod
    def _call(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except Exception as error:
            raise CacheBackendUnavailable('Shared cache is unavailable.') from error


class ResilientCacheBackend:
    """Use a bounded local cache when Redis coordination is unavailable."""

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self._degraded = False

    def get(self, key, *, allow_stale=False):
        try:
            return self.primary.get(key, allow_stale=allow_stale)
        except CacheBackendUnavailable:
            self._degraded = True
            return self.fallback.get(key, allow_stale=allow_stale)

    def set(self, key, value, *, ttl_seconds=None, stale_ttl_seconds=None):
        try:
            self.primary.set(
                key,
                value,
                ttl_seconds=ttl_seconds,
                stale_ttl_seconds=stale_ttl_seconds,
            )
        except CacheBackendUnavailable:
            self._degraded = True
            self.fallback.set(
                key,
                value,
                ttl_seconds=ttl_seconds,
                stale_ttl_seconds=stale_ttl_seconds,
            )

    def get_or_load(
        self,
        key,
        loader,
        *,
        ttl_seconds=None,
        stale_ttl_seconds=None,
    ):
        loaded = []

        def tracked_loader():
            value = loader()
            loaded.append(value)
            return value

        try:
            return self.primary.get_or_load(
                key,
                tracked_loader,
                ttl_seconds=ttl_seconds,
                stale_ttl_seconds=stale_ttl_seconds,
            )
        except CacheBackendUnavailable:
            self._degraded = True
            if loaded:
                self.fallback.set(
                    key,
                    loaded[0],
                    ttl_seconds=ttl_seconds,
                    stale_ttl_seconds=stale_ttl_seconds,
                )
                return CacheLookup(status='filled', value=loaded[0], ageSeconds=0)
            return self.fallback.get_or_load(
                key,
                loader,
                ttl_seconds=ttl_seconds,
                stale_ttl_seconds=stale_ttl_seconds,
            )

    def health(self):
        health = self.primary.health()
        if health.get('status') == 'ready' and not self._degraded:
            return health
        return {
            'backend': health.get('backend', 'redis'),
            'shared': False,
            'status': 'degraded',
            'fallback': 'memory',
        }


def build_cache_backend(config, metrics, *, environment='development'):
    memory = MemoryCacheBackend(
        default_ttl_seconds=config['FIXTURE_CACHE_TTL'],
        default_stale_ttl_seconds=config['FIXTURE_STALE_TTL'],
        max_entries=config['FIXTURE_CACHE_MAX_ENTRIES'],
        max_key_length=config['CACHE_MAX_KEY_LENGTH'],
        max_value_bytes=config['CACHE_MAX_VALUE_BYTES'],
        metrics=metrics,
        health_status=(
            'degraded'
            if str(environment).lower() in {'production', 'prod'}
            else 'development'
        ),
    )
    redis_url = config.get('REDIS_URL')
    if not redis_url:
        return memory

    import redis

    client = redis.Redis.from_url(
        redis_url,
        socket_connect_timeout=config['REDIS_CONNECT_TIMEOUT'],
        socket_timeout=config['REDIS_READ_TIMEOUT'],
        health_check_interval=30,
    )
    primary = RedisCacheBackend(
        client,
        namespace=config['CACHE_NAMESPACE'],
        default_ttl_seconds=config['FIXTURE_CACHE_TTL'],
        default_stale_ttl_seconds=config['FIXTURE_STALE_TTL'],
        max_key_length=config['CACHE_MAX_KEY_LENGTH'],
        max_value_bytes=config['CACHE_MAX_VALUE_BYTES'],
        lock_ttl_seconds=config['CACHE_LOCK_TTL'],
        lock_wait_seconds=config['CACHE_LOCK_WAIT'],
        metrics=metrics,
    )
    return ResilientCacheBackend(primary, memory)
