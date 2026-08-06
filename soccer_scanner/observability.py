"""Small structured logging and in-process metrics primitives."""

import json
import re
from threading import Lock


DEFAULT_METRICS = {
    'api.requests',
    'api.errors',
    'api.rate_limited',
    'api.provider_health_degraded',
    'provider.requests',
    'provider.failures',
    'provider.rate_limited',
    'provider.duration_ms',
    'cache.hit',
    'cache.miss',
    'cache.stale_hit',
    'cache.eviction',
    'cache.fill_ms',
    'fixture.deduplicated',
    'team.mapping_failure',
}
_SENSITIVE_KEY = re.compile(r'(?:api.?key|token|secret|score|payload|body)', re.IGNORECASE)


class MetricsRegistry:
    def __init__(self, allowed_names=None):
        self.allowed_names = frozenset(allowed_names or DEFAULT_METRICS)
        self._counters = {}
        self._timings = {}
        self._lock = Lock()

    def _validate(self, name):
        if name not in self.allowed_names:
            raise KeyError(f'Unknown metric name: {name}')

    def increment(self, name, amount=1):
        self._validate(name)
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def observe_ms(self, name, duration_ms):
        self._validate(name)
        value = max(0, round(float(duration_ms)))
        with self._lock:
            timing = self._timings.setdefault(name, {'count': 0, 'totalMs': 0, 'maxMs': 0})
            timing['count'] += 1
            timing['totalMs'] += value
            timing['maxMs'] = max(timing['maxMs'], value)

    def snapshot(self):
        with self._lock:
            return {
                'counters': dict(self._counters),
                'timings': {name: dict(value) for name, value in self._timings.items()},
            }


def _safe_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if not _SENSITIVE_KEY.search(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return str(value)


def log_event(logger, event, **fields):
    record = {'event': str(event)}
    record.update({
        str(key): _safe_value(value)
        for key, value in fields.items()
        if not _SENSITIVE_KEY.search(str(key))
    })
    logger.info(json.dumps(record, separators=(',', ':'), sort_keys=True))
