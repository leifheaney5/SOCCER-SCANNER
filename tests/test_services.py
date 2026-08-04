import unittest
from datetime import date
from unittest.mock import Mock, patch

import requests

from soccer_scanner.services.cache import TTLCache
from soccer_scanner.services.fixtures import FixtureService
from soccer_scanner.services.teams import TeamAnalysisService
from soccer_scanner.services.team_identity import TeamIdentityResolver


class TTLCacheTest(unittest.TestCase):
    def test_stores_values(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set('fixtures', {'matches': []})

        self.assertEqual(cache.get('fixtures'), {'matches': []})

    def test_retains_expired_value_during_stale_window(self):
        cache = TTLCache(ttl_seconds=-1, stale_ttl_seconds=60)
        cache.set('fixtures', {'matches': []})

        self.assertIsNone(cache.get('fixtures'))
        self.assertEqual(cache.get_stale('fixtures'), {'matches': []})

    def test_evicts_least_recently_used_entry(self):
        cache = TTLCache(ttl_seconds=60, max_entries=2)
        cache.set('first', 1)
        cache.set('second', 2)
        cache.get('first')
        cache.set('third', 3)

        self.assertIsNone(cache.get('second'))
        self.assertEqual(cache.get('first'), 1)


class FixtureServiceTest(unittest.TestCase):
    @patch('soccer_scanner.services.fixtures.requests.get')
    def test_reuses_cached_fixture_response(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'events': []}
        get.return_value.raise_for_status.return_value = None
        football_data = Mock()
        football_data.get.return_value = {'matches': []}
        service = FixtureService(football_data, TTLCache(60))

        first = service.fixtures_for_date(date(2026, 8, 14))
        second = service.fixtures_for_date(date(2026, 8, 14))

        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(get.call_count, 20)
        football_data.get.assert_called_once()

    @patch('soccer_scanner.services.fixtures.requests.get')
    def test_reports_partial_provider_results(self, get):
        get.side_effect = requests.Timeout('provider timed out')
        football_data = Mock()
        football_data.get.side_effect = requests.Timeout('fallback timed out')
        service = FixtureService(football_data, TTLCache(60), fetch_deadline=0.1)

        result = service.fixtures_for_date(date(2026, 8, 14))

        self.assertTrue(result['partial'])
        self.assertEqual(result['providers']['espn']['status'], 'unavailable')
        self.assertEqual(result['providers']['football_data']['status'], 'unavailable')

    @patch('soccer_scanner.services.fixtures.requests.get')
    def test_espn_uses_one_inclusive_range_request_per_league(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'events': []}
        get.return_value.raise_for_status.return_value = None
        service = FixtureService(Mock(), TTLCache(60))

        service._fetch_espn([date(2026, 8, 3), date(2026, 8, 4)])

        self.assertEqual(get.call_count, 20)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs['params']['dates'], '20260803-20260804')

    @patch('soccer_scanner.services.fixtures.requests.get')
    def test_serves_stale_data_when_all_providers_fail(self, get):
        get.side_effect = requests.Timeout('provider timed out')
        football_data = Mock()
        football_data.get.side_effect = requests.Timeout('fallback timed out')
        cache = TTLCache(ttl_seconds=-1, stale_ttl_seconds=60)
        cache.set('2026-08-14|UTC', {'matches': [{'id': 1}], 'date': '2026-08-14'})
        service = FixtureService(football_data, cache, fetch_deadline=0.1)

        result = service.fixtures_for_date(date(2026, 8, 14))

        self.assertTrue(result['cached'])
        self.assertTrue(result['stale'])
        self.assertEqual(result['matches'], [{'id': 1}])

    def test_filters_fixture_using_the_users_local_calendar_date(self):
        match = {
            'id': 'late-match',
            'utcDate': '2026-08-15T01:00:00Z',
            'homeTeam': {'name': 'Home'},
            'awayTeam': {'name': 'Away'},
            'competition': {'name': 'League'},
            'status': 'SCHEDULED',
        }

        result = FixtureService._enhance_and_deduplicate(
            [match], date(2026, 8, 14), 'America/New_York'
        )

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['id'].startswith('fx_'))
        self.assertEqual(result[0]['utcDate'], '2026-08-15T01:00:00Z')

    def test_deduplicates_cross_provider_fixture_ids_using_canonical_identity(self):
        identities = TeamIdentityResolver([
            {
                'canonicalId': 'arsenal', 'name': 'Arsenal', 'aliases': ['Arsenal FC'],
                'providerIds': {'espn': '359', 'football-data': '57'},
            },
            {
                'canonicalId': 'chelsea', 'name': 'Chelsea', 'aliases': ['Chelsea FC'],
                'providerIds': {'espn': '363', 'football-data': '61'},
            },
        ])
        espn = {
            'id': 'espn_401', 'providerIds': {'espn': '401'},
            'utcDate': '2026-08-14T19:00:00Z', 'status': 'SCHEDULED',
            'sourceUpdatedAt': '2026-08-14T12:00:00Z',
            'homeTeam': {'provider': 'espn', 'providerId': '359', 'name': 'Arsenal'},
            'awayTeam': {'provider': 'espn', 'providerId': '363', 'name': 'Chelsea'},
            'competition': {'name': 'Premier League'},
            'score': {'fullTime': {'home': None, 'away': None}},
        }
        football_data = {
            'id': 9001, 'utcDate': '2026-08-14T19:05:00Z', 'status': 'TIMED',
            'lastUpdated': '2026-08-14T13:00:00Z',
            'homeTeam': {'id': 57, 'name': 'Arsenal FC'},
            'awayTeam': {'id': 61, 'name': 'Chelsea FC'},
            'competition': {'id': 2021, 'name': 'Premier League', 'code': 'PL'},
            'score': {'fullTime': {'home': None, 'away': None}},
        }

        result = FixtureService._enhance_and_deduplicate(
            [espn, football_data],
            date(2026, 8, 14),
            identity_resolver=identities,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['providerIds'], {'espn': '401', 'football-data': '9001'})
        self.assertTrue(result[0]['canonicalFixtureId'].startswith('fx_'))


class TeamAnalysisServiceTest(unittest.TestCase):
    def test_keeps_basic_team_data_when_match_history_is_unavailable(self):
        client = Mock()
        client.get.side_effect = [
            {'name': 'Example FC', 'squad': []},
            requests.Timeout(),
        ]

        result = TeamAnalysisService(client).analyze('10')

        self.assertEqual(result['team_info']['name'], 'Example FC')
        self.assertEqual(result['recent_matches'], [])
        self.assertEqual(result['upcoming_matches'], [])

    def test_fetches_team_matches_once_and_preserves_provider_played(self):
        client = Mock()
        finished = {
            'status': 'FINISHED',
            'homeTeam': {'id': 10},
            'awayTeam': {'id': 20},
            'score': {'fullTime': {'home': 2, 'away': 1}},
            'competition': {'id': 1, 'name': 'Test League'},
            'utcDate': '2026-08-01T12:00:00Z',
        }
        upcoming = {
            'status': 'SCHEDULED',
            'homeTeam': {'id': 20},
            'awayTeam': {'id': 10},
            'score': {'fullTime': {'home': None, 'away': None}},
            'competition': {'id': 1, 'name': 'Test League'},
            'utcDate': '2026-08-10T12:00:00Z',
        }
        client.get.side_effect = [
            {'name': 'Example FC', 'squad': []},
            {'matches': [finished, upcoming], 'resultSet': {'count': 2, 'played': 1}},
        ]

        result = TeamAnalysisService(client).analyze('10')

        self.assertEqual(client.get.call_count, 2)
        client.get.assert_any_call('teams/10/matches', params={'limit': 50})
        self.assertEqual(result['recent_matches'], [finished])
        self.assertEqual(result['upcoming_matches'], [upcoming])
        self.assertEqual(result['stats']['matches_played'], 1)


if __name__ == '__main__':
    unittest.main()
