"""ESPN scoreboard adapter with truthful, provider-qualified normalization."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta
import re
from time import monotonic

from soccer_scanner.domain.models import ProviderOutcome, ProviderStatus
from soccer_scanner.providers.http import ProviderRequestError


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

_LEAGUE_UID_PATTERN = re.compile(r'(?:^|~)l:([^~]+)')


def extract_league_id(event):
    """Return the provider-qualified league ID carried by a global event UID."""
    if not isinstance(event, dict):
        return None
    match = _LEAGUE_UID_PATTERN.search(str(event.get('uid') or ''))
    return match.group(1) if match else None


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


def _streaming_services(competition_event):
    broadcasts = competition_event.get('broadcasts')
    if not isinstance(broadcasts, list):
        return []
    services = []
    seen = set()
    for broadcast in broadcasts:
        if not isinstance(broadcast, dict):
            continue
        broadcast_type = broadcast.get('type')
        kind = _nullable_text(
            broadcast_type.get('shortName') if isinstance(broadcast_type, dict) else None
        )
        if kind != 'STREAMING':
            continue
        media = broadcast.get('media')
        name = _nullable_text(
            (media.get('shortName') or media.get('name')) if isinstance(media, dict) else None
        )
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        services.append({
            'name': name,
            'type': kind,
            'region': _nullable_text(broadcast.get('region')),
        })
    return services


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


def normalize_event(
    event,
    league_id,
    league_name,
    identities=None,
    *,
    league_slug=None,
    league_emblem=None,
):
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
            'canonicalId': ESPN_COMPETITION_IDS.get(league_slug or league_id),
            'provider': 'espn',
            'providerId': league_id,
            'providerIds': {'espn': league_id},
            'name': league_name,
            'code': None,
            'type': None,
            'emblem': league_emblem,
        },
        'season': season,
        'stage': stage,
        'round': round_name,
        'matchday': _nullable_int(competition_event.get('matchday')),
        'venue': venue,
        'referees': None,
        'aggregate': None,
        'broadcasts': _streaming_services(competition_event),
        'sourceUpdatedAt': source_updated_at,
        'sources': ['espn'],
        'dataQuality': {'missingFields': []},
    }


class EspnProvider:
    def __init__(
        self,
        client,
        *,
        identities=None,
        league_metadata=None,
        cache=None,
        league_metadata_ttl_seconds=86_400,
        max_workers=8,
        clock=monotonic,
    ):
        self.client = client
        self.identities = identities
        self.league_metadata = {
            str(key): dict(value)
            for key, value in (league_metadata or {}).items()
            if isinstance(value, dict)
        }
        self.cache = cache
        self.league_metadata_ttl_seconds = max(60, int(league_metadata_ttl_seconds))
        self.max_workers = max(1, min(8, int(max_workers)))
        self.clock = clock

    def fetch_range(self, start_date, end_date, *, budget=None):
        started = self.clock()
        events = []
        global_observations = []
        successful_global_responses = 0
        representatives = {}
        failures = []
        current_date = start_date
        while current_date <= end_date:
            try:
                payload, observation = self.client.get_json(
                    'sports/soccer/all/scoreboard',
                    params={
                        'dates': f'{current_date:%Y%m%d}',
                        'limit': 500,
                    },
                    budget=budget,
                )
                global_observations.append(observation)
                if not isinstance(payload, dict) or not isinstance(payload.get('events', []), list):
                    failures.append('malformed_payload')
                else:
                    successful_global_responses += 1
                    events.extend(payload['events'])
            except ProviderRequestError as error:
                if error.observation is not None:
                    global_observations.append(error.observation)
                failures.append(error.category)
            current_date += timedelta(days=1)

        if not successful_global_responses:
            status = (
                ProviderStatus.RATE_LIMITED
                if failures and set(failures) == {'rate_limited'}
                else ProviderStatus.UNAVAILABLE
            )
            return ProviderOutcome(
                provider='espn',
                status=status,
                fixtures=(),
                requestedResources=(),
                completedResources=(),
                requestCount=sum(item.requestCount for item in global_observations),
                timeoutCount=sum(item.timeoutCount for item in global_observations),
                rateLimitCount=sum(item.rateLimitCount for item in global_observations),
                sourceUpdatedAt=None,
                durationMs=max(0, round((self.clock() - started) * 1000)),
                failureCategories=tuple(sorted(set(failures))),
            )

        for event in events:
            league_id = extract_league_id(event)
            if league_id is None:
                failures.append('missing_league_identity')
                continue
            representatives.setdefault(league_id, event)

        metadata, metadata_observations, metadata_failures = self._resolve_metadata(
            representatives,
            budget=budget,
        )
        failures.extend(metadata_failures)
        request_count = sum(item.requestCount for item in global_observations) + sum(
            item.requestCount for item in metadata_observations
        )
        timeout_count = sum(item.timeoutCount for item in global_observations) + sum(
            item.timeoutCount for item in metadata_observations
        )
        rate_limit_count = sum(item.rateLimitCount for item in global_observations) + sum(
            item.rateLimitCount for item in metadata_observations
        )
        fixtures = []
        source_updates = []
        completed = []
        for event in events:
            league_id = extract_league_id(event)
            league = metadata.get(league_id)
            if league is None:
                continue
            normalized = normalize_event(
                event,
                league_id,
                league['name'],
                self.identities,
                league_slug=league.get('slug'),
                league_emblem=league.get('emblem'),
            )
            if normalized is None:
                failures.append('malformed_event')
                continue
            completed.append(league_id)
            fixtures.append(normalized)
            if normalized.get('sourceUpdatedAt'):
                source_updates.append(normalized['sourceUpdatedAt'])

        status = ProviderStatus.PARTIAL if failures else ProviderStatus.SUCCESS
        return ProviderOutcome(
            provider='espn',
            status=status,
            fixtures=tuple(fixtures),
            requestedResources=tuple(sorted(representatives)),
            completedResources=tuple(sorted(set(completed))),
            requestCount=request_count,
            timeoutCount=timeout_count,
            rateLimitCount=rate_limit_count,
            sourceUpdatedAt=max(source_updates) if source_updates else None,
            durationMs=max(0, round((self.clock() - started) * 1000)),
            failureCategories=tuple(sorted(set(failures))),
        )

    def _resolve_metadata(self, representatives, *, budget):
        metadata = {}
        observations = []
        failures = []
        pending = {}
        resources = iter(representatives.items())
        exhausted = False

        with ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix='soccer-espn-meta',
        ) as executor:
            while len(pending) < self.max_workers:
                try:
                    league_id, event = next(resources)
                except StopIteration:
                    exhausted = True
                    break
                pending[executor.submit(
                    self._resolve_league_metadata,
                    league_id,
                    event.get('id'),
                    budget,
                )] = league_id

            while pending:
                done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                for future in done:
                    league_id = pending.pop(future)
                    try:
                        resolved, observation = future.result()
                        metadata[league_id] = resolved
                        if observation is not None:
                            observations.append(observation)
                    except ProviderRequestError as error:
                        if error.observation is not None:
                            observations.append(error.observation)
                        failures.append(f'league_metadata_{error.category}')

                while len(pending) < self.max_workers and not exhausted:
                    if budget is not None and budget.remaining() <= 0:
                        failures.append('league_metadata_budget_exhausted')
                        exhausted = True
                        break
                    try:
                        league_id, event = next(resources)
                    except StopIteration:
                        exhausted = True
                        break
                    pending[executor.submit(
                        self._resolve_league_metadata,
                        league_id,
                        event.get('id'),
                        budget,
                    )] = league_id

        return metadata, observations, failures

    def _resolve_league_metadata(self, league_id, event_id, budget):
        cached = self.league_metadata.get(league_id)
        if cached is not None:
            return cached, None
        if not event_id:
            raise ProviderRequestError('missing_event_id')
        observations = []

        def load():
            payload, observation = self.client.get_json(
                'sports/soccer/all/summary',
                params={'event': event_id},
                budget=budget,
            )
            observations.append(observation)
            league = payload.get('header', {}).get('league') if isinstance(payload, dict) else None
            if not isinstance(league, dict):
                raise ProviderRequestError('malformed_payload', observation=observation)
            name = _nullable_text(league.get('name'))
            if _nullable_text(league.get('id')) != league_id or not name:
                raise ProviderRequestError('malformed_payload', observation=observation)
            logos = league.get('logos')
            emblem = next(
                (
                    _nullable_text(item.get('href'))
                    for item in logos
                    if isinstance(item, dict) and _nullable_text(item.get('href'))
                ),
                None,
            ) if isinstance(logos, list) else None
            return {
                'name': name,
                'slug': _nullable_text(league.get('slug')),
                'emblem': emblem,
            }

        if self.cache is None:
            resolved = load()
        else:
            lookup = self.cache.get_or_load(
                f'espn-league-metadata:{league_id}',
                load,
                ttl_seconds=self.league_metadata_ttl_seconds,
                stale_ttl_seconds=7 * 24 * 60 * 60,
            )
            resolved = lookup.value
        self.league_metadata[league_id] = resolved
        return resolved, observations[0] if observations else None
