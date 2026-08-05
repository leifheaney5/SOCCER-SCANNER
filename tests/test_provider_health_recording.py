import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from soccer_scanner import create_app
from soccer_scanner.domain.models import ProviderOutcome, ProviderStatus
from soccer_scanner.services.cache_backend import MemoryCacheBackend
from soccer_scanner.services.fixture_service import CanonicalFixtureService
from soccer_scanner.services.provider_health import ProviderHealthRegistry


class FakeClock:
    def __init__(self, value=1_770_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def outcome(provider, status, failure_categories=()):
    return ProviderOutcome(
        provider=provider,
        status=status,
        fixtures=(),
        requestedResources=(),
        completedResources=(),
        requestCount=1,
        timeoutCount=0,
        rateLimitCount=0,
        sourceUpdatedAt=None,
        durationMs=5,
        failureCategories=tuple(failure_categories),
    )


def stub_provider(name, result):
    provider = Mock()
    provider.provider_name = name
    provider.fetch_range = Mock(return_value=result)
    return provider


class _RaisesForKeySubstring:
    """Cache stand-in that raises a non-`_ProviderFailure` exception the
    first time a key containing `raise_for` is filled, then delegates
    everything else to a real cache. Simulates faults such as
    cache_backend.py's oversized-value `ValueError` or a Redis `TimeoutError`
    that are not part of the provider-outcome vocabulary."""

    def __init__(self, real_cache, raise_for):
        self.real_cache = real_cache
        self.raise_for = raise_for

    def get_or_load(self, key, loader, **kwargs):
        if self.raise_for in key:
            raise ValueError('boom: internal serialization detail leak-token-XYZ123')
        return self.real_cache.get_or_load(key, loader, **kwargs)

    def get(self, key, **kwargs):
        return self.real_cache.get(key, **kwargs)

    def set(self, key, value, **kwargs):
        return self.real_cache.set(key, value, **kwargs)


def build_service(espn_result, football_result, registry):
    return CanonicalFixtureService(
        stub_provider('espn', espn_result),
        stub_provider('football-data', football_result),
        MemoryCacheBackend(),
        provider_health=registry,
        now=lambda: datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
    )


class ProviderHealthRecordingTest(unittest.TestCase):
    def test_a_successful_fetch_marks_both_providers_healthy(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.SUCCESS),
            outcome('football-data', ProviderStatus.SUCCESS),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'ok')
        self.assertEqual({item['name'] for item in snapshot['providers']},
                         {'espn', 'football-data'})

    def test_a_failing_provider_is_recorded_with_its_failure_category(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.SUCCESS),
            outcome('football-data', ProviderStatus.UNAVAILABLE, ('timeout',)),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        recorded = {
            item['name']: item for item in registry.snapshot()['providers']
        }
        self.assertEqual(recorded['football-data']['status'], 'unavailable')
        self.assertIn('timeout', recorded['football-data']['detail'])
        self.assertEqual(registry.snapshot()['status'], 'degraded')

    def test_a_disabled_provider_does_not_degrade_health(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.SUCCESS),
            outcome('football-data', ProviderStatus.DISABLED),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        self.assertEqual(registry.snapshot()['status'], 'ok')
        self.assertTrue(registry.snapshot()['singleProvider'])

    def test_recording_happens_on_every_call_not_only_on_a_cache_miss(self):
        # The cache-outer-path property: recording must run on the code path
        # that executes on *every* request, not only inside the loader that
        # runs on a cache miss. Otherwise a provider that never fails once
        # (and is then served from cache) would silently stop being observed.
        clock = FakeClock()
        registry = ProviderHealthRegistry(clock=clock)
        espn = stub_provider('espn', outcome('espn', ProviderStatus.SUCCESS))
        football_data = stub_provider(
            'football-data', outcome('football-data', ProviderStatus.SUCCESS)
        )
        service = CanonicalFixtureService(
            espn,
            football_data,
            MemoryCacheBackend(),
            provider_health=registry,
            now=lambda: datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')
        first_observed = {
            item['name']: item['lastObservedAt']
            for item in registry.snapshot()['providers']
        }

        clock.advance(30)
        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')
        second_observed = {
            item['name']: item['lastObservedAt']
            for item in registry.snapshot()['providers']
        }

        # Second call must be served from cache, not a fresh upstream fetch.
        self.assertEqual(espn.fetch_range.call_count, 1)
        self.assertEqual(football_data.fetch_range.call_count, 1)
        # Yet health must still have been recorded again on the second call.
        self.assertNotEqual(first_observed['espn'], second_observed['espn'])
        self.assertNotEqual(
            first_observed['football-data'], second_observed['football-data']
        )

    def test_a_partial_outcome_is_recorded_as_degraded(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.PARTIAL, ('timeout',)),
            outcome('football-data', ProviderStatus.SUCCESS),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        recorded = {
            item['name']: item for item in registry.snapshot()['providers']
        }
        self.assertEqual(recorded['espn']['status'], 'degraded')

    def test_a_rate_limited_outcome_is_recorded_as_unavailable(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.RATE_LIMITED, ('rate_limited',)),
            outcome('football-data', ProviderStatus.SUCCESS),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        recorded = {
            item['name']: item for item in registry.snapshot()['providers']
        }
        self.assertEqual(recorded['espn']['status'], 'unavailable')

    def test_a_non_provider_failure_from_the_cache_still_lets_the_second_provider_run(self):
        # cache_backend.py raises plain ValueError/TimeoutError for faults
        # (oversized value, Redis timeout) that are unrelated to what the
        # provider itself returned. Before this fix such an exception escaped
        # the loop entirely: the second provider was never attempted and
        # neither provider's outcome was recorded.
        registry = ProviderHealthRegistry()
        real_cache = MemoryCacheBackend()
        cache = _RaisesForKeySubstring(real_cache, 'espn')
        espn = stub_provider('espn', outcome('espn', ProviderStatus.SUCCESS))
        football_data = stub_provider(
            'football-data', outcome('football-data', ProviderStatus.SUCCESS)
        )
        service = CanonicalFixtureService(
            espn,
            football_data,
            cache,
            provider_health=registry,
            now=lambda: datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        # (a) the second provider is still attempted.
        self.assertEqual(football_data.fetch_range.call_count, 1)
        recorded = {
            item['name']: item for item in registry.snapshot()['providers']
        }
        # (b) the first provider is recorded unavailable.
        self.assertEqual(recorded['espn']['status'], 'unavailable')
        # (c) detail carries no exception text.
        self.assertEqual(recorded['espn']['detail'], 'internal_error')
        self.assertNotIn('boom', recorded['espn']['detail'])
        self.assertNotIn('XYZ123', recorded['espn']['detail'])

    def test_the_registry_is_wired_into_the_application_service(self):
        app = create_app({'TESTING': True})

        self.assertIs(
            app.extensions['fixture_service'].provider_health,
            app.extensions['provider_health'],
        )


if __name__ == '__main__':
    unittest.main()
