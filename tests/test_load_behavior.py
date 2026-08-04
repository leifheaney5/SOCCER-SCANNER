import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import Mock

from soccer_scanner import create_app
from soccer_scanner.domain.models import ProviderOutcome, ProviderStatus
from soccer_scanner.observability import MetricsRegistry
from soccer_scanner.services.cache_backend import MemoryCacheBackend
from soccer_scanner.services.fixture_service import CanonicalFixtureService


class SlowProvider:
    def __init__(self, name, status, fixtures=()):
        self.provider_name = name
        self.status = status
        self.fixtures = tuple(fixtures)
        self.calls = 0
        self.lock = threading.Lock()

    def fetch_range(self, _start, _end, *, budget=None):
        with self.lock:
            self.calls += 1
        time.sleep(0.04)
        return ProviderOutcome(
            provider=self.provider_name,
            status=self.status,
            fixtures=self.fixtures,
            requestedResources=('fixtures',),
            completedResources=('fixtures',) if self.status is ProviderStatus.SUCCESS else (),
            requestCount=1,
            timeoutCount=0,
            rateLimitCount=0,
            sourceUpdatedAt='2026-08-03T12:00:00Z',
            durationMs=40,
            failureCategories=(),
        )


def normalized_fixture():
    return {
        'canonicalFixtureId': None,
        'providerIds': {'espn': 'load-1'},
        'utcDate': '2026-08-03T19:00:00Z',
        'status': {'code': 'scheduled', 'raw': 'STATUS_SCHEDULED', 'completed': False},
        'homeTeam': {'canonicalId': 'arsenal', 'name': 'Arsenal', 'providerIds': {'espn': 'home'}},
        'awayTeam': {'canonicalId': 'chelsea', 'name': 'Chelsea', 'providerIds': {'espn': 'away'}},
        'competition': {'canonicalId': 'premier-league', 'name': 'Premier League', 'providerIds': {'espn': 'eng.1'}},
        'score': {'winner': None, 'fullTime': {'home': None, 'away': None}},
        'sources': ['espn'],
        'sourceUpdatedAt': '2026-08-03T12:00:00Z',
    }


def test_simultaneous_timezone_requests_share_provider_fills():
    espn = SlowProvider('espn', ProviderStatus.SUCCESS, [normalized_fixture()])
    football = SlowProvider('football-data', ProviderStatus.DISABLED)
    cache = MemoryCacheBackend(default_ttl_seconds=60, metrics=MetricsRegistry())
    service = CanonicalFixtureService(espn, football, cache)

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [
            executor.submit(
                service.fixtures_for_date,
                date(2026, 8, 3),
                'UTC' if index % 2 == 0 else 'Africa/Abidjan',
            )
            for index in range(12)
        ]
        results = [future.result() for future in futures]

    assert espn.calls == 1
    assert football.calls == 1
    assert {result['timezone'] for result in results} == {'UTC', 'Africa/Abidjan'}
    assert all(len(result['matches']) == 1 for result in results)


def test_independent_cache_keys_fill_concurrently_without_a_global_lock():
    cache = MemoryCacheBackend(default_ttl_seconds=60)
    release = threading.Event()
    lock = threading.Lock()
    active = 0
    peak = 0

    def load(key):
        def loader():
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            release.wait(timeout=1)
            with lock:
                active -= 1
            return {'key': key}
        return cache.get_or_load(key, loader).value

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(load, f'key-{index}') for index in range(6)]
        deadline = time.monotonic() + 1
        while peak < 6 and time.monotonic() < deadline:
            time.sleep(0.005)
        release.set()
        results = [future.result() for future in futures]

    assert peak == 6
    assert len(results) == 6


def test_rate_limit_burst_has_a_stable_bounded_response():
    app = create_app({
        'TESTING': True,
        'RATE_LIMIT_MAX_REQUESTS': 3,
        'RATE_LIMIT_WINDOW_SECONDS': 60,
    })
    app.extensions['fixture_service'].fixtures_for_date = Mock(return_value={
        'matches': [],
        'date': '2026-08-03',
    })
    client = app.test_client()

    responses = [client.get('/api/v2/fixtures?date=2026-08-03') for _ in range(10)]

    assert [response.status_code for response in responses[:3]] == [200, 200, 200]
    assert all(response.status_code == 429 for response in responses[3:])
    assert all(response.json['error']['code'] == 'rate_limited' for response in responses[3:])
    assert all(response.headers['Retry-After'] == '60' for response in responses[3:])
