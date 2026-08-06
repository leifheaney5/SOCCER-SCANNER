"""In-process provider health tracking.

Readiness answers "can this process serve requests", which stayed true during a
real production outage where every fixture request failed. This registry
answers the different question of whether upstream data is actually flowing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from threading import Lock
import time

VALID_STATUSES = frozenset({'ok', 'degraded', 'unavailable', 'disabled'})

# A provider that is switched off by configuration is not a failure.
_COUNTS_AGAINST_HEALTH = frozenset({'degraded', 'unavailable'})


def _isoformat(epoch_seconds):
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


@dataclass
class _ProviderState:
    status: str
    detail: str | None
    last_observed_at: float
    last_success_at: float | None


class ProviderHealthRegistry:
    def __init__(self, *, clock=time.time):
        self.clock = clock
        self._states = {}
        self._lock = Lock()

    def record(self, name, status, detail=None):
        if status not in VALID_STATUSES:
            raise ValueError(f'unknown provider status: {status!r}')
        now = self.clock()
        with self._lock:
            previous = self._states.get(str(name))
            last_success = previous.last_success_at if previous else None
            if status == 'ok':
                last_success = now
            self._states[str(name)] = _ProviderState(
                status=status,
                detail=detail,
                last_observed_at=now,
                last_success_at=last_success,
            )

    def snapshot(self):
        with self._lock:
            states = dict(self._states)

        providers = [
            {
                'name': name,
                'status': state.status,
                'detail': state.detail,
                'lastObservedAt': _isoformat(state.last_observed_at),
                'lastSuccessAt': _isoformat(state.last_success_at),
            }
            for name, state in sorted(states.items())
        ]

        return _aggregate(providers)


class RedisProviderHealthRegistry:
    """Provider health shared across gunicorn workers.

    The in-process registry gives each worker its own view, so /health/providers
    answered `ok` or `unknown` depending on which worker happened to serve the
    request. One hash keyed by provider name fixes that.

    The hash's own TTL (`EXPIRE`) only bounds total key growth in Redis; it is
    refreshed on every write, so as long as *any* provider is actively
    recording, it keeps every other provider's stale entry alive too. Per-field
    Redis TTLs would fix that but would force a `SCAN` on every `snapshot()`,
    which is exactly what a health endpoint hit during an incident cannot
    afford. Instead, `_read()` deterministically drops any entry whose
    `lastObservedAt` is older than `ttl_seconds` relative to the injected
    clock, so a decommissioned provider ages out independent of both Redis
    semantics and its neighbours' traffic.

    Writes go through a single Lua script (`_RECORD_SCRIPT`) so a read of the
    previous `lastSuccessAt` and the write of the merged payload happen
    atomically on the server, the same pattern `RedisRateLimiter` uses for its
    increment-and-check. Without that, two workers recording the same
    provider concurrently could race a stale read past a newer write.
    """

    # Reads the field's previous payload (if any) so `lastSuccessAt` survives
    # a later failure, then writes the merged payload and refreshes the
    # key-level TTL -- all atomically, so concurrent writers cannot race a
    # stale `lastSuccessAt` past a newer one. Values are bound through
    # KEYS/ARGV only; the script text itself is a fixed literal.
    _RECORD_SCRIPT = (
        "local existing = redis.call('HGET', KEYS[1], ARGV[1]) "
        "local last_success = cjson.null "
        "if existing then "
        "local ok, decoded = pcall(cjson.decode, existing) "
        "if ok and type(decoded) == 'table' and decoded.lastSuccessAt ~= nil then "
        "last_success = decoded.lastSuccessAt "
        "end "
        "end "
        "local status = ARGV[2] "
        "local now = tonumber(ARGV[4]) "
        "if status == 'ok' then last_success = now end "
        "local payload = { "
        "status = status, "
        "detail = cjson.decode(ARGV[3]), "
        "lastObservedAt = now, "
        "lastSuccessAt = last_success, "
        "} "
        "redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(payload)) "
        "redis.call('EXPIRE', KEYS[1], ARGV[5]) "
        "return 1"
    )

    def __init__(
        self,
        client,
        *,
        namespace='soccer-scanner',
        ttl_seconds=900,
        fallback=None,
        clock=time.time,
        metrics=None,
    ):
        self.client = client
        self.namespace = ''.join(
            character if character.isalnum() or character in '-_.' else '-'
            for character in str(namespace)
        )[:64]
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.clock = clock
        self.metrics = metrics
        self.shared = True
        self.degraded = False
        self._fallback = fallback or ProviderHealthRegistry(clock=clock)

    @property
    def _key(self):
        return f'{self.namespace}:provider-health'

    def record(self, name, status, detail=None):
        if status not in VALID_STATUSES:
            raise ValueError(f'unknown provider status: {status!r}')
        # Mirror into the fallback so a later Redis outage still has context.
        self._fallback.record(name, status, detail)
        now = self.clock()
        try:
            # `client.eval` is the redis-py method that sends a Redis `EVAL`
            # command to the server -- not Python's `eval()` builtin. The
            # script is the fixed Lua literal above; caller-supplied values
            # (name, status, detail, now, ttl) are bound through EVAL's
            # KEYS/ARGV, never interpolated into the script text.
            self.client.eval(
                self._RECORD_SCRIPT,
                1,
                self._key,
                str(name),
                status,
                json.dumps(detail),
                str(now),
                str(self.ttl_seconds),
            )
            self.degraded = False
        except Exception:
            self.degraded = True
            if self.metrics is not None:
                self.metrics.increment('api.provider_health_degraded')

    def _read(self):
        raw = self.client.hgetall(self._key) or {}
        now = self.clock()
        entries = {}
        for name, value in raw.items():
            key = name.decode() if isinstance(name, bytes) else str(name)
            text = value.decode() if isinstance(value, bytes) else str(value)
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                # A corrupt entry must never take down the health endpoint.
                continue
            if not isinstance(parsed, dict) or parsed.get('status') not in VALID_STATUSES:
                continue
            last_observed = parsed.get('lastObservedAt')
            # The hash's own TTL only bounds total growth; ageing out an
            # individual provider is enforced here so one actively-recording
            # provider cannot keep a decommissioned neighbour's entry alive.
            if last_observed is None or (now - last_observed) > self.ttl_seconds:
                continue
            entries[key] = parsed
        return entries

    def snapshot(self):
        try:
            entries = self._read()
            self.degraded = False
        except Exception:
            self.degraded = True
            return self._fallback.snapshot()

        providers = [
            {
                'name': name,
                'status': entry['status'],
                'detail': entry.get('detail'),
                'lastObservedAt': _isoformat(entry.get('lastObservedAt')),
                'lastSuccessAt': _isoformat(entry.get('lastSuccessAt')),
            }
            for name, entry in sorted(entries.items())
        ]
        return _aggregate(providers)


def _aggregate(providers):
    """Shared status rollup so the two registries cannot drift apart.

    Takes the already-rendered provider dicts, not internal state, so both the
    dataclass-backed in-memory registry and the JSON-backed Redis one can share
    it without a type mismatch.
    """
    accountable = [item for item in providers if item['status'] != 'disabled']
    if not providers:
        status = 'unknown'
    elif not accountable:
        status = 'unavailable'
    elif all(item['status'] in _COUNTS_AGAINST_HEALTH for item in accountable):
        status = 'unavailable'
    elif any(item['status'] in _COUNTS_AGAINST_HEALTH for item in accountable):
        status = 'degraded'
    else:
        status = 'ok'
    successes = [
        item['lastSuccessAt'] for item in providers if item['lastSuccessAt']
    ]
    return {
        'status': status,
        'providers': providers,
        'lastSuccessAt': max(successes) if successes else None,
        # One usable provider means an upstream failure has no fallback.
        'singleProvider': len(accountable) <= 1,
    }


def build_provider_health(config, *, metrics=None):
    """Shared registry when Redis is configured, in-process otherwise."""
    fallback = ProviderHealthRegistry()
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
    return RedisProviderHealthRegistry(
        client,
        namespace=config.get('CACHE_NAMESPACE', 'soccer-scanner'),
        fallback=fallback,
        metrics=metrics,
    )
