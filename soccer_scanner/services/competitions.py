"""Verified competition → country registry.

ESPN emits no country for a competition, so the country filter had nothing to
populate from and was permanently empty. This resolves a country only for
competitions we can verify; anything else stays unmapped rather than guessed,
and multi-country competitions are deliberately excluded because forcing them
into one country would be wrong.

ESPN also emits `canonicalId: null` for nearly every competition and instead
names many of them with a nationality-adjective prefix (e.g. "Argentine Liga
Profesional de Futbol", "English Carabao Cup"). The adjective map is a last
resort after canonical-ID and alias lookups miss, and matches only a
word-boundary prefix -- the name must *start* with the adjective followed by
whitespace -- never a substring, to avoid resolving an adjective embedded
elsewhere in an unrelated name.
"""

import json
from pathlib import Path


class CompetitionRegistry:
    def __init__(self, competitions, adjectives=None):
        self._by_id = {}
        self._by_alias = {}
        for entry in competitions:
            self._by_id[entry['canonicalId']] = entry['country']
            for alias in entry.get('aliases', []):
                self._by_alias[self._normalize(alias)] = entry['country']

        self._adjectives = [
            (self._normalize(entry['prefix']), entry['country'])
            for entry in (adjectives or [])
        ]

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('competitions', []), payload.get('adjectives', []))

    @staticmethod
    def _normalize(value):
        return ' '.join(str(value or '').strip().lower().split())

    def country_for(self, canonical_id, name):
        # A canonical ID is authoritative; a display name is a fallback.
        if canonical_id and canonical_id in self._by_id:
            return self._by_id[canonical_id]

        normalized_name = self._normalize(name)
        if normalized_name in self._by_alias:
            return self._by_alias[normalized_name]

        for prefix, country in self._adjectives:
            if normalized_name.startswith(prefix + ' '):
                return country

        return None

    def describe_area(self, competition):
        if not isinstance(competition, dict):
            return None
        country = self.country_for(
            competition.get('canonicalId'),
            competition.get('name'),
        )
        return {'name': country} if country else None
