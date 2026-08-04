"""football-data.org adapter for the canonical fixture contract."""

from time import monotonic

from soccer_scanner.domain.models import ProviderOutcome, ProviderStatus
from soccer_scanner.providers.http import ProviderRequestError


_STATUS_MAP = {
    'SCHEDULED': 'scheduled',
    'TIMED': 'scheduled',
    'IN_PLAY': 'in_progress',
    'PAUSED': 'half_time',
    'FINISHED': 'finished',
    'POSTPONED': 'postponed',
    'SUSPENDED': 'suspended',
    'CANCELLED': 'cancelled',
}

_COMPETITION_IDS = {
    'PL': 'premier-league',
    'PD': 'la-liga',
    'BL1': 'bundesliga',
    'SA': 'serie-a',
    'FL1': 'ligue-1',
    'CL': 'champions-league',
}


def _text(value):
    result = str(value or '').strip()
    return result or None


def _integer(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _team(payload, identities):
    payload = payload if isinstance(payload, dict) else {}
    provider_id = _text(payload.get('id'))
    resolved = identities.resolve('football-data', provider_id, payload.get('name'))
    return {
        **resolved.as_dict(),
        'name': _text(payload.get('name')),
        'shortName': _text(payload.get('shortName')),
        'tla': _text(payload.get('tla')),
        'crest': _text(payload.get('crest')),
    }


def normalize_match(payload, identities):
    if not isinstance(payload, dict) or not _text(payload.get('id')) or not _text(payload.get('utcDate')):
        return None
    competition = payload.get('competition') if isinstance(payload.get('competition'), dict) else {}
    competition_id = _text(competition.get('id'))
    competition_code = _text(competition.get('code'))
    raw_status = _text(payload.get('status'))
    season_payload = payload.get('season') if isinstance(payload.get('season'), dict) else {}
    start_date = _text(season_payload.get('startDate'))
    season_year = _integer(start_date[:4]) if start_date else None
    season = None
    if season_payload:
        season = {
            'year': season_year,
            'name': None,
            'startDate': start_date,
            'endDate': _text(season_payload.get('endDate')),
        }
    referees = payload.get('referees')
    if not isinstance(referees, list) or not referees:
        referees = None
    score_payload = payload.get('score') if isinstance(payload.get('score'), dict) else {}
    full_time = score_payload.get('fullTime') if isinstance(score_payload.get('fullTime'), dict) else {}
    return {
        'canonicalFixtureId': None,
        'providerIds': {'football-data': _text(payload.get('id'))},
        'utcDate': _text(payload.get('utcDate')),
        'status': {
            'code': _STATUS_MAP.get(raw_status, 'unknown'),
            'raw': raw_status,
            'detail': None,
            'shortDetail': None,
            'clock': None,
            'completed': raw_status == 'FINISHED',
        },
        'homeTeam': _team(payload.get('homeTeam'), identities),
        'awayTeam': _team(payload.get('awayTeam'), identities),
        'competition': {
            'canonicalId': _COMPETITION_IDS.get(competition_code),
            'provider': 'football-data',
            'providerId': competition_id,
            'providerIds': {'football-data': competition_id} if competition_id else {},
            'name': _text(competition.get('name')),
            'code': competition_code,
            'type': _text(competition.get('type')),
            'emblem': _text(competition.get('emblem')),
        },
        'score': {
            'winner': _text(score_payload.get('winner')),
            'fullTime': {'home': _integer(full_time.get('home')), 'away': _integer(full_time.get('away'))},
            'halfTime': score_payload.get('halfTime'),
            'extraTime': score_payload.get('extraTime'),
            'penalties': score_payload.get('penalties'),
        },
        'season': season,
        'stage': _text(payload.get('stage')).casefold().replace('_', '-') if _text(payload.get('stage')) else None,
        'round': _text(payload.get('group')),
        'matchday': _integer(payload.get('matchday')),
        'venue': _text(payload.get('venue')),
        'referees': referees,
        'aggregate': None,
        'sourceUpdatedAt': _text(payload.get('lastUpdated')),
        'sources': ['football-data'],
    }


class FootballDataProvider:
    def __init__(self, client, identities, *, enabled=True, clock=monotonic):
        self.client = client
        self.identities = identities
        self.enabled = bool(enabled)
        self.clock = clock

    def fetch_range(self, start_date, end_date, *, budget=None):
        if not self.enabled:
            return ProviderOutcome(
                provider='football-data', status=ProviderStatus.DISABLED, fixtures=(),
                requestedResources=('matches',), completedResources=(), requestCount=0,
                timeoutCount=0, rateLimitCount=0, sourceUpdatedAt=None, durationMs=0,
                failureCategories=(),
            )
        started = self.clock()
        try:
            payload, observation = self.client.get_json(
                'matches',
                params={'dateFrom': start_date.isoformat(), 'dateTo': end_date.isoformat()},
                budget=budget,
            )
            matches = payload.get('matches', []) if isinstance(payload, dict) else []
            if not isinstance(matches, list):
                raise ProviderRequestError('malformed_payload')
            fixtures = tuple(
                normalized for raw in matches
                if (normalized := normalize_match(raw, self.identities)) is not None
            )
            return ProviderOutcome(
                provider='football-data', status=ProviderStatus.SUCCESS, fixtures=fixtures,
                requestedResources=('matches',), completedResources=('matches',),
                requestCount=observation.requestCount, timeoutCount=observation.timeoutCount,
                rateLimitCount=observation.rateLimitCount,
                sourceUpdatedAt=max(
                    (fixture['sourceUpdatedAt'] for fixture in fixtures if fixture['sourceUpdatedAt']),
                    default=None,
                ),
                durationMs=max(0, round((self.clock() - started) * 1000)),
                failureCategories=(),
            )
        except ProviderRequestError as error:
            observation = error.observation
            status = ProviderStatus.RATE_LIMITED if error.category == 'rate_limited' else ProviderStatus.UNAVAILABLE
            return ProviderOutcome(
                provider='football-data', status=status, fixtures=(),
                requestedResources=('matches',), completedResources=(),
                requestCount=observation.requestCount if observation else 0,
                timeoutCount=observation.timeoutCount if observation else 0,
                rateLimitCount=observation.rateLimitCount if observation else 0,
                sourceUpdatedAt=None,
                durationMs=max(0, round((self.clock() - started) * 1000)),
                failureCategories=(error.category,),
            )
