import json
import unittest
from unittest.mock import Mock


def observability_types():
    try:
        from soccer_scanner.observability import MetricsRegistry, log_event
    except ModuleNotFoundError as error:
        raise AssertionError('observability boundary is not implemented') from error
    return MetricsRegistry, log_event


class ObservabilityTest(unittest.TestCase):
    def test_metrics_registry_tracks_bounded_counters_and_timings(self):
        MetricsRegistry, _ = observability_types()
        registry = MetricsRegistry({'api.requests', 'provider.duration_ms'})

        registry.increment('api.requests')
        registry.increment('api.requests', 2)
        registry.observe_ms('provider.duration_ms', 12)
        registry.observe_ms('provider.duration_ms', 8)

        self.assertEqual(registry.snapshot(), {
            'counters': {'api.requests': 3},
            'timings': {
                'provider.duration_ms': {
                    'count': 2,
                    'totalMs': 20,
                    'maxMs': 12,
                },
            },
        })
        with self.assertRaises(KeyError):
            registry.increment('user-controlled-name')

    def test_structured_log_omits_secrets_payloads_and_scores(self):
        _, log_event = observability_types()
        logger = Mock()

        log_event(
            logger,
            'provider_completed',
            provider='espn',
            fixtureCount=4,
            apiKey='top-secret',
            score={'home': 2, 'away': 1},
            payload={'events': ['private-body']},
        )

        encoded = logger.info.call_args.args[0]
        record = json.loads(encoded)
        self.assertEqual(record, {
            'event': 'provider_completed',
            'provider': 'espn',
            'fixtureCount': 4,
        })
        self.assertNotIn('top-secret', encoded)
        self.assertNotIn('private-body', encoded)


if __name__ == '__main__':
    unittest.main()
