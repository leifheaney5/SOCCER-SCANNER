import unittest

from soccer_scanner.services.provider_health import ProviderHealthRegistry


class FakeClock:
    def __init__(self, value=1_770_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class ProviderHealthRegistryTest(unittest.TestCase):
    def test_reports_unknown_before_any_observation(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        snapshot = registry.snapshot()

        self.assertEqual(snapshot['status'], 'unknown')
        self.assertEqual(snapshot['providers'], [])
        self.assertIsNone(snapshot['lastSuccessAt'])

    def test_all_healthy_providers_report_ok(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'ok')

        self.assertEqual(registry.snapshot()['status'], 'ok')

    def test_one_failing_provider_degrades_rather_than_fails(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable', detail='connect timeout')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'degraded')

    def test_every_provider_failing_reports_unavailable(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'unavailable')
        registry.record('football-data', 'unavailable')

        self.assertEqual(registry.snapshot()['status'], 'unavailable')

    def test_disabled_providers_do_not_count_against_health(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        self.assertEqual(registry.snapshot()['status'], 'ok')

    def test_last_success_is_retained_after_a_later_failure(self):
        clock = FakeClock()
        registry = ProviderHealthRegistry(clock=clock)

        registry.record('espn', 'ok')
        clock.advance(120)
        registry.record('espn', 'unavailable', detail='HTTP 503')

        provider = registry.snapshot()['providers'][0]
        self.assertEqual(provider['status'], 'unavailable')
        self.assertEqual(provider['detail'], 'HTTP 503')
        # The success timestamp must survive so staleness is measurable.
        self.assertIsNotNone(provider['lastSuccessAt'])
        self.assertNotEqual(provider['lastSuccessAt'], provider['lastObservedAt'])

    def test_timestamps_are_iso8601_utc(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')

        provider = registry.snapshot()['providers'][0]
        self.assertTrue(provider['lastSuccessAt'].endswith('+00:00'))
        self.assertIn('T', provider['lastSuccessAt'])

    def test_a_lone_configured_provider_is_flagged(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        # One usable provider means no fallback exists.
        self.assertTrue(registry.snapshot()['singleProvider'])

    def test_two_usable_providers_are_not_flagged_as_single(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable')

        self.assertFalse(registry.snapshot()['singleProvider'])

    def test_providers_are_reported_in_a_stable_order(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('zebra', 'ok')
        registry.record('alpha', 'ok')

        names = [item['name'] for item in registry.snapshot()['providers']]
        self.assertEqual(names, ['alpha', 'zebra'])

    def test_unknown_status_values_are_rejected(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        with self.assertRaises(ValueError):
            registry.record('espn', 'exploded')


if __name__ == '__main__':
    unittest.main()
