import unittest

from soccer_scanner.services.broadcast_adapter import OfficialBroadcastAdapter
from soccer_scanner.services.broadcast_sources import BroadcastSourceRegistry


class OfficialBroadcastAdapterTest(unittest.TestCase):
    def setUp(self):
        self.registry = BroadcastSourceRegistry([
            {
                'id': 'uefa-where-to-watch',
                'name': 'UEFA where to watch',
                'provider': 'uefa',
                'url': 'https://www.uefa.com/match-calendar/',
                'allowedDomains': ['uefa.com'],
                'status': 'active',
            },
        ])
        self.adapter = OfficialBroadcastAdapter(self.registry)
        self.match = {
            'canonicalFixtureId': 'fx_' + ('a' * 24),
            'utcDate': '2026-08-13T19:00:00Z',
            'homeTeam': {'name': 'Arsenal'},
            'awayTeam': {'name': 'Chelsea'},
        }

    def test_emits_verified_record_for_exact_match_and_declared_domain(self):
        result = self.adapter.match_listing({
            'sourceId': 'uefa-where-to-watch',
            'homeTeam': 'Arsenal',
            'awayTeam': 'Chelsea',
            'utcDate': '2026-08-13T19:08:00Z',
            'displayName': 'UEFA.tv',
            'region': 'US',
            'officialUrl': 'https://www.uefa.com/uefatv/',
            'observedAt': '2026-08-13T18:00:00Z',
        }, [self.match])

        self.assertEqual(result['fixtureKey'], self.match['canonicalFixtureId'])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['officialUrl'], 'https://www.uefa.com/uefatv/')
        self.assertTrue(result['regionKnown'])

    def test_rejects_wrong_domain_and_ambiguous_matches(self):
        wrong_domain = self.adapter.match_listing({
            'sourceId': 'uefa-where-to-watch',
            'homeTeam': 'Arsenal', 'awayTeam': 'Chelsea',
            'utcDate': '2026-08-13T19:00:00Z',
            'displayName': 'UEFA.tv',
            'officialUrl': 'https://example.com/watch',
        }, [self.match])
        self.assertEqual(wrong_domain['status'], 'unlinked')
        self.assertIsNone(wrong_domain['officialUrl'])

        ambiguous = self.adapter.match_listing({
            'sourceId': 'uefa-where-to-watch',
            'homeTeam': 'Arsenal', 'awayTeam': 'Chelsea',
            'utcDate': '2026-08-13T19:00:00Z',
            'displayName': 'UEFA.tv',
            'officialUrl': 'https://www.uefa.com/uefatv/',
        }, [self.match, {**self.match, 'canonicalFixtureId': 'fx_' + ('b' * 24)}])
        self.assertEqual(ambiguous['status'], 'ambiguous')
        self.assertIsNone(ambiguous['fixtureKey'])

    def test_missing_url_is_display_only_and_unknown_source_is_rejected(self):
        display_only = self.adapter.match_listing({
            'sourceId': 'uefa-where-to-watch',
            'homeTeam': 'Arsenal', 'awayTeam': 'Chelsea',
            'utcDate': '2026-08-13T19:00:00Z',
            'displayName': 'UEFA.tv',
        }, [self.match])
        self.assertEqual(display_only['status'], 'unlinked')
        self.assertEqual(display_only['fixtureKey'], self.match['canonicalFixtureId'])

        self.assertIsNone(self.adapter.match_listing({
            'sourceId': 'not-configured', 'displayName': 'Unknown',
        }, [self.match]))

    def test_observation_batch_reports_coverage_without_promoting_unmatched_rows(self):
        result = self.adapter.observe([
            {
                'sourceId': 'uefa-where-to-watch',
                'homeTeam': 'Arsenal', 'awayTeam': 'Chelsea',
                'utcDate': '2026-08-13T19:00:00Z',
                'displayName': 'UEFA.tv', 'region': 'US',
                'officialUrl': 'https://www.uefa.com/uefatv/',
            },
            {
                'sourceId': 'uefa-where-to-watch',
                'homeTeam': 'Unknown', 'awayTeam': 'Elsewhere',
                'utcDate': '2026-08-13T19:00:00Z',
                'displayName': 'UEFA.tv',
            },
        ], [self.match])

        self.assertEqual(result['metrics'], {
            'observed': 2, 'matched': 1, 'verifiedLinks': 1,
            'regionKnown': 1, 'stale': 0, 'unmatched': 1, 'ambiguous': 0,
        })
        self.assertEqual(len(result['records']), 2)
