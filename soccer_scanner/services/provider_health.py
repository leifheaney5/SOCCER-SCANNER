"""In-process provider health tracking.

Readiness answers "can this process serve requests", which stayed true during a
real production outage where every fixture request failed. This registry
answers the different question of whether upstream data is actually flowing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
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

        accountable = [
            state for state in states.values() if state.status != 'disabled'
        ]
        if not accountable:
            status = 'unknown' if not states else 'unavailable'
        elif all(state.status in _COUNTS_AGAINST_HEALTH for state in accountable):
            status = 'unavailable'
        elif any(state.status in _COUNTS_AGAINST_HEALTH for state in accountable):
            status = 'degraded'
        else:
            status = 'ok'
        if not states:
            status = 'unknown'

        successes = [
            state.last_success_at for state in states.values()
            if state.last_success_at is not None
        ]
        return {
            'status': status,
            'providers': providers,
            'lastSuccessAt': _isoformat(max(successes)) if successes else None,
            # One usable provider means an upstream failure has no fallback.
            'singleProvider': len(accountable) <= 1,
        }
