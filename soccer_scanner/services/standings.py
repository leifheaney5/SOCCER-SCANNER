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
    SEASON_TYPES = {'split-year', 'calendar-year', 'tournament', 'manual'}
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
            {
                **entry,
                'verifiedAt': entry.get('verifiedAt', payload['lastVerified']),
                'reviewBy': entry.get('reviewBy'),
                'seasonType': entry.get('seasonType', 'manual'),
                'embedUrl': self._embed_url(entry),
            }
            for entry in payload.get('competitions', [])
        ]
        for entry in self.competitions:
            if entry['seasonType'] not in self.SEASON_TYPES:
                raise ValueError(f"Unsupported standings season type: {entry['seasonType']}")

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

    @staticmethod
    def expected_season(entry, today=None):
        """Return the deterministic expected season, or None for manual editions."""
        today = today or date.today()
        season_type = entry.get('seasonType', 'manual')
        if season_type == 'split-year':
            first_year = today.year if today.month >= 7 else today.year - 1
            return f'{first_year}/{str(first_year + 1)[-2:]}'
        if season_type == 'calendar-year':
            return str(today.year)
        return None

    def review_status(self, entry, today=None):
        today = today or date.today()
        statuses = []
        if not entry.get('season') or not entry.get('seasonType'):
            statuses.append('missing_season_configuration')
        if not entry.get('verifiedAt') or not entry.get('reviewBy'):
            statuses.append('missing_verification_metadata')
        else:
            review_by = date.fromisoformat(entry['reviewBy'])
            if today > review_by:
                statuses.append('review_due')
        expected = self.expected_season(entry, today)
        if expected is not None and entry.get('season') != expected:
            statuses.append('season_mismatch')
        return tuple(statuses)

    def review_warnings(self, today=None):
        warnings = []
        for entry in self.competitions:
            statuses = self.review_status(entry, today)
            if statuses:
                warnings.append({
                    'name': entry.get('name', 'Competition'),
                    'season': entry.get('season') or 'not configured',
                    'statuses': statuses,
                })
        return warnings
