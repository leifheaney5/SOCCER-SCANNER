import unittest
from pathlib import Path

from soccer_scanner import create_app
from soccer_scanner.services.broadcast_sources import (
    BroadcastObservation,
    BroadcastSourceRegistry,
    match_source_listing,
)


REGISTRY_PATH = Path('soccer_scanner/data/broadcast-sources.json')


class BroadcastSourceRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = BroadcastSourceRegistry.from_file(REGISTRY_PATH)

    def test_registry_contains_only_https_official_sources(self):
        sources = self.registry.sources()

        self.assertGreaterEqual(len(sources), 2)
        self.assertTrue(all(item['url'].startswith('https://') for item in sources))
        self.assertTrue(all(item['status'] in {'inventory', 'observation', 'active'} for item in sources))

    def test_source_scope_is_explicit_and_copy_is_immutable(self):
        source = self.registry.get('espn-broadcasts')

        self.assertEqual(source['provider'], 'espn')
        self.assertIn('fixture-level', source['scope'])
        source['scope'].append('changed')
        self.assertNotIn('changed', self.registry.get('espn-broadcasts')['scope'])

    def test_unknown_source_is_not_resolvable(self):
        self.assertIsNone(self.registry.get('not-a-source'))

    def test_matches_a_listing_only_when_both_teams_date_and_kickoff_agree(self):
        match = {
            'utcDate': '2026-08-13T19:00:00Z',
            'homeTeam': {'name': 'Arsenal'},
            'awayTeam': {'name': 'Chelsea'},
        }
        listing = {
            'utcDate': '2026-08-13T19:08:00Z',
            'homeTeam': 'Arsenal',
            'awayTeam': 'Chelsea',
            'displayName': 'Official Stream',
        }

        self.assertTrue(match_source_listing(listing, match))
        self.assertFalse(match_source_listing({**listing, 'awayTeam': 'Fulham'}, match))
        self.assertFalse(match_source_listing({**listing, 'utcDate': '2026-08-13T19:31:00Z'}, match))

    def test_normalizes_a_verified_listing_without_inventing_a_url(self):
        listing = {
            'sourceId': 'espn-broadcasts',
            'displayName': 'ESPN+',
            'region': 'US',
            'observedAt': '2026-08-13T18:00:00Z',
        }

        described = self.registry.describe_listing(listing)

        self.assertEqual(described['displayName'], 'ESPN+')
        self.assertEqual(described['region'], 'US')
        self.assertIsNone(described['officialUrl'])
        self.assertEqual(described['status'], 'unlinked')

    def test_observation_metrics_are_explicit_and_serializable(self):
        observation = BroadcastObservation()
        observation.observed = 4
        observation.matched = 3
        observation.verified_links = 2
        observation.region_known = 1
        observation.stale = 1
        observation.unmatched = 1
        observation.ambiguous = 1

        self.assertEqual(observation.as_dict(), {
            'observed': 4,
            'matched': 3,
            'verifiedLinks': 2,
            'regionKnown': 1,
            'stale': 1,
            'unmatched': 1,
            'ambiguous': 1,
        })

    def test_application_registers_the_source_inventory(self):
        app = create_app({'TESTING': True})

        self.assertIs(app.extensions['broadcast_sources'].__class__, BroadcastSourceRegistry)
        self.assertIsNotNone(app.extensions['broadcast_sources'].get('espn-broadcasts'))


if __name__ == '__main__':
    unittest.main()
