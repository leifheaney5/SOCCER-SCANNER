"""Bounded, score-free search over canonical fixture responses."""

from datetime import date, timedelta

from soccer_scanner.services.team_identity import normalize_alias


SEARCH_WINDOW_DAYS = 7
DEFAULT_PAST_DAYS = 3
DEFAULT_FUTURE_DAYS = 3


def _text(value):
    return str(value or '').strip()


def _matches_query(value, query):
    return query in normalize_alias(value)


def _entity_id(prefix, item):
    canonical_id = _text(item.get('canonicalId'))
    if canonical_id:
        return canonical_id
    provider = _text(item.get('provider')) or 'unknown'
    provider_id = _text(item.get('providerId'))
    return f'{prefix}:{provider}:{provider_id}' if provider_id else f'{prefix}:{provider}:{normalize_alias(item.get("name"))}'


def _team_result(team):
    return {
        'type': 'team',
        'id': _entity_id('team', team),
        'name': _text(team.get('name')),
        'canonicalId': team.get('canonicalId'),
        'provider': team.get('provider'),
        'providerId': team.get('providerId'),
    }


def _competition_result(competition):
    return {
        'type': 'competition',
        'id': _entity_id('competition', competition),
        'name': _text(competition.get('name')),
        'canonicalId': competition.get('canonicalId'),
        'provider': competition.get('provider'),
        'providerId': competition.get('providerId'),
    }


def _fixture_result(match, local_date):
    return {
        'type': 'fixture',
        'id': _text(match.get('canonicalFixtureId') or match.get('id')),
        'date': local_date.isoformat(),
        'utcDate': match.get('utcDate'),
        'status': match.get('status'),
        'homeTeam': {
            'id': _entity_id('team', match.get('homeTeam') or {}),
            'name': _text((match.get('homeTeam') or {}).get('name')),
        },
        'awayTeam': {
            'id': _entity_id('team', match.get('awayTeam') or {}),
            'name': _text((match.get('awayTeam') or {}).get('name')),
        },
        'competition': {
            'id': _entity_id('competition', match.get('competition') or {}),
            'name': _text((match.get('competition') or {}).get('name')),
        },
    }


class SearchService:
    def __init__(self, fixture_service, *, today=None):
        self.fixture_service = fixture_service
        self.today = today or date.today()

    def search(
        self,
        query,
        *,
        timezone_name='UTC',
        start_date=None,
        end_date=None,
        limit=20,
        offset=0,
    ):
        normalized_query = normalize_alias(query)
        if len(normalized_query) < 2:
            return {
                'state': 'success',
                'query': _text(query),
                'results': [],
                'total': 0,
                'limit': limit,
                'offset': offset,
                'days': [],
            }

        start = start_date or self.today - timedelta(days=DEFAULT_PAST_DAYS)
        end = end_date or self.today + timedelta(days=DEFAULT_FUTURE_DAYS)
        if (end - start).days + 1 > SEARCH_WINDOW_DAYS:
            raise ValueError('Search date window is too large.')

        results = []
        seen = set()
        days = []
        partial = False
        current = start
        while current <= end:
            try:
                payload = self.fixture_service.fixtures_for_date(current, timezone_name)
                matches = payload.get('matches', []) if isinstance(payload, dict) else []
                days.append({'date': current.isoformat(), 'state': 'success', 'matches': len(matches)})
            except Exception:
                partial = True
                matches = []
                days.append({'date': current.isoformat(), 'state': 'unavailable', 'matches': 0})

            for match in matches:
                if not isinstance(match, dict):
                    continue
                home = match.get('homeTeam') or {}
                away = match.get('awayTeam') or {}
                competition = match.get('competition') or {}
                matching_items = [
                    ('team', home),
                    ('team', away),
                    ('competition', competition),
                ]
                if any(_matches_query(item.get('name'), normalized_query) for _, item in matching_items):
                    for kind, item in matching_items:
                        if _matches_query(item.get('name'), normalized_query):
                            result = _team_result(item) if kind == 'team' else _competition_result(item)
                            if (result['type'], result['id']) not in seen:
                                seen.add((result['type'], result['id']))
                                results.append(result)
                    fixture = _fixture_result(match, current)
                    if fixture['id'] and ('fixture', fixture['id']) not in seen:
                        seen.add(('fixture', fixture['id']))
                        results.append(fixture)
            current += timedelta(days=1)

        results.sort(key=lambda item: (item['type'], item.get('name') or item.get('date') or ''))
        total = len(results)
        return {
            'state': 'partial' if partial else 'success',
            'query': _text(query),
            'results': results[offset:offset + limit],
            'total': total,
            'limit': limit,
            'offset': offset,
            'days': days,
        }
