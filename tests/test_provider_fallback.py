import unittest

from soccer_scanner import create_app


class ProviderFallbackTest(unittest.TestCase):
    def test_without_a_key_the_secondary_provider_is_disabled(self):
        app = create_app({'TESTING': True, 'FOOTBALL_DATA_API_KEY': None})

        self.assertFalse(app.extensions['football_data_provider'].enabled)

    def test_supplying_a_key_enables_the_secondary_provider(self):
        app = create_app({'TESTING': True, 'FOOTBALL_DATA_API_KEY': 'test-key'})

        self.assertTrue(app.extensions['football_data_provider'].enabled)

    def test_a_single_usable_provider_is_reported_as_a_risk(self):
        app = create_app({'TESTING': True, 'FOOTBALL_DATA_API_KEY': None})
        registry = app.extensions['provider_health']
        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        snapshot = app.test_client().get('/health/providers').json

        self.assertTrue(snapshot['singleProvider'])
        self.assertEqual(snapshot['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
