from datetime import date

import pytest

from soccer_scanner.domain.models import (
    FixtureState,
    FixtureUnavailable,
    ProviderOutcome,
    ProviderStatus,
)
from soccer_scanner.services.cache_backend import MemoryCacheBackend
from soccer_scanner.services.fixture_service import CanonicalFixtureService


class Clock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class Provider:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def fetch_range(self, start_date, end_date, *, budget=None):
        self.calls.append((start_date, end_date))
        return self.outcome


def outcome(provider, status, fixtures=(), *, completed=('all',), failures=()):
    return ProviderOutcome(
        provider=provider,
        status=status,
        fixtures=tuple(fixtures),
        requestedResources=('all',),
        completedResources=tuple(completed),
        requestCount=1,
        timeoutCount=0,
        rateLimitCount=1 if status is ProviderStatus.RATE_LIMITED else 0,
        sourceUpdatedAt='2026-08-03T12:00:00Z',
        durationMs=5,
        failureCategories=tuple(failures),
    )


def fixture(provider, identifier):
    return {
        'canonicalFixtureId': None,
        'providerIds': {provider: identifier},
        'utcDate': '2026-08-03T19:00:00Z',
        'status': {'code': 'scheduled', 'raw': 'raw', 'completed': False},
        'homeTeam': {'canonicalId': 'arsenal', 'name': 'Arsenal', 'providerIds': {provider: 'home'}},
        'awayTeam': {'canonicalId': 'chelsea', 'name': 'Chelsea', 'providerIds': {provider: 'away'}},
        'competition': {'canonicalId': 'premier-league', 'name': 'Premier League', 'providerIds': {provider: 'pl'}},
        'score': {'winner': None, 'fullTime': {'home': None, 'away': None}},
        'season': {'year': 2026},
        'stage': 'regular-season',
        'round': None,
        'matchday': 1,
        'venue': None,
        'referees': None,
        'aggregate': None,
        'sourceUpdatedAt': '2026-08-03T12:00:00Z',
        'sources': [provider],
    }


def service(espn_outcome, football_outcome, *, clock=None):
    clock = clock or Clock()
    cache = MemoryCacheBackend(
        default_ttl_seconds=10,
        default_stale_ttl_seconds=30,
        clock=clock,
    )
    espn = Provider(espn_outcome)
    football = Provider(football_outcome)
    return CanonicalFixtureService(
        espn,
        football,
        cache,
        cache_ttl_seconds=10,
        stale_ttl_seconds=30,
        provider_budget_seconds=2,
    ), espn, football


def test_full_success_and_authoritative_empty_have_distinct_states():
    populated, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [fixture('espn', '1')]),
        outcome('football-data', ProviderStatus.SUCCESS, []),
    )
    empty, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, []),
        outcome('football-data', ProviderStatus.SUCCESS, []),
    )

    success_result = populated.fixtures_for_date(date(2026, 8, 3), 'UTC')
    empty_result = empty.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert success_result['state'] == FixtureState.SUCCESS.value
    assert empty_result['state'] == FixtureState.EMPTY_CONFIRMED.value


def test_partial_results_never_look_like_a_confirmed_empty_day():
    fixtures = []
    for index in range(6):
        item = fixture('espn', str(index))
        item['utcDate'] = f'2026-08-03T{10 + index:02d}:00:00Z'
        fixtures.append(item)
    scanner, espn, football = service(
        outcome('espn', ProviderStatus.SUCCESS, fixtures),
        outcome('football-data', ProviderStatus.UNAVAILABLE, failures=('timeout',), completed=()),
    )

    result = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert result['state'] == FixtureState.PARTIAL.value
    assert len(result['matches']) == 6
    assert len(football.calls) == 1
    assert len(espn.calls) == 1


def test_total_outage_raises_stable_unavailable_and_is_not_cached():
    scanner, espn, football = service(
        outcome('espn', ProviderStatus.UNAVAILABLE, failures=('timeout',), completed=()),
        outcome('football-data', ProviderStatus.UNAVAILABLE, failures=('connection',), completed=()),
    )

    with pytest.raises(FixtureUnavailable) as caught:
        scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    with pytest.raises(FixtureUnavailable):
        scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert caught.value.state is FixtureState.PROVIDER_UNAVAILABLE
    assert len(espn.calls) == 2
    assert len(football.calls) == 2


def test_rate_limited_total_failure_preserves_retry_semantics():
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.RATE_LIMITED, failures=('rate_limited',), completed=()),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
    )

    with pytest.raises(FixtureUnavailable) as caught:
        scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert caught.value.state is FixtureState.RATE_LIMITED
    assert caught.value.retry_after_seconds == 30


def test_stale_data_is_only_used_when_no_current_provider_data_exists():
    clock = Clock()
    scanner, espn, football = service(
        outcome('espn', ProviderStatus.SUCCESS, [fixture('espn', '1')]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        clock=clock,
    )
    first = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    clock.advance(11)
    espn.outcome = outcome('espn', ProviderStatus.UNAVAILABLE, failures=('timeout',), completed=())

    stale = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert first['state'] == FixtureState.SUCCESS.value
    assert stale['state'] == FixtureState.STALE.value
    assert stale['matches'] == first['matches']
    assert stale['cache']['status'] == 'stale'


def test_provider_cache_is_timezone_independent_and_composition_is_local():
    scanner, espn, football = service(
        outcome('espn', ProviderStatus.SUCCESS, [fixture('espn', '1')]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
    )

    utc = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    abidjan = scanner.fixtures_for_date(date(2026, 8, 3), 'Africa/Abidjan')

    assert len(espn.calls) == 1
    assert len(football.calls) == 1
    assert utc['timezone'] == 'UTC'
    assert abidjan['timezone'] == 'Africa/Abidjan'
    assert abidjan['matches'][0]['localDate'] == '2026-08-03'
