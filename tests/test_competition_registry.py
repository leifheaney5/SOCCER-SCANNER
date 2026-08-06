import json
from pathlib import Path
import unittest

from soccer_scanner.services.competitions import CompetitionRegistry

REGISTRY_PATH = Path('soccer_scanner/data/competition-countries.json')
REAL_COMPETITION_NAMES_PATH = Path('tests/fixtures/providers/real-competition-names.json')

# Expected outcome for every distinct competition name observed in a real
# production payload (tests/fixtures/providers/real-competition-names.json).
# This is the regression test for the defect where the registry resolved 0 of
# 64 real fixtures: ESPN emits `canonicalId: null` for nearly every
# competition and names them with a nationality-adjective prefix instead.
REAL_COMPETITION_EXPECTATIONS = {
    'Argentine Liga Profesional de Fútbol': 'Argentina',
    'Bolivian Liga Profesional': 'Bolivia',
    'Club Friendly': None,
    'Copa do Brasil': None,
    'English Carabao Cup': 'England',
    'Leagues Cup': None,
    'Mexican Liga de Expansión MX': 'Mexico',
    'Peruvian Liga 1': 'Peru',
    'UEFA Conference League Qualifying': None,
    'UEFA Europa League Qualifying': None,
    'Venezuelan Primera División': 'Venezuela',
    "Women's Africa Cup of Nations": None,
}


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

    def test_resolves_every_distinct_competition_in_a_real_production_payload(self):
        # This is the test that would have caught the original defect: the
        # registry resolved 0 of 64 real fixtures because ESPN emits
        # `canonicalId: null` for nearly every competition and names them
        # with a nationality-adjective prefix rather than a bare alias.
        payload = json.loads(REAL_COMPETITION_NAMES_PATH.read_text(encoding='utf-8'))

        seen = {}
        for match in payload['matches']:
            competition = match['competition']
            seen[competition['name']] = competition.get('canonicalId')

        self.assertEqual(set(seen), set(REAL_COMPETITION_EXPECTATIONS))

        for name, canonical_id in seen.items():
            with self.subTest(name=name):
                self.assertEqual(
                    self.registry.country_for(canonical_id, name),
                    REAL_COMPETITION_EXPECTATIONS[name],
                )


if __name__ == '__main__':
    unittest.main()
