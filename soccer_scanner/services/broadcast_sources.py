"""Registry for free, official broadcast-listing sources."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path


KICKOFF_TOLERANCE_SECONDS = 15 * 60


@dataclass
class BroadcastObservation:
    observed: int = 0
    matched: int = 0
    verified_links: int = 0
    region_known: int = 0
    stale: int = 0
    unmatched: int = 0
    ambiguous: int = 0

    def as_dict(self):
        values = asdict(self)
        return {
            'observed': values['observed'],
            'matched': values['matched'],
            'verifiedLinks': values['verified_links'],
            'regionKnown': values['region_known'],
            'stale': values['stale'],
            'unmatched': values['unmatched'],
            'ambiguous': values['ambiguous'],
        }


def _text(value):
    result = str(value or '').strip().casefold()
    return result or None


def _instant(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def match_source_listing(listing, match):
    """Return true only for a strong, fixture-level listing match."""
    if not isinstance(listing, dict) or not isinstance(match, dict):
        return False
    home = _text(match.get('homeTeam', {}).get('name') if isinstance(match.get('homeTeam'), dict) else None)
    away = _text(match.get('awayTeam', {}).get('name') if isinstance(match.get('awayTeam'), dict) else None)
    if not home or not away or _text(listing.get('homeTeam')) != home or _text(listing.get('awayTeam')) != away:
        return False
    kickoff = _instant(match.get('utcDate'))
    listed_kickoff = _instant(listing.get('utcDate'))
    if kickoff is None or listed_kickoff is None:
        return False
    return abs((listed_kickoff - kickoff).total_seconds()) <= KICKOFF_TOLERANCE_SECONDS


class BroadcastSourceRegistry:
    def __init__(self, sources):
        self._sources = {
            item['id']: deepcopy(item)
            for item in sources
            if isinstance(item, dict) and item.get('id') and item.get('url', '').startswith('https://')
        }

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('sources', []))

    def get(self, source_id):
        source = self._sources.get(str(source_id))
        return deepcopy(source) if source else None

    def sources(self):
        return [deepcopy(source) for source in self._sources.values()]

    def describe_listing(self, listing):
        """Normalize a source listing; links remain absent until verified."""
        if not isinstance(listing, dict):
            return None
        name = str(listing.get('displayName') or '').strip()
        if not name:
            return None
        return {
            'displayName': name,
            'region': str(listing.get('region') or 'Region unknown').strip(),
            'regionKnown': bool(str(listing.get('region') or '').strip()),
            'officialUrl': None,
            'source': listing.get('sourceId'),
            'observedAt': listing.get('observedAt'),
            'status': 'unlinked',
        }
