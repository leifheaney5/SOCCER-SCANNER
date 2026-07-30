import unittest
from unittest.mock import Mock, patch

from app import app


class SoccerScannerRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_fixture_dashboard_is_home_page(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1 id="page-title">Fixtures</h1>', response.data)
        self.assertIn(b'id="fixture-search"', response.data)
        self.assertIn(b'id="status-filter"', response.data)
        self.assertIn(b'id="fixture-dialog"', response.data)

    def test_team_analysis_has_a_stable_route(self):
        response = self.client.get('/teams')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1>Team Analysis</h1>', response.data)

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

        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json['status'], 'ready')
        self.assertEqual(live.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("default-src 'self'", live.headers['Content-Security-Policy'])
        self.assertIn("script-src 'self'", live.headers['Content-Security-Policy'])
        self.assertNotIn("script-src 'self' 'unsafe-inline'", live.headers['Content-Security-Policy'])

    def test_pages_use_shared_layout_and_external_assets(self):
        fixtures = self.client.get('/').get_data(as_text=True)
        teams = self.client.get('/teams').get_data(as_text=True)
        standings = self.client.get('/league-tables').get_data(as_text=True)

        for page in (fixtures, teams, standings):
            self.assertIn('href="#main-content"', page)
            self.assertIn('/static/css/base.css', page)
            self.assertNotIn('<style>', page)
        self.assertIn('/static/js/fixtures.js', fixtures)
        self.assertIn('/static/js/teams.js', teams)

        static_asset = self.client.get('/static/css/base.css')
        self.assertEqual(static_asset.status_code, 200)
        self.assertIn('max-age=3600', static_asset.headers['Cache-Control'])
        static_asset.close()

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
