"""Standings season configuration.

The season and provider identifiers used to be hardcoded in the template, so a
season rollover silently served a dead table with no signal. They now live in
configuration carrying a verification date, and `is_stale` gives a test
something to fail on.
"""

from datetime import date, timedelta
import json
from pathlib import Path
from urllib.parse import quote


class StandingsSeasons:
    # A malformed or missing key here raises immediately (KeyError/ValueError
    # from `date.fromisoformat`), the same fail-fast-at-startup behaviour as
    # StreamingRegistry and CompetitionRegistry: a broken registry should
    # never load silently and only fail later when something looks it up.
    def __init__(self, payload):
        self.version = int(payload['version'])
        self.last_verified = date.fromisoformat(payload['lastVerified'])
        self.verified_by = payload.get('verifiedBy', 'unknown')
        self.stale_after_days = int(payload.get('staleAfterDays', 400))
        self.competitions = [
            {**entry, 'embedUrl': self._embed_url(entry)}
            for entry in payload.get('competitions', [])
        ]

    @classmethod
    def from_file(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

    @staticmethod
    def _embed_url(entry):
        title = f"{entry['name']} {entry['season']}"
        # safe='' is required: the season contains a literal '/' (e.g.
        # "2025/26"), and quote()'s default safe='/' would leave it
        # unescaped, splitting the title across an extra URL path segment.
        encoded_title = quote(title, safe='')
        return (
            'https://widgets.sofascore.com/embed/tournament/'
            f"{entry['tournamentId']}/season/{entry['seasonId']}/standings/"
            f'{encoded_title}?widgetTitle={encoded_title}&showCompetitionLogo=true'
        )

    def is_stale(self, today=None):
        today = today or date.today()
        return today > self.last_verified + timedelta(days=self.stale_after_days)
