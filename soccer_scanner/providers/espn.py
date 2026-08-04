"""ESPN scoreboard adapter with truthful, provider-qualified normalization."""

from datetime import date, timedelta
from time import monotonic

from soccer_scanner.domain.models import ProviderOutcome, ProviderStatus
from soccer_scanner.providers.http import ProviderRequestError


ESPN_LEAGUES = {
    'eng.1': 'Premier League',
    'esp.1': 'La Liga',
    'ger.1': 'Bundesliga',
    'ita.1': 'Serie A',
    'fra.1': 'Ligue 1',
    'uefa.champions': 'Champions League',
    'uefa.europa': 'Europa League',
    'uefa.europa.conf': 'Conference League',
    'ned.1': 'Eredivisie',
    'por.1': 'Primeira Liga',
    'bel.1': 'Pro League',
    'aut.1': 'Austrian Bundesliga',
    'tur.1': 'Süper Lig',
    'sco.1': 'Scottish Premiership',
    'eng.2': 'Championship',
    'esp.2': 'Segunda División',
    'ger.2': '2. Bundesliga',
    'ita.2': 'Serie B',
    'bra.1': 'Brasileirão',
    'arg.1': 'Liga Profesional',
}

ESPN_COMPETITION_IDS = {
    'eng.1': 'premier-league',
    'esp.1': 'la-liga',
    'ger.1': 'bundesliga',
    'ita.1': 'serie-a',
    'fra.1': 'ligue-1',
    'uefa.champions': 'champions-league',
    'uefa.europa': 'europa-league',
    'uefa.europa.conf': 'conference-league',
    'ned.1': 'eredivisie',
    'por.1': 'primeira-liga',
    'bel.1': 'belgian-pro-league',
    'aut.1': 'austrian-bundesliga',
    'tur.1': 'super-lig',
    'sco.1': 'scottish-premiership',
    'eng.2': 'championship',
    'esp.2': 'segunda-division',
    'ger.2': 'second-bundesliga',
    'ita.2': 'serie-b',
    'bra.1': 'brasileirao',
    'arg.1': 'liga-profesional',
}


_STATUS_MAP = {
    'STATUS_SCHEDULED': 'scheduled',
    'STATUS_DELAYED': 'delayed',
    'STATUS_IN_PROGRESS': 'in_progress',
    'STATUS_FIRST_HALF': 'in_progress',
    'STATUS_SECOND_HALF': 'in_progress',
    'STATUS_HALFTIME': 'half_time',
    'STATUS_END_PERIOD': 'half_time',
    'STATUS_EXTRA_TIME': 'extra_time',
    'STATUS_PENALTIES': 'penalties',
    'STATUS_FINAL': 'finished',
    'STATUS_FULL_TIME': 'finished',
    'STATUS_FINAL_AET': 'finished',
    'STATUS_FINAL_PEN': 'finished',
    'STATUS_POSTPONED': 'postponed',
    'STATUS_CANCELED': 'cancelled',
    'STATUS_CANCELLED': 'cancelled',
    'STATUS_SUSPENDED': 'suspended',
    'STATUS_ABANDONED': 'abandoned',
}


def _nullable_text(value):
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _nullable_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _team(competitor, identities=None):
    if not isinstance(competitor, dict):
        return None
    payload = competitor.get('team')
    if not isinstance(payload, dict):
        return None
    provider_id = _nullable_text(payload.get('id'))
    name = _nullable_text(payload.get('displayName') or payload.get('name'))
    if not provider_id or not name:
        return None
    abbreviation = _nullable_text(payload.get('abbreviation'))
    identity = (
        identities.resolve('espn', provider_id, name).as_dict()
        if identities is not None
        else {
            'canonicalId': None,
            'provider': 'espn',
            'providerId': provider_id,
            'providerIds': {'espn': provider_id},
        }
    )
    return {
        **identity,
        'name': name,
        'shortName': _nullable_text(payload.get('shortDisplayName')) or abbreviation,
        'tla': abbreviation,
        'crest': _nullable_text(payload.get('logo')),
    }


def _winner(home_score, away_score, completed):
    if not completed or home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return 'home'
    if away_score > home_score:
        return 'away'
    return 'draw'


def normalize_event(event, league_id, league_name, identities=None):
    """Normalize one ESPN event; malformed identities are discarded."""
    if not isinstance(event, dict):
        return None
    provider_id = _nullable_text(event.get('id'))
    utc_date = _nullable_text(event.get('date'))
    competitions = event.get('competitions')
    if not provider_id or not utc_date or not isinstance(competitions, list) or not competitions:
        return None
    competition_event = competitions[0]
    if not isinstance(competition_event, dict):
        return None
    competitors = competition_event.get('competitors')
    if not isinstance(competitors, list):
        return None
    home_competitor = next(
        (item for item in competitors if isinstance(item, dict) and item.get('homeAway') == 'home'),
        None,
    )
    away_competitor = next(
        (item for item in competitors if isinstance(item, dict) and item.get('homeAway') == 'away'),
        None,
    )
    home = _team(home_competitor, identities)
    away = _team(away_competitor, identities)
    if home is None or away is None:
        return None

    raw_status = event.get('status', {}).get('type', {})
    if not isinstance(raw_status, dict):
        raw_status = {}
    raw_status_name = _nullable_text(raw_status.get('name'))
    status_code = _STATUS_MAP.get(raw_status_name, 'unknown')
    completed = bool(raw_status.get('completed')) or status_code == 'finished'
    home_score = _nullable_int(home_competitor.get('score'))
    away_score = _nullable_int(away_competitor.get('score'))

    season_payload = event.get('season')
    season = None
    if isinstance(season_payload, dict):
        year = _nullable_int(season_payload.get('year'))
        name = _nullable_text(season_payload.get('displayName') or season_payload.get('slug'))
        if year is not None or name is not None:
            season = {'year': year, 'name': name}

    type_payload = competition_event.get('type')
    stage = (
        _nullable_text(type_payload.get('abbreviation') or type_payload.get('text'))
        if isinstance(type_payload, dict)
        else None
    )
    notes = competition_event.get('notes')
    round_name = None
    if isinstance(notes, list):
        round_name = next(
            (
                _nullable_text(note.get('headline'))
                for note in notes
                if isinstance(note, dict) and _nullable_text(note.get('headline'))
            ),
            None,
        )
    venue_payload = competition_event.get('venue')
    venue = (
        _nullable_text(venue_payload.get('fullName'))
        if isinstance(venue_payload, dict)
        else None
    )
    source_updated_at = _nullable_text(
        event.get('lastUpdated') or competition_event.get('lastUpdated')
    )

    return {
        'canonicalFixtureId': None,
        'providerIds': {'espn': provider_id},
        'utcDate': utc_date,
        'status': {
            'code': status_code,
            'raw': raw_status_name,
            'detail': _nullable_text(raw_status.get('detail')),
            'shortDetail': _nullable_text(raw_status.get('shortDetail')),
            'clock': _nullable_text(event.get('status', {}).get('displayClock')),
            'completed': completed,
        },
        'homeTeam': home,
        'awayTeam': away,
        'score': {
            'winner': _winner(home_score, away_score, completed),
            'fullTime': {'home': home_score, 'away': away_score},
            'halfTime': None,
            'extraTime': None,
            'penalties': None,
        },
        'competition': {
            'canonicalId': ESPN_COMPETITION_IDS.get(league_id),
            'provider': 'espn',
            'providerId': league_id,
            'providerIds': {'espn': league_id},
            'name': league_name,
            'code': None,
            'type': None,
            'emblem': None,
        },
        'season': season,
        'stage': stage,
        'round': round_name,
        'matchday': _nullable_int(competition_event.get('matchday')),
        'venue': venue,
        'referees': None,
        'aggregate': None,
        'sourceUpdatedAt': source_updated_at,
        'sources': ['espn'],
        'dataQuality': {'missingFields': []},
    }


class EspnProvider:
    def __init__(self, client, *, identities=None, leagues=None, clock=monotonic):
        self.client = client
        self.identities = identities
        self.leagues = dict(leagues or ESPN_LEAGUES)
        self.clock = clock

    def fetch_range(self, start_date, end_date, *, budget=None):
        started = self.clock()
        fixtures = []
        completed = []
        failures = []
        request_count = timeout_count = rate_limit_count = 0
        source_updates = []

        for league_id, league_name in self.leagues.items():
            try:
                payloads, observations = self._range_payloads(
                    league_id, start_date, end_date, budget=budget,
                )
                completed.append(league_id)
                for observation in observations:
                    request_count += observation.requestCount
                    timeout_count += observation.timeoutCount
                    rate_limit_count += observation.rateLimitCount
                for payload in payloads:
                    updated = _nullable_text(payload.get('timestamp')) if isinstance(payload, dict) else None
                    if updated:
                        source_updates.append(updated)
                    events = payload.get('events', []) if isinstance(payload, dict) else []
                    if not isinstance(events, list):
                        raise ProviderRequestError('malformed_payload')
                    fixtures.extend(
                        normalized
                        for raw_event in events
                        if (normalized := normalize_event(
                            raw_event, league_id, league_name, self.identities,
                        )) is not None
                    )
            except ProviderRequestError as error:
                observation = error.observation
                if observation is not None:
                    request_count += observation.requestCount
                    timeout_count += observation.timeoutCount
                    rate_limit_count += observation.rateLimitCount
                failures.append(error.category)

        if not completed:
            status = ProviderStatus.RATE_LIMITED if failures and set(failures) == {'rate_limited'} else ProviderStatus.UNAVAILABLE
        elif failures:
            status = ProviderStatus.PARTIAL
        else:
            status = ProviderStatus.SUCCESS
        return ProviderOutcome(
            provider='espn',
            status=status,
            fixtures=tuple(fixtures),
            requestedResources=tuple(self.leagues),
            completedResources=tuple(completed),
            requestCount=request_count,
            timeoutCount=timeout_count,
            rateLimitCount=rate_limit_count,
            sourceUpdatedAt=max(source_updates) if source_updates else None,
            durationMs=max(0, round((self.clock() - started) * 1000)),
            failureCategories=tuple(sorted(set(failures))),
        )

    def _range_payloads(self, league_id, start_date, end_date, *, budget):
        params = {
            'dates': f'{start_date:%Y%m%d}-{end_date:%Y%m%d}',
            'limit': 100,
        }
        path = f'sports/soccer/{league_id}/scoreboard'
        try:
            payload, observation = self.client.get_json(path, params=params, budget=budget)
            if not isinstance(payload, dict) or not isinstance(payload.get('events', []), list):
                raise ProviderRequestError('malformed_payload')
            return [payload], [observation]
        except ProviderRequestError as error:
            if start_date == end_date or error.category not in {'http_4xx', 'invalid_json', 'malformed_payload'}:
                raise
        payloads = []
        observations = []
        current = start_date
        while current <= end_date:
            payload, observation = self.client.get_json(
                path,
                params={'dates': f'{current:%Y%m%d}', 'limit': 100},
                budget=budget,
            )
            if not isinstance(payload, dict) or not isinstance(payload.get('events', []), list):
                raise ProviderRequestError('malformed_payload')
            payloads.append(payload)
            observations.append(observation)
            current += timedelta(days=1)
        return payloads, observations
