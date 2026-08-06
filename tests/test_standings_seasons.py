from datetime import date, timedelta
import json
from pathlib import Path
import unittest
from urllib.parse import unquote, urlparse

from soccer_scanner import create_app
from soccer_scanner.services.standings import StandingsSeasons

CONFIG_PATH = Path('soccer_scanner/data/standings-seasons.json')


class StandingsSeasonsTest(unittest.TestCase):
    def setUp(self):
        self.seasons = StandingsSeasons.from_file(CONFIG_PATH)

    def test_every_competition_declares_a_verified_season(self):
        for entry in self.seasons.competitions:
            with self.subTest(entry=entry['canonicalId']):
                self.assertTrue(entry['season'].strip())
                self.assertTrue(entry['tournamentId'])
                self.assertTrue(entry['seasonId'])

    def test_embed_urls_are_https_and_on_the_declared_provider(self):
        for entry in self.seasons.competitions:
            with self.subTest(entry=entry['canonicalId']):
                parsed = urlparse(entry['embedUrl'])
                self.assertEqual(parsed.scheme, 'https')
                self.assertTrue(parsed.netloc.endswith('sofascore.com'))

    def test_embed_url_title_is_a_single_path_segment(self):
        # The season contains a literal '/' (e.g. "2025/26"). If it is not
        # percent-encoded as %2F, it splits the title across an extra URL
        # path segment instead of staying inside the standings/<title>
        # segment — a regression that broke every one of the six URLs.
        premier_league = next(
            entry for entry in self.seasons.competitions
            if entry['canonicalId'] == 'premier-league'
        )
        self.assertEqual(
            premier_league['embedUrl'],
            'https://widgets.sofascore.com/embed/tournament/1/season/76986/'
            'standings/Premier%20League%202025%2F26'
            '?widgetTitle=Premier%20League%202025%2F26&showCompetitionLogo=true',
        )
        for entry in self.seasons.competitions:
            with self.subTest(entry=entry['canonicalId']):
                parsed = urlparse(entry['embedUrl'])
                segments = parsed.path.split('/')
                title_segment = segments[segments.index('standings') + 1]
                self.assertEqual(
                    unquote(title_segment),
                    f"{entry['name']} {entry['season']}",
                )

    def test_configuration_is_not_stale_today(self):
        # This is the point of the task: it must FAIL once the recorded
        # verification ages out, rather than silently serving a dead season.
        self.assertFalse(
            self.seasons.is_stale(date.today()),
            'standings season configuration is stale — re-verify the season IDs '
            'and update lastVerified in soccer_scanner/data/standings-seasons.json',
        )

    def test_staleness_triggers_after_the_configured_window(self):
        payload = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        verified = date.fromisoformat(payload['lastVerified'])
        window = int(payload['staleAfterDays'])

        self.assertFalse(self.seasons.is_stale(verified + timedelta(days=window - 1)))
        self.assertTrue(self.seasons.is_stale(verified + timedelta(days=window + 1)))

    def test_the_page_renders_from_configuration_not_hardcoded_markup(self):
        app = create_app({'TESTING': True})

        html = app.test_client().get('/league-tables').get_data(as_text=True)

        for entry in self.seasons.competitions:
            self.assertIn(entry['name'], html)
        # The season label must come from configuration, so changing it there
        # changes the page.
        self.assertIn(self.seasons.competitions[0]['season'], html)


if __name__ == '__main__':
    unittest.main()
