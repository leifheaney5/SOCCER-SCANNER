import unittest
import os
from datetime import date
from unittest.mock import Mock, patch

from app import app
from soccer_scanner import create_app


class SoccerScannerRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.app = app
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
        self.assertIn('>Teams</a>', html)
        self.assertIn('>Calendar</a>', html)
        self.assertIn('>Favorites</a>', html)

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

    def test_calendar_workspace_is_available(self):
        response = self.client.get('/calendar')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="calendar-results"', response.data)
        self.assertIn(b'/static/js/calendar.js', response.data)

    def test_canonical_fixture_lookup_deep_link_and_ics_are_spoiler_free(self):
        fixture_id = 'fx_' + ('a' * 24)
        match = {
            'canonicalFixtureId': fixture_id,
            'utcDate': '2026-08-03T19:00:00Z',
            'localDate': '2026-08-03',
            'homeTeam': {'name': 'Arsenal'},
            'awayTeam': {'name': 'Chelsea'},
            'competition': {'name': 'Premier League'},
            'venue': 'Scanner Stadium',
            'score': {'fullTime': {'home': 97, 'away': 96}},
        }
        service = Mock()
        service.lookup_fixture.return_value = match
        original = self.app.extensions['fixture_service']
        self.app.extensions['fixture_service'] = service
        try:
            api_response = self.client.get(f'/api/v2/fixtures/{fixture_id}')
            deep_link = self.client.get(f'/fixtures/{fixture_id}')
            calendar = self.client.get(f'/fixtures/{fixture_id}.ics')
        finally:
            self.app.extensions['fixture_service'] = original

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json['fixture']['canonicalFixtureId'], fixture_id)
        self.assertEqual(deep_link.status_code, 302)
        self.assertIn(f'fixture={fixture_id}', deep_link.headers['Location'])
        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(calendar.mimetype, 'text/calendar')
        self.assertIn('SUMMARY:Arsenal vs Chelsea', calendar.get_data(as_text=True))
        self.assertIn('LOCATION:Scanner Stadium', calendar.get_data(as_text=True))
        self.assertNotIn('97', calendar.get_data(as_text=True))
        self.assertNotIn('96', calendar.get_data(as_text=True))

    def test_team_and_competition_deep_pages_have_stable_routes(self):
        team = self.client.get('/teams/arsenal')
        competition = self.client.get('/competitions/premier-league')
        unknown_team = self.client.get('/teams/not-mapped')

        self.assertEqual(team.status_code, 200)
        self.assertIn(b'data-team-id="arsenal"', team.data)
        self.assertEqual(competition.status_code, 200)
        self.assertIn(b'Premier League', competition.data)
        self.assertEqual(unknown_team.status_code, 404)

    def test_fixture_api_rejects_an_invalid_date(self):
        response = self.client.get('/api/matches-today?date=tomorrow')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['code'], 'invalid_date')

    def test_fixture_api_rejects_an_invalid_timezone(self):
        response = self.client.get('/api/matches-today?timezone=Mars/Olympus')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['code'], 'invalid_timezone')

    def test_v2_rejects_unknown_parameters_with_stable_error_envelope(self):
        response = self.client.get('/api/v2/fixtures?date=2026-08-03&tracking=unbounded')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error']['code'], 'invalid_request')
        self.assertFalse(response.json['error']['retryable'])
        self.assertEqual(response.json['error']['requestId'], response.headers['X-Request-ID'])

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
        self.assertIn('cache', ready.json)
        self.assertIn('backend', ready.json['cache'])
        self.assertIn('shared', ready.json['cache'])
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
        self.assertIn("frame-ancestors 'self'", live.headers['Content-Security-Policy'])
        self.assertNotIn('Access-Control-Allow-Origin', live.headers)

    def test_api_responses_are_not_stored_and_html_has_canonical_metadata(self):
        api_response = self.client.get('/api/v2/fixtures?date=invalid')
        page = self.client.get('/')
        html = page.get_data(as_text=True)

        self.assertEqual(api_response.headers['Cache-Control'], 'no-store')
        self.assertIn('<link rel="canonical" href="https://soccerscanner.pro/">', html)
        self.assertIn('property="og:title"', html)
        self.assertIn('name="twitter:card"', html)
        self.assertIn('/static/manifest.webmanifest', html)
        self.assertNotIn('score', html.lower().split('property="og:description"', 1)[-1].split('>', 1)[0])

    def test_trusted_https_proxy_enables_production_hsts(self):
        environment = {
            'APP_ENVIRONMENT': 'production',
            'GIT_COMMIT_SHA': '0123456789abcdef0123456789abcdef01234567',
        }
        with patch.dict(os.environ, environment, clear=False):
            production_app = create_app({
                'TESTING': False,
                'TRUSTED_PROXY_HOPS': 1,
                'REDIS_URL': None,
            })
            response = production_app.test_client().get(
                '/health/live',
                headers={'X-Forwarded-Proto': 'https'},
            )

        self.assertIn('max-age=31536000', response.headers['Strict-Transport-Security'])

    def test_privacy_data_sources_and_error_pages_are_useful(self):
        privacy = self.client.get('/privacy')
        sources = self.client.get('/data-sources')
        missing = self.client.get('/not-a-real-page')
        missing_api = self.client.get('/api/not-a-real-route')

        self.assertEqual(privacy.status_code, 200)
        self.assertIn(b'Privacy', privacy.data)
        self.assertIn(b'localStorage', privacy.data)
        self.assertEqual(sources.status_code, 200)
        self.assertIn(b'ESPN', sources.data)
        self.assertIn(b'Football-data.org', sources.data)
        self.assertEqual(missing.status_code, 404)
        self.assertIn(b'Page not found', missing.data)
        self.assertEqual(missing_api.status_code, 404)
        self.assertEqual(missing_api.json['error']['code'], 'not_found')

    def test_offline_shell_and_service_worker_scope_are_available(self):
        home = self.client.get('/')
        offline = self.client.get('/offline')
        worker = self.client.get('/static/sw.js')

        self.assertEqual(offline.status_code, 200)
        self.assertIn(b'You are offline', offline.data)
        self.assertIn(b'/static/js/pwa.js', home.data)
        self.assertEqual(worker.headers['Service-Worker-Allowed'], '/')

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

    def test_production_readiness_reports_missing_shared_cache_as_degraded(self):
        environment = {
            'APP_ENVIRONMENT': 'production',
            'GIT_COMMIT_SHA': '0123456789abcdef0123456789abcdef01234567',
        }
        with patch.dict(os.environ, environment, clear=False):
            production_app = create_app({'TESTING': False, 'REDIS_URL': None})
            ready = production_app.test_client().get('/health/ready')

        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json['status'], 'ready')
        self.assertEqual(ready.json['cache'], {
            'backend': 'memory',
            'shared': False,
            'status': 'degraded',
        })

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

    def test_fixture_api_alias_queries_the_canonical_service(self):
        service = Mock()
        service.fixtures_for_date.return_value = {
            'state': 'empty_confirmed',
            'date': '2026-08-14',
            'timezone': 'UTC',
            'matches': [],
        }
        self.app.extensions['fixture_service'] = service

        response = self.client.get('/api/matches-today?date=2026-08-14')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['date'], '2026-08-14')
        service.fixtures_for_date.assert_called_once_with(date(2026, 8, 14), 'UTC')

    def test_v2_provider_outage_has_stable_typed_error(self):
        from soccer_scanner.domain.models import FixtureState, FixtureUnavailable

        service = Mock()
        service.fixtures_for_date.side_effect = FixtureUnavailable(
            FixtureState.PROVIDER_UNAVAILABLE,
            'Fixture providers are temporarily unavailable.',
            retry_after_seconds=30,
        )
        self.app.extensions['fixture_service'] = service

        response = self.client.get('/api/v2/fixtures?date=2026-08-14')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error']['code'], 'provider_unavailable')
        self.assertTrue(response.json['error']['retryable'])
        self.assertEqual(response.json['error']['retryAfterSeconds'], 30)
        self.assertEqual(response.headers['Retry-After'], '30')

    @patch('soccer_scanner.services.teams.TeamAnalysisService.analyze')
    def test_canonical_team_analysis_translates_to_compatible_provider_id(self, analyze):
        analyze.return_value = {'team_info': {'name': 'Arsenal'}}

        response = self.client.get('/api/v2/teams/arsenal/analysis')

        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once_with('57')
        self.assertEqual(response.json['team_info']['canonicalId'], 'arsenal')
        self.assertEqual(response.json['team_info']['providerId'], '57')

    def test_canonical_team_analysis_rejects_raw_or_unknown_provider_id(self):
        response = self.client.get('/api/v2/teams/57/analysis')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error']['code'], 'team_identity_unavailable')


if __name__ == '__main__':
    unittest.main()
