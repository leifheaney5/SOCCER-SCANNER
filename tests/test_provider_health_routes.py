import os
import unittest
from unittest.mock import Mock, patch

from soccer_scanner import create_app


class ProviderHealthRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})
        self.client = self.app.test_client()

    def test_readiness_includes_a_provider_block(self):
        payload = self.client.get('/health/ready').json

        self.assertIn('providers', payload)
        self.assertIn('status', payload['providers'])

    def test_provider_detail_route_is_available(self):
        self.app.extensions['provider_health'].record('espn', 'ok')

        response = self.client.get('/health/providers')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'ok')
        self.assertEqual(response.json['providers'][0]['name'], 'espn')

    def test_a_total_provider_outage_never_fails_readiness(self):
        environment = {
            'APP_ENVIRONMENT': 'production',
            'GIT_COMMIT_SHA': '0123456789abcdef0123456789abcdef01234567',
        }
        with patch.dict(os.environ, environment, clear=False):
            production = create_app({'TESTING': False})
        production.extensions['fixture_identities'] = Mock(
            durable=True,
            health=Mock(return_value={
                'backend': 'database', 'reachable': True,
                'schemaVersion': '20260804_01', 'status': 'ready',
            }),
        )
        production.extensions['cache_backend'] = Mock(
            health=Mock(return_value={
                'backend': 'redis', 'shared': True, 'status': 'ready',
            }),
        )
        production.extensions['rate_limiter'] = Mock(shared=True, degraded=False)
        production.extensions['provider_health'].record('espn', 'unavailable')

        ready = production.test_client().get('/health/ready')

        # A 503 here would fail Railway's healthcheck and roll the deploy back
        # over an upstream outage that redeploying cannot fix.
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json['status'], 'ready')
        self.assertNotIn('providers_unavailable', ready.json['blocking'])
        self.assertEqual(ready.json['providers']['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
