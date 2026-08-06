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
    request. One hash keyed by provider name fixes that; entries carry a TTL so
    a decommissioned provider ages out instead of lingering forever.
    """

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
            existing = self._read()
            previous = existing.get(str(name)) or {}
            last_success = previous.get('lastSuccessAt')
            payload = {
                'status': status,
                'detail': detail,
                'lastObservedAt': now,
                'lastSuccessAt': now if status == 'ok' else last_success,
            }
            self.client.hset(self._key, str(name), json.dumps(payload))
            self.client.expire(self._key, self.ttl_seconds)
            self.degraded = False
        except Exception:
            self.degraded = True
            if self.metrics is not None:
                self.metrics.increment('api.provider_health_degraded')

    def _read(self):
        raw = self.client.hgetall(self._key) or {}
        entries = {}
        for name, value in raw.items():
            key = name.decode() if isinstance(name, bytes) else str(name)
            text = value.decode() if isinstance(value, bytes) else str(value)
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                # A corrupt entry must never take down the health endpoint.
                continue
            if isinstance(parsed, dict) and parsed.get('status') in VALID_STATUSES:
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
