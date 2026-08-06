import unittest

from soccer_scanner import create_app


class CompetitionEnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})

    def test_the_registry_is_registered(self):
        self.assertIn('competition_registry', self.app.extensions)

    def test_a_known_competition_resolves_a_country(self):
        registry = self.app.extensions['competition_registry']

        self.assertEqual(
            registry.describe_area({'canonicalId': 'premier-league', 'name': 'Premier League'}),
            {'name': 'England'},
        )

    def test_an_unmapped_competition_gets_no_area(self):
        registry = self.app.extensions['competition_registry']

        self.assertIsNone(registry.describe_area({'name': 'UEFA Champions League'}))

    def test_the_registry_is_wired_into_the_fixture_service(self):
        self.assertIs(
            self.app.extensions['fixture_service'].competition_registry,
            self.app.extensions['competition_registry'],
        )


if __name__ == '__main__':
    unittest.main()
