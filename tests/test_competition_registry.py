import json
from pathlib import Path
import unittest

from soccer_scanner.services.competitions import CompetitionRegistry

REGISTRY_PATH = Path('soccer_scanner/data/competition-countries.json')


class CompetitionRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = CompetitionRegistry.from_file(REGISTRY_PATH)

    def test_resolves_by_canonical_id(self):
        self.assertEqual(self.registry.country_for('premier-league', None), 'England')

    def test_resolves_by_name_case_insensitively(self):
        for raw in ('Premier League', '  premier league  ', 'EPL'):
            with self.subTest(raw=raw):
                self.assertEqual(self.registry.country_for(None, raw), 'England')

    def test_canonical_id_wins_over_a_conflicting_name(self):
        self.assertEqual(self.registry.country_for('la-liga', 'Premier League'), 'Spain')

    def test_an_unmapped_competition_returns_none(self):
        self.assertIsNone(self.registry.country_for('uefa-champions-league', 'UEFA Champions League'))
        self.assertIsNone(self.registry.country_for(None, None))
        self.assertIsNone(self.registry.country_for(None, ''))

    def test_describe_area_shapes_the_client_contract(self):
        area = self.registry.describe_area({'canonicalId': 'serie-a', 'name': 'Serie A'})

        self.assertEqual(area, {'name': 'Italy'})

    def test_describe_area_returns_none_when_unknown(self):
        # An absent area is honest; a guessed one is not.
        self.assertIsNone(self.registry.describe_area({'name': 'UEFA Champions League'}))
        self.assertIsNone(self.registry.describe_area({}))
        self.assertIsNone(self.registry.describe_area(None))

    def test_multi_country_competitions_blocklist(self):
        # Multi-country competitions are deliberately absent from the registry.
        # See the 'note' field in competition-countries.json for why each is excluded.
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        mapped = {entry['canonicalId'] for entry in payload['competitions']}

        # Continental competitions with no single country
        for forbidden in ('uefa-champions-league', 'uefa-europa-league', 'copa-libertadores'):
            self.assertNotIn(forbidden, mapped)

        # Domestic leagues with cross-border teams
        self.assertNotIn('mls', mapped)  # Includes Canadian franchises (Toronto, Montréal, Vancouver)

        # Other known multi-country competitions
        for forbidden in ('uefa-conference-league', 'concacaf-champions-league'):
            self.assertNotIn(forbidden, mapped)

    def test_ids_and_aliases_are_unique(self):
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        ids = [entry['canonicalId'] for entry in payload['competitions']]
        self.assertEqual(len(ids), len(set(ids)))

        seen = set()
        for entry in payload['competitions']:
            for alias in entry['aliases']:
                normalized = alias.lower()
                self.assertNotIn(normalized, seen, f'duplicate alias: {alias}')
                seen.add(normalized)

    def test_every_entry_declares_a_non_empty_country(self):
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        for entry in payload['competitions']:
            with self.subTest(entry=entry['canonicalId']):
                self.assertTrue(entry['country'].strip())


if __name__ == '__main__':
    unittest.main()
