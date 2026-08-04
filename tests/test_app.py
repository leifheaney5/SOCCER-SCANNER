import unittest
import os
from unittest.mock import Mock, patch

from app import app
from soccer_scanner import create_app


class SoccerScannerRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_fixture_dashboard_is_home_page(self):
        response = self.client.get('/')
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for element_id in (
            'dashboard-date', 'fixture-stream', 'team-drawer', 'score-toggle',
            'daily-summary', 'featured-match', 'match-context',
            'match-context-dialog', 'dashboard-status', 'data-notice',
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('aria-label="Primary navigation"', html)
        self.assertIn('aria-current="page"', html)
        self.assertIn('href="https://select-xi.pro/"', html)
        self.assertIn('aria-labelledby="team-drawer-title"', html)
        self.assertIn('aria-labelledby="match-context-dialog-title"', html)
        self.assertNotIn('class="suite-rail"', html)
        self.assertNotIn('>Teams</a>', html)

    def test_team_analysis_has_a_stable_route(self):
        response = self.client.get('/teams')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1>Team Analysis</h1>', response.data)

    def test_compatibility_routes_remain_available(self):
        fixtures = self.client.get('/matches-today')
        standings = self.client.get('/league-tables')

        self.assertEqual(fixtures.status_code, 200)
        self.assertIn(b'id="fixture-stream"', fixtures.data)
        self.assertEqual(standings.status_code, 200)
        self.assertIn(b'id="league-selector"', standings.data)

    def test_fixture_api_rejects_an_invalid_date(self):
        response = self.client.get('/api/matches-today?date=tomorrow')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['code'], 'invalid_date')

    def test_fixture_api_rejects_an_invalid_timezone(self):
        response = self.client.get('/api/matches-today?timezone=Mars/Olympus')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['code'], 'invalid_timezone')

    def test_health_endpoints_and_security_headers(self):
        live = self.client.get('/health/live')
        ready = self.client.get('/health/ready')
        version = self.client.get('/health/version')
        metrics = self.client.get('/health/metrics')

        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(version.status_code, 200)
        self.assertEqual(metrics.status_code, 200)
        self.assertIn('counters', metrics.json)
        self.assertIn('timings', metrics.json)
        self.assertEqual(ready.json['status'], 'ready')
        self.assertEqual(ready.json['build'], version.json)
        self.assertRegex(version.json['version'], r'^\d+\.\d+\.\d+$')
        self.assertIn('commitSha', version.json)
        self.assertIn('buildTimestamp', version.json)
        self.assertIn('environment', version.json)
        self.assertIn('assetVersion', version.json)
        self.assertEqual(live.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("default-src 'self'", live.headers['Content-Security-Policy'])
        self.assertIn("script-src 'self'", live.headers['Content-Security-Policy'])
        self.assertNotIn("script-src 'self' 'unsafe-inline'", live.headers['Content-Security-Policy'])
        self.assertNotIn("style-src 'self' 'unsafe-inline'", live.headers['Content-Security-Policy'])
        self.assertIn("object-src 'none'", live.headers['Content-Security-Policy'])

    def test_request_id_is_validated_and_echoed(self):
        accepted = self.client.get('/health/live', headers={'X-Request-ID': 'client-123'})
        generated = self.client.get('/health/live', headers={'X-Request-ID': 'not valid!'})

        self.assertEqual(accepted.headers['X-Request-ID'], 'client-123')
        self.assertRegex(
            generated.headers['X-Request-ID'],
            r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        )

    def test_provider_transport_configuration_is_bounded(self):
        self.assertGreaterEqual(app.config['PROVIDER_MAX_RETRIES'], 0)
        self.assertLessEqual(app.config['PROVIDER_MAX_RETRIES'], 3)
        self.assertLessEqual(app.config['PROVIDER_MAX_JSON_BYTES'], 2_000_000)
        self.assertLessEqual(app.config['PROVIDER_RETRY_AFTER_MAX'], 60)
        self.assertLessEqual(app.config['PROVIDER_POOL_CONNECTIONS'], 16)
        self.assertLessEqual(app.config['PROVIDER_POOL_MAXSIZE'], 32)

    def test_production_requires_a_valid_commit_sha(self):
        environment = {
            'APP_ENVIRONMENT': 'production',
            'RAILWAY_ENVIRONMENT_NAME': '',
            'GIT_COMMIT_SHA': '',
            'RAILWAY_GIT_COMMIT_SHA': '',
        }
        with patch.dict(os.environ, environment, clear=False):
            with self.assertRaisesRegex(RuntimeError, 'commit SHA'):
                create_app({'TESTING': False})

    def test_build_sha_versions_every_first_party_entry_asset(self):
        sha = '0123456789abcdef0123456789abcdef01234567'
        environment = {
            'APP_ENVIRONMENT': 'test',
            'GIT_COMMIT_SHA': sha,
            'APP_VERSION': '2.0.0',
            'BUILD_TIMESTAMP': '2026-08-03T20:00:00Z',
        }
        with patch.dict(os.environ, environment, clear=False):
            built_app = create_app({'TESTING': True})
            response = built_app.test_client().get('/')
            version = built_app.test_client().get('/health/version').json

        html = response.get_data(as_text=True)
        self.assertEqual(version, {
            'version': '2.0.0',
            'commitSha': sha,
            'buildTimestamp': '2026-08-03T20:00:00Z',
            'environment': 'test',
            'assetVersion': sha[:12],
        })
        self.assertIn(f'/static/css/base.css?v={sha[:12]}', html)
        self.assertIn(f'/static/css/fixtures.css?v={sha[:12]}', html)
        self.assertIn(f'/static/js/dom.js?v={sha[:12]}', html)
        self.assertIn(f'/static/js/fixtures.js?v={sha[:12]}', html)
        self.assertNotIn('20260803-dashboard-v1', html)

    def test_pages_use_shared_layout_and_external_assets(self):
        fixtures = self.client.get('/').get_data(as_text=True)
        teams = self.client.get('/teams').get_data(as_text=True)
        standings = self.client.get('/league-tables').get_data(as_text=True)

        for page in (fixtures, teams, standings):
            self.assertIn('href="#main-content"', page)
            self.assertIn('/static/css/base.css', page)
            self.assertIn('/static/favicon.svg', page)
            self.assertNotIn('<style>', page)
            self.assertNotIn(' style=', page)
            self.assertIn('/static/js/dom.js', page)
        self.assertIn('/static/js/fixtures.js', fixtures)
        self.assertIn('/static/js/teams.js', teams)
        self.assertIn('/static/js/standings.js', standings)
        self.assertEqual(standings.count('<iframe'), 1)
        self.assertIn('id="league-selector"', standings)

        static_asset = self.client.get('/static/css/base.css')
        self.assertEqual(static_asset.status_code, 200)
        self.assertIn('max-age=3600', static_asset.headers['Cache-Control'])
        static_asset.close()

        favicon = self.client.get('/static/favicon.svg')
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.mimetype, 'image/svg+xml')
        favicon.close()

    @patch('soccer_scanner.services.football_data.FootballDataClient.get')
    @patch('soccer_scanner.services.fixtures.requests.get')
    def test_fixture_api_queries_the_requested_date(self, get, football_data_get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'events': []}
        get.return_value.raise_for_status.return_value = None
        football_data_get.return_value = {'matches': []}

        response = self.client.get('/api/matches-today?date=2026-08-14')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['date'], '2026-08-14')
        self.assertEqual(get.call_count, 20)
        self.assertTrue(all(call.kwargs['params']['dates'] == '20260814' for call in get.call_args_list))


if __name__ == '__main__':
    unittest.main()
