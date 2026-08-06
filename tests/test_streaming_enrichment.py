import unittest

from soccer_scanner import create_app


class StreamingEnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})

    def test_the_registry_is_registered(self):
        self.assertIn('streaming_registry', self.app.extensions)

    def test_a_known_service_is_enriched_with_an_official_url(self):
        registry = self.app.extensions['streaming_registry']

        described = registry.describe({
            'type': 'STREAMING', 'name': 'Peacock', 'region': 'US',
        })

        self.assertEqual(described['displayName'], 'Peacock')
        self.assertTrue(described['officialUrl'].startswith('https://'))
        self.assertEqual(described['region'], 'US')

    def test_an_unknown_service_is_never_given_a_link(self):
        registry = self.app.extensions['streaming_registry']

        described = registry.describe({
            'type': 'STREAMING', 'name': 'Unverified Stream', 'region': None,
        })

        # Linking an unrecognised name could send a visitor anywhere.
        self.assertIsNone(described['officialUrl'])
        self.assertEqual(described['region'], 'Region unknown')


if __name__ == '__main__':
    unittest.main()
