import unittest

from soccer_scanner.services.broadcast_coverage import BroadcastCoverageService
from soccer_scanner.services.broadcast_sources import BroadcastSourceRegistry


class BroadcastCoverageServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BroadcastCoverageService(BroadcastSourceRegistry([{
            'id': 'uefa-where-to-watch', 'provider': 'uefa',
            'url': 'https://www.uefa.com/match-calendar/',
            'allowedDomains': ['uefa.com'], 'status': 'active',
        }]))
        self.match = {
            'canonicalFixtureId': 'fx_' + ('a' * 24),
            'utcDate': '2026-08-13T19:00:00Z',
            'homeTeam': {'name': 'Arsenal'}, 'awayTeam': {'name': 'Chelsea'},
            'streaming': [],
        }

    def test_only_verified_observations_are_added_to_fixture_streaming(self):
        result = self.service.enrich([self.match], [{
            'sourceId': 'uefa-where-to-watch', 'homeTeam': 'Arsenal',
            'awayTeam': 'Chelsea', 'utcDate': '2026-08-13T19:00:00Z',
            'displayName': 'UEFA.tv', 'region': 'US',
            'officialUrl': 'https://www.uefa.com/uefatv/',
            'observedAt': '2026-08-13T18:00:00Z',
        }])

        self.assertEqual(result['metrics']['verifiedLinks'], 1)
        self.assertEqual(result['matches'][0]['streaming'][0]['officialUrl'],
                         'https://www.uefa.com/uefatv/')

    def test_enrichment_does_not_mutate_input_or_add_unverified_records(self):
        original = {**self.match, 'streaming': []}
        result = self.service.enrich([original], [{
            'sourceId': 'uefa-where-to-watch', 'homeTeam': 'Arsenal',
            'awayTeam': 'Chelsea', 'utcDate': '2026-08-13T19:00:00Z',
            'displayName': 'UEFA.tv', 'officialUrl': 'https://example.com/watch',
        }])

        self.assertEqual(original['streaming'], [])
        self.assertEqual(result['matches'][0]['streaming'], [])
        self.assertEqual(result['metrics']['verifiedLinks'], 0)
