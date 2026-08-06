"""Verified competition → country registry.

ESPN emits no country for a competition, so the country filter had nothing to
populate from and was permanently empty. This resolves a country only for
competitions we can verify; anything else stays unmapped rather than guessed,
and multi-country competitions are deliberately excluded because forcing them
into one country would be wrong.
"""

import json
from pathlib import Path


class CompetitionRegistry:
    def __init__(self, competitions):
        self._by_id = {}
        self._by_alias = {}
        for entry in competitions:
            self._by_id[entry['canonicalId']] = entry['country']
            for alias in entry.get('aliases', []):
                self._by_alias[self._normalize(alias)] = entry['country']

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('competitions', []))

    @staticmethod
    def _normalize(value):
        return ' '.join(str(value or '').strip().lower().split())

    def country_for(self, canonical_id, name):
        # A canonical ID is authoritative; a display name is a fallback.
        if canonical_id and canonical_id in self._by_id:
            return self._by_id[canonical_id]
        return self._by_alias.get(self._normalize(name))

    def describe_area(self, competition):
        if not isinstance(competition, dict):
            return None
        country = self.country_for(
            competition.get('canonicalId'),
            competition.get('name'),
        )
        return {'name': country} if country else None
