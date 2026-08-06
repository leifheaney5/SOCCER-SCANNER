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
from soccer_scanner.services.streaming import StreamingRegistry
from soccer_scanner.persistence.database import Base, DatabaseRuntime, SchemaMetadata
from soccer_scanner.persistence.fixture_identities import FixtureIdentityRepository


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


def service(
    espn_outcome,
    football_outcome,
    *,
    clock=None,
    cache=None,
    identity_registry=None,
    streaming_registry=None,
):
    clock = clock or Clock()
    cache = cache or MemoryCacheBackend(
        default_ttl_seconds=10,
        default_stale_ttl_seconds=30,
        clock=clock,
    )
    espn = Provider(espn_outcome)
    football = Provider(football_outcome)
    options = {
        'cache_ttl_seconds': 10,
        'stale_ttl_seconds': 30,
        'provider_budget_seconds': 2,
    }
    if identity_registry is not None:
        options['identity_registry'] = identity_registry
    if streaming_registry is not None:
        options['streaming_registry'] = streaming_registry
    return CanonicalFixtureService(
        espn,
        football,
        cache,
        **options,
    ), espn, football


def streaming_registry():
    return StreamingRegistry([
        {
            'id': 'peacock',
            'displayName': 'Peacock',
            'aliases': ['peacock'],
            'domains': ['peacocktv.com'],
            'officialUrl': 'https://www.peacocktv.com/',
        },
    ])


def repository(tmp_path):
    runtime = DatabaseRuntime.from_config({
        'DATABASE_URL': f'sqlite:///{(tmp_path / "identity.db").as_posix()}',
    })
    Base.metadata.create_all(runtime.engine)
    with runtime.session_scope() as session:
        session.add(SchemaMetadata(key='schema_version', value='20260804_01'))
    return runtime, FixtureIdentityRepository(runtime)


def unmapped_fixture(identifier, kickoff='2026-08-03T19:00:00Z'):
    match = fixture('espn', identifier)
    match['utcDate'] = kickoff
    for field in ('homeTeam', 'awayTeam', 'competition'):
        entity = match[field]
        entity['canonicalId'] = None
        entity['provider'] = 'espn'
        entity['providerId'] = f'{field}-{identifier}'
        entity['providerIds'] = {'espn': f'{field}-{identifier}'}
    return match


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


def test_composed_fixtures_are_available_through_bounded_canonical_lookup():
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [fixture('espn', '1')]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
    )

    result = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    fixture_id = result['matches'][0]['canonicalFixtureId']

    assert scanner.lookup_fixture(fixture_id) == result['matches'][0]
    assert scanner.lookup_fixture('fx_' + ('0' * 24)) is None


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


def test_dst_local_day_filters_once_and_analytics_use_local_hours():
    before_midnight = fixture('espn', 'before')
    before_midnight['utcDate'] = '2026-03-08T04:30:00Z'
    after_midnight = fixture('espn', 'after')
    after_midnight['utcDate'] = '2026-03-08T05:30:00Z'
    after_jump = fixture('espn', 'jump')
    after_jump['utcDate'] = '2026-03-08T07:30:00Z'
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [before_midnight, after_midnight, after_jump]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
    )

    result = scanner.fixtures_for_date(date(2026, 3, 8), 'America/New_York')

    assert len(result['matches']) == 2
    assert {match['providerIds']['espn'] for match in result['matches']} == {'after', 'jump'}
    assert result['matchStatistics']['byTimeSlot']['lateNight'] == 2


def test_full_response_identity_registry_keeps_ten_same_kickoff_events_unique(tmp_path):
    runtime, identity_registry = repository(tmp_path)
    fixtures = [unmapped_fixture(f'event-{index}') for index in range(10)]
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, fixtures),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        identity_registry=identity_registry,
    )

    result = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert len(result['matches']) == 10
    assert len({match['canonicalFixtureId'] for match in result['matches']}) == 10
    runtime.dispose()


def test_duplicate_public_ids_fail_before_fixture_lookup_cache_writes():
    class CollidingRegistry:
        def resolve(self, _group, _match):
            return 'fx_' + ('a' * 24)

    class TrackingCache(MemoryCacheBackend):
        def __init__(self):
            super().__init__()
            self.set_keys = []

        def set(self, key, value, *, ttl_seconds=None, stale_ttl_seconds=None):
            self.set_keys.append(key)
            return super().set(
                key,
                value,
                ttl_seconds=ttl_seconds,
                stale_ttl_seconds=stale_ttl_seconds,
            )

    cache = TrackingCache()
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [
            unmapped_fixture('event-1'),
            unmapped_fixture('event-2'),
        ]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        cache=cache,
        identity_registry=CollidingRegistry(),
    )

    with pytest.raises(RuntimeError, match='Duplicate public fixture ID'):
        scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert not any(key.startswith('fixture-lookup:') for key in cache.set_keys)


def test_deep_link_recovers_after_cache_loss_and_kickoff_correction(tmp_path):
    runtime, identity_registry = repository(tmp_path)
    original = unmapped_fixture('event-1')
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [original]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        identity_registry=identity_registry,
    )
    first = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')['matches'][0]

    corrected = unmapped_fixture('event-1', kickoff='2026-08-03T19:45:00Z')
    restarted, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [corrected]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        identity_registry=identity_registry,
    )

    recovered = restarted.lookup_fixture(first['canonicalFixtureId'], 'UTC')

    assert recovered['canonicalFixtureId'] == first['canonicalFixtureId']
    assert recovered['utcDate'] == '2026-08-03T19:45:00Z'
    runtime.dispose()


def test_composed_fixtures_are_enriched_with_streaming_and_keep_raw_broadcasts():
    match = fixture('espn', '1')
    match['broadcasts'] = [{'name': 'Peacock', 'type': 'STREAMING', 'region': 'US'}]
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [match]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        streaming_registry=streaming_registry(),
    )

    result = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    composed = result['matches'][0]

    # The raw provider-reported broadcasts survive alongside the enrichment,
    # for backward compatibility.
    assert composed['broadcasts'] == match['broadcasts']
    assert composed['streaming'] == [{
        'id': 'peacock',
        'displayName': 'Peacock',
        'officialUrl': 'https://www.peacocktv.com/',
        'region': 'US',
        'regionKnown': True,
        'source': 'espn',
    }]


def test_an_unverified_broadcast_composes_with_no_link():
    match = fixture('espn', '1')
    match['broadcasts'] = [
        {'name': 'Some Regional Stream', 'type': 'STREAMING', 'region': None},
    ]
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [match]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        streaming_registry=streaming_registry(),
    )

    result = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    described = result['matches'][0]['streaming'][0]

    # Linking an unrecognised name could send a visitor anywhere: the
    # no-link guarantee holds at the service layer, not only in the browser.
    assert described['officialUrl'] is None
    assert described['region'] == 'Region unknown'


def test_streaming_enrichment_persists_across_a_warm_provider_cache():
    # The cache-outer-path property: `_compose` (and therefore enrichment)
    # runs on every `fixtures_for_date` call, including a cache hit that
    # never calls the provider's `fetch_range` again — only the recomposed
    # cached provider outcome is re-enriched.
    match = fixture('espn', '1')
    match['broadcasts'] = [{'name': 'Peacock', 'type': 'STREAMING', 'region': 'US'}]
    scanner, espn, football = service(
        outcome('espn', ProviderStatus.SUCCESS, [match]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
        streaming_registry=streaming_registry(),
    )

    first = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    second = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')

    assert len(espn.calls) == 1
    assert first['matches'][0]['streaming']
    assert second['matches'][0]['streaming']


def test_a_service_without_a_streaming_registry_composes_without_a_streaming_key():
    match = fixture('espn', '1')
    match['broadcasts'] = [{'name': 'Peacock', 'type': 'STREAMING', 'region': 'US'}]
    scanner, _, _ = service(
        outcome('espn', ProviderStatus.SUCCESS, [match]),
        outcome('football-data', ProviderStatus.DISABLED, completed=()),
    )

    result = scanner.fixtures_for_date(date(2026, 8, 3), 'UTC')
    composed = result['matches'][0]

    assert 'streaming' not in composed
    assert composed['broadcasts'] == match['broadcasts']
