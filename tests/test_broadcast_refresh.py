import unittest
from datetime import date, datetime, timedelta, timezone
from soccer_scanner import create_app
from soccer_scanner.services.broadcast_refresh import BroadcastObservationStore, BroadcastRefreshService
from soccer_scanner.services.broadcast_sources import BroadcastSourceRegistry
from soccer_scanner.services.cache_backend import MemoryCacheBackend
from soccer_scanner.services.broadcast_refresh import (
    OBSERVATION_STALE_SECONDS,
    OBSERVATION_TTL_SECONDS,
)


class BroadcastRefreshTest(unittest.TestCase):
    def test_failed_refresh_does_not_extend_the_last_observation_retention_window(self):
        clock = [0.0]
        cache = MemoryCacheBackend(clock=lambda: clock[0])
        store = BroadcastObservationStore(cache)
        updated_at = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        store.write({'observations': [], 'fixtures': [], 'coverage': {}, 'sources': {}},
                    updated_at=updated_at, age_seconds=3 * 60 * 60)

        clock[0] = OBSERVATION_TTL_SECONDS + OBSERVATION_STALE_SECONDS - 3 * 60 * 60 + 1

        self.assertIsNone(store.read())

    def test_refresh_stores_matching_positive_rows_but_never_infers_confirmed_none(self):
        app = create_app({'TESTING': True})
        store = app.extensions['broadcast_observation_store']
        observed_at = datetime(2026, 9, 29, 16, tzinfo=timezone.utc)
        fixture = {
            'canonicalFixtureId': 'fx_' + ('c' * 24),
            'utcDate': '2026-09-29T20:00:00Z',
            'homeTeam': {'name': 'Arsenal'},
            'awayTeam': {'name': 'Chelsea'},
            'competition': {'name': 'Premier League', 'canonicalId': 'eng.1'},
            'sourceUpdatedAt': '2026-09-29T15:50:00Z',
            'whereToWatch': [{
                'id': 'espn', 'displayName': 'ESPN', 'type': 'STREAMING',
                'region': 'US', 'officialUrl': 'https://www.espn.com/soccer/',
                'sourceId': 'espn-broadcasts', 'observedAt': '2026-09-29T15:50:00Z',
            }],
        }
        service = BroadcastRefreshService(
            store,
            lambda requested_date: {'state': 'success', 'matches': [fixture]},
            source_registry=app.extensions['broadcast_sources'],
            now=lambda: observed_at,
        )

        result = service.refresh(date(2026, 9, 29))
        stored = store.read()

        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(stored['observations']), 1)
        self.assertEqual(stored['observations'][0]['fixtureKey'], fixture['canonicalFixtureId'])
        self.assertEqual(stored['observations'][0]['status'], 'available')
        self.assertEqual(stored['coverage']['confirmedNone'], 0)
        self.assertEqual(stored['coverage']['coverageThresholdPercent'], 90)

    def test_failed_refresh_keeps_last_known_data_for_stale_reads(self):
        app = create_app({'TESTING': True})
        store = app.extensions['broadcast_observation_store']
        updated_at = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        store.write({
            'observations': [{'fixtureKey': 'fx_' + ('d' * 24), 'region': 'US'}],
            'fixtures': [], 'coverage': {'matched': 1}, 'sources': {},
        }, updated_at=updated_at)
        service = BroadcastRefreshService(
            store,
            lambda requested_date: {'state': 'provider_unavailable', 'matches': []},
            source_registry=app.extensions['broadcast_sources'],
            now=lambda: updated_at + timedelta(hours=3),
        )

        result = service.refresh(date(2026, 9, 29))
        stored = store.read()

        self.assertEqual(result['status'], 'stale')
        self.assertEqual(stored['observations'][0]['fixtureKey'], 'fx_' + ('d' * 24))
        self.assertEqual(stored['refreshStatus'], 'stale')

    def test_successful_fixture_refresh_replaces_old_rows_without_claiming_no_listing(self):
        app = create_app({'TESTING': True})
        store = app.extensions['broadcast_observation_store']
        fixture_id = 'fx_' + ('9' * 24)
        updated_at = datetime(2026, 9, 29, 16, tzinfo=timezone.utc)
        store.write({
            'observations': [{
                'fixtureKey': fixture_id, 'fixtureDate': '2026-09-29T20:00:00Z',
                'displayName': 'ESPN', 'region': 'US', 'sourceId': 'espn-broadcasts',
                'status': 'available',
            }],
            'fixtures': [], 'coverage': {}, 'sources': {},
        }, updated_at=updated_at)
        fixture = {
            'canonicalFixtureId': fixture_id,
            'utcDate': '2026-09-29T20:00:00Z',
            'homeTeam': {'name': 'Arsenal'}, 'awayTeam': {'name': 'Chelsea'},
            'competition': {'name': 'Premier League', 'canonicalId': 'eng.1'},
            'whereToWatch': [],
        }
        service = BroadcastRefreshService(
            store,
            lambda requested_date: {'state': 'success', 'matches': [fixture]},
            source_registry=app.extensions['broadcast_sources'],
            now=lambda: updated_at + timedelta(minutes=15),
        )

        service.refresh(date(2026, 9, 29))

        self.assertEqual(store.read()['observations'], [])
        self.assertEqual(store.read()['coverage']['confirmedNone'], 0)

    def test_competition_is_covered_only_at_90_percent_with_complete_region_evidence(self):
        app = create_app({'TESTING': True})
        sources = app.extensions['broadcast_sources'].sources()
        sources[0]['feed']['completeTerritoryCoverage'] = True
        sources[0]['feed']['completeTerritories'] = ['US']
        sources[0]['feed']['competitionId'] = 'eng.1'
        service = BroadcastRefreshService(
            app.extensions['broadcast_observation_store'],
            lambda requested_date: {'state': 'success', 'matches': []},
            source_registry=BroadcastSourceRegistry(sources),
        )
        fixtures = [
            {'fixtureKey': f'fx_{index:024x}', 'competitionId': 'eng.1', 'competition': 'Premier League'}
            for index in range(10)
        ]
        observations = [
            {'fixtureKey': fixture['fixtureKey'], 'competitionId': 'eng.1', 'region': 'US'}
            for fixture in fixtures[:9]
        ]

        report = service._rolling_coverage(fixtures, observations)

        self.assertEqual(report[0]['verifiedPercent'], 90)
        self.assertTrue(report[0]['sourceConfirmedComplete'])
        self.assertTrue(report[0]['covered'])
        report = service._rolling_coverage(fixtures, observations[:8])
        self.assertEqual(report[0]['verifiedPercent'], 80)
        self.assertFalse(report[0]['covered'])

    def test_fixture_api_exposes_regional_observation_status_additively(self):
        app = create_app({'TESTING': True})
        fixture = {
            'canonicalFixtureId': 'fx_' + ('a' * 24),
            'utcDate': '2026-09-29T20:00:00Z',
            'homeTeam': {'name': 'Arsenal'},
            'awayTeam': {'name': 'Chelsea'},
            'whereToWatch': [],
        }

        class FixtureService:
            def fixtures_for_date(self, requested_date, timezone_name):
                return {'state': 'success', 'date': str(requested_date), 'matches': [fixture]}

        app.extensions['fixture_service'] = FixtureService()
        app.extensions['broadcast_refresh_service'].now = lambda: datetime(
            2026, 9, 29, 16, tzinfo=timezone.utc
        )
        app.extensions['broadcast_observation_store'].write({
            'observations': [{
                'fixtureKey': fixture['canonicalFixtureId'],
                'fixtureDate': fixture['utcDate'],
                'displayName': 'ESPN',
                'type': 'STREAMING',
                'region': 'US',
                'officialUrl': 'https://www.espn.com/soccer/',
                'sourceId': 'espn-broadcasts',
                'source': 'espn',
                'observedAt': '2026-09-29T15:50:00Z',
                'status': 'available',
            }],
            'fixtures': [], 'coverage': {}, 'sources': {},
        }, updated_at=datetime(2026, 9, 29, 15, 50, tzinfo=timezone.utc))

        response = app.test_client().get('/api/v2/fixtures?date=2026-09-29')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['matches'][0]['whereToWatch'][0]['displayName'], 'ESPN')
        self.assertEqual(
            response.json['matches'][0]['broadcastCoverage']['regions'][0],
            {'region': 'US', 'status': 'available'},
        )
        self.assertEqual(response.json['broadcastCoverageReport']['thresholdPercent'], 90)

    def test_live_provider_listing_is_available_before_the_first_scheduled_refresh(self):
        app = create_app({'TESTING': True})
        fixture = {
            'canonicalFixtureId': 'fx_' + ('8' * 24),
            'whereToWatch': [{
                'id': 'espn', 'displayName': 'ESPN', 'type': 'STREAMING',
                'region': 'US', 'sourceId': 'espn-broadcasts',
                'officialUrl': 'https://www.espn.com/soccer/',
            }],
        }

        class FixtureService:
            def fixtures_for_date(self, requested_date, timezone_name):
                return {'state': 'success', 'date': str(requested_date), 'matches': [fixture]}

        app.extensions['fixture_service'] = FixtureService()
        response = app.test_client().get('/api/v2/fixtures?date=2026-09-29')

        self.assertEqual(response.json['matches'][0]['broadcastCoverage']['status'], 'available')
        self.assertEqual(
            response.json['matches'][0]['broadcastCoverage']['regions'],
            [{'region': 'US', 'status': 'available'}],
        )

    def test_fixture_without_a_source_confirmation_remains_unverified(self):
        app = create_app({'TESTING': True})
        fixture = {'canonicalFixtureId': 'fx_' + ('b' * 24), 'whereToWatch': []}

        class FixtureService:
            def fixtures_for_date(self, requested_date, timezone_name):
                return {'state': 'success', 'date': str(requested_date), 'matches': [fixture]}

        app.extensions['fixture_service'] = FixtureService()
        response = app.test_client().get('/api/v2/fixtures?date=2026-09-29')

        self.assertEqual(response.json['matches'][0]['broadcastCoverage']['status'], 'unverified')

    def test_fixture_only_reports_confirmed_none_when_source_certifies_competition_and_region(self):
        app = create_app({'TESTING': True})
        fixture = {'canonicalFixtureId': 'fx_' + ('f' * 24), 'whereToWatch': []}

        class FixtureService:
            def fixtures_for_date(self, requested_date, timezone_name):
                return {'state': 'success', 'date': str(requested_date), 'matches': [fixture]}

        app.extensions['fixture_service'] = FixtureService()
        app.extensions['broadcast_refresh_service'].now = lambda: datetime(
            2026, 9, 29, 16, tzinfo=timezone.utc
        )
        source = app.extensions['broadcast_sources'].sources()[0]
        source['feed'].update({
            'completeTerritoryCoverage': True,
            'competitionId': 'eng.1',
            'completeTerritories': ['US'],
        })
        app.extensions['broadcast_refresh_service'].source_registry = BroadcastSourceRegistry([source])
        fixture['competition'] = {'canonicalId': 'eng.1', 'name': 'Premier League'}
        app.extensions['broadcast_observation_store'].write({
            'observations': [{
                'fixtureKey': fixture['canonicalFixtureId'],
                'displayName': '', 'region': 'US', 'sourceId': 'espn-broadcasts',
                'competitionId': 'eng.1',
                'status': 'confirmed_none',
            }],
            'fixtures': [], 'coverage': {}, 'sources': {}, 'refreshStatus': 'success',
        }, updated_at=datetime(2026, 9, 29, 15, 59, tzinfo=timezone.utc))

        response = app.test_client().get('/api/v2/fixtures?date=2026-09-29')

        self.assertEqual(
            response.json['matches'][0]['broadcastCoverage']['regions'],
            [{'region': 'US', 'status': 'confirmed_none'}],
        )
        self.assertEqual(response.json['matches'][0]['broadcastCoverage']['status'], 'confirmed_none')

    def test_fixture_does_not_report_confirmed_none_from_ineligible_source(self):
        app = create_app({'TESTING': True})
        fixture = {'canonicalFixtureId': 'fx_' + ('1' * 24), 'whereToWatch': []}

        class FixtureService:
            def fixtures_for_date(self, requested_date, timezone_name):
                return {'state': 'success', 'date': str(requested_date), 'matches': [fixture]}

        app.extensions['fixture_service'] = FixtureService()
        app.extensions['broadcast_refresh_service'].now = lambda: datetime(
            2026, 9, 29, 16, tzinfo=timezone.utc
        )
        app.extensions['broadcast_observation_store'].write({
            'observations': [{
                'fixtureKey': fixture['canonicalFixtureId'],
                'displayName': '', 'region': 'US', 'sourceId': 'espn-broadcasts',
                'competitionId': 'eng.1', 'status': 'confirmed_none',
            }],
            'fixtures': [], 'coverage': {}, 'sources': {}, 'refreshStatus': 'success',
        }, updated_at=datetime(2026, 9, 29, 15, 59, tzinfo=timezone.utc))

        response = app.test_client().get('/api/v2/fixtures?date=2026-09-29')

        self.assertEqual(response.json['matches'][0]['broadcastCoverage']['status'], 'unverified')

    def test_source_storage_failure_does_not_fail_the_fixture_api(self):
        app = create_app({'TESTING': True})
        fixture = {
            'canonicalFixtureId': 'fx_' + ('e' * 24),
            'whereToWatch': [{
                'id': 'espn', 'displayName': 'ESPN', 'type': 'STREAMING',
                'region': 'US', 'sourceId': 'espn-broadcasts',
                'officialUrl': 'https://www.espn.com/soccer/',
            }],
        }

        class FixtureService:
            def fixtures_for_date(self, requested_date, timezone_name):
                return {'state': 'success', 'date': str(requested_date), 'matches': [fixture]}

        app.extensions['fixture_service'] = FixtureService()
        app.extensions['broadcast_observation_store'].read = lambda: (_ for _ in ()).throw(
            RuntimeError('Redis unavailable')
        )

        response = app.test_client().get('/api/v2/fixtures?date=2026-09-29')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['matches'][0]['broadcastCoverage']['status'], 'available')

    def test_internal_refresh_requires_the_configured_operations_token(self):
        app = create_app({'TESTING': True, 'OPS_ADMIN_TOKEN': 'ops-secret'})
        response = app.test_client().post('/api/internal/broadcast-refresh')

        self.assertEqual(response.status_code, 401)

    def test_internal_refresh_accepts_only_the_bearer_token_without_echoing_it(self):
        app = create_app({'TESTING': True, 'OPS_ADMIN_TOKEN': 'ops-secret'})

        class RefreshService:
            def refresh(self, requested_date):
                return {'status': 'success', 'coverage': {'observed': 2}, 'updatedAt': '2026-09-29T16:00:00Z'}

        app.extensions['broadcast_refresh_service'] = RefreshService()
        response = app.test_client().post(
            '/api/internal/broadcast-refresh',
            headers={'Authorization': 'Bearer ops-secret'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'success')
        self.assertNotIn('ops-secret', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
