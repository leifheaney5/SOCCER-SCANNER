import json
import os
import unittest
from unittest.mock import patch

from soccer_scanner import create_app


class TermsRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app({'TESTING': True}).test_client()

    def test_terms_route_is_served(self):
        response = self.client.get('/terms')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Terms of Service', response.data)

    def test_terms_covers_the_required_sections(self):
        html = self.client.get('/terms').get_data(as_text=True)

        for heading in (
            'Service description',
            'Third-party data',
            'Accuracy limitations',
            'Streaming limitations',
            'External links',
            'Permitted use',
            'Rate limits',
            'Intellectual property',
            'Third-party trademarks',
            'Accounts',
            'Warranty disclaimer',
            'Limitation of liability',
            'Changes to these terms',
            'Effective date',
        ):
            self.assertIn(heading, html, heading)

    def test_terms_does_not_invent_a_legal_entity_or_jurisdiction(self):
        html = self.client.get('/terms').get_data(as_text=True)

        # A placeholder must be visible so legal review is not skipped.
        self.assertIn('LEGAL REVIEW REQUIRED', html)
        for invented in ('Inc.', 'LLC', 'Ltd.', 'GmbH'):
            self.assertNotIn(invented, html, invented)

    def test_terms_carries_a_noindex_robots_tag(self):
        # The page is a labelled engineering draft and must not be advertised
        # to crawlers, but it still needs to be reachable by visitors.
        response = self.client.get('/terms')
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="robots" content="noindex, follow"', html)

    def test_footer_links_terms_privacy_and_data_sources(self):
        html = self.client.get('/').get_data(as_text=True)

        self.assertIn('href="/terms"', html)
        self.assertIn('href="/privacy"', html)
        self.assertIn('href="/data-sources"', html)


class RobotsAndSitemapTest(unittest.TestCase):
    def setUp(self):
        # Only production advertises itself to crawlers.
        with patch.dict(os.environ, {
            'APP_ENVIRONMENT': 'production',
            'GIT_COMMIT_SHA': '0123456789abcdef0123456789abcdef01234567',
        }, clear=False):
            self.app = create_app({
                'TESTING': True,
                'PUBLIC_BASE_URL': 'https://soccerscanner.pro',
            })
        self.client = self.app.test_client()

    def test_robots_is_plain_text_and_points_at_the_sitemap(self):
        response = self.client.get('/robots.txt')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.mimetype.startswith('text/plain'))
        self.assertIn('User-agent: *', body)
        self.assertIn('Sitemap: https://soccerscanner.pro/sitemap.xml', body)

    def test_robots_keeps_operational_surfaces_out_of_the_index(self):
        body = self.client.get('/robots.txt').get_data(as_text=True)

        self.assertIn('Disallow: /health/', body)
        self.assertIn('Disallow: /api/', body)

    def test_non_production_environments_refuse_indexing(self):
        # Staging must not compete with production for the same content.
        with patch.dict(os.environ, {'APP_ENVIRONMENT': 'staging'}, clear=False):
            staging = create_app({'TESTING': True})
        body = staging.test_client().get('/robots.txt').get_data(as_text=True)

        self.assertIn('Disallow: /', body)
        self.assertNotIn('Allow: /', body)
        self.assertNotIn('Sitemap:', body)

    def test_sitemap_is_valid_xml_with_absolute_canonical_urls(self):
        response = self.client.get('/sitemap.xml')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response.mimetype)
        self.assertIn('<urlset', body)
        self.assertIn('<loc>https://soccerscanner.pro/</loc>', body)
        self.assertIn('<loc>https://soccerscanner.pro/privacy</loc>', body)
        # /terms is a labelled draft (noindex) and must never be advertised
        # to crawlers via the sitemap, though the route itself stays live.
        self.assertNotIn('<loc>https://soccerscanner.pro/terms</loc>', body)
        # Never advertise non-indexable surfaces.
        self.assertNotIn('/api/', body)
        self.assertNotIn('/health/', body)


class AppleAppSiteAssociationTest(unittest.TestCase):
    def test_aasa_is_absent_until_apple_identifiers_are_configured(self):
        app = create_app({'TESTING': True, 'APPLE_TEAM_ID': None, 'APPLE_BUNDLE_ID': None})

        response = app.test_client().get('/.well-known/apple-app-site-association')

        # Publishing invented identifiers would be worse than publishing none.
        self.assertEqual(response.status_code, 404)

    def test_aasa_is_served_without_redirect_as_json_when_configured(self):
        app = create_app({
            'TESTING': True,
            'APPLE_TEAM_ID': 'ABCDE12345',
            'APPLE_BUNDLE_ID': 'pro.soccerscanner.app',
        })

        response = app.test_client().get('/.well-known/apple-app-site-association')
        payload = json.loads(response.get_data(as_text=True))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/json')
        details = payload['applinks']['details'][0]
        self.assertEqual(details['appIDs'], ['ABCDE12345.pro.soccerscanner.app'])
        paths = details['components']
        self.assertTrue(any(component.get('/') == '/fixtures/*' for component in paths))
        self.assertTrue(any(component.get('/') == '/teams/*' for component in paths))
        self.assertTrue(any(component.get('/') == '/competitions/*' for component in paths))
        self.assertTrue(any(component.get('/') == '/calendar' for component in paths))


class AppConfigTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app({'TESTING': True}).test_client()

    def test_app_config_exposes_only_non_sensitive_client_settings(self):
        response = self.client.get('/api/v2/app-config')
        payload = response.json

        self.assertEqual(response.status_code, 200)
        self.assertIn('minimumSupportedClient', payload)
        self.assertIn('features', payload)
        self.assertIn('apiVersion', payload)
        self.assertIn('publicBaseUrl', payload)

        serialized = json.dumps(payload).lower()
        for secret in ('database_url', 'redis_url', 'ops_admin_token', 'api_key', 'password'):
            self.assertNotIn(secret, serialized, secret)

    def test_app_config_reports_feature_flags_as_booleans(self):
        payload = self.client.get('/api/v2/app-config').json

        self.assertGreater(len(payload['features']), 0)
        for name, enabled in payload['features'].items():
            self.assertIsInstance(enabled, bool, name)

    def test_app_config_states_that_accounts_are_unavailable(self):
        payload = self.client.get('/api/v2/app-config').json

        # Guest mode is the current product decision; clients must not offer
        # sign-in affordances that the backend cannot honour.
        self.assertFalse(payload['features']['accounts'])
        self.assertFalse(payload['features']['favorites'])


if __name__ == '__main__':
    unittest.main()
