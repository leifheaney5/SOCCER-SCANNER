"""Verified streaming-service registry.

Providers report free-text service names. This maps them onto a small set of
verified services with official URLs, so the UI can link somewhere real instead
of rendering an unlinked string — and so an unrecognised name degrades to plain
text rather than a guessed link.
"""

import json
from pathlib import Path

REGION_UNKNOWN = 'Region unknown'


class StreamingRegistry:
    def __init__(self, services):
        self._services = {}
        self._by_alias = {}
        for service in services:
            self._services[service['id']] = service
            for alias in [service['displayName'], *service.get('aliases', [])]:
                self._by_alias[self._normalize(alias)] = service['id']

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('services', []))

    @staticmethod
    def _normalize(value):
        return ' '.join(str(value or '').strip().lower().split())

    def resolve(self, name):
        service_id = self._by_alias.get(self._normalize(name))
        if service_id is None:
            return None
        service = self._services[service_id]
        return {
            'id': service['id'],
            'displayName': service['displayName'],
            'officialUrl': service['officialUrl'],
            'domains': list(service['domains']),
            'requiresAttribution': bool(service.get('requiresAttribution')),
        }

    def describe(self, broadcast):
        """Render-ready description, or None if this is not a streaming entry."""
        if not isinstance(broadcast, dict):
            return None
        if str(broadcast.get('type') or '').upper() != 'STREAMING':
            return None
        raw_name = str(broadcast.get('name') or '').strip()
        if not raw_name:
            return None

        service = self.resolve(raw_name)
        region = str(broadcast.get('region') or '').strip()
        return {
            'id': service['id'] if service else None,
            'displayName': service['displayName'] if service else raw_name,
            'officialUrl': service['officialUrl'] if service else None,
            'region': region or REGION_UNKNOWN,
            'regionKnown': bool(region),
            'source': 'espn',
        }
