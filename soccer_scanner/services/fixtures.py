from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, time, timedelta, timezone
from threading import Lock
from weakref import WeakValueDictionary
from zoneinfo import ZoneInfo

import requests

from soccer_scanner.domain.identity import merge_fixtures
from soccer_scanner.services.team_identity import normalize_alias

from .fixture_analytics import (
    analyze_daily_matches,
    calculate_match_importance,
    check_rivalry_factor,
    convert_espn_to_standard_format,
)

ESPN_LEAGUES = {
    'eng.1': 'Premier League', 'esp.1': 'La Liga', 'ger.1': 'Bundesliga',
    'ita.1': 'Serie A', 'fra.1': 'Ligue 1', 'uefa.champions': 'Champions League',
    'uefa.europa': 'Europa League', 'uefa.europa.conf': 'Conference League',
    'ned.1': 'Eredivisie', 'por.1': 'Primeira Liga', 'bel.1': 'Pro League',
    'aut.1': 'Austrian Bundesliga', 'tur.1': 'Süper Lig',
    'sco.1': 'Scottish Premiership', 'eng.2': 'Championship',
    'esp.2': 'Segunda División', 'ger.2': '2. Bundesliga', 'ita.2': 'Serie B',
    'bra.1': 'Brasileirão', 'arg.1': 'Liga Profesional',
}


class FixtureService:
    def __init__(self, football_data, cache, timeout=(3.05, 8), max_workers=8,
                 fetch_deadline=4, identity_resolver=None):
        self.football_data = football_data
        self.cache = cache
        self.timeout = timeout
        self.max_workers = max_workers
        self.fetch_deadline = fetch_deadline
        self.identity_resolver = identity_resolver
        self._key_locks = WeakValueDictionary()
        self._key_locks_guard = Lock()

    def fixtures_for_date(self, requested_date, timezone_name='UTC'):
        cache_key = f'{requested_date.isoformat()}|{timezone_name}'
        cached = self.cache.get(cache_key)
        if cached is not None:
            return {**cached, 'cached': True}

        # Single-flight: only one request per date may fill an empty cache key.
        key_lock = self._lock_for(cache_key)
        with key_lock:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return {**cached, 'cached': True}
            return self._load_fixtures(requested_date, timezone_name, cache_key)

    def _load_fixtures(self, requested_date, timezone_name, cache_key):
        provider_dates = self._provider_dates(requested_date, timezone_name)
        matches, espn_health = self._fetch_espn(provider_dates)

        espn_count = len(matches)
        fallback_count = 0
        football_data_health = 'not_needed'
        if len(matches) < 5:
            try:
                fallback = self.football_data.get('matches', params={
                    'dateFrom': provider_dates[0].isoformat(),
                    'dateTo': provider_dates[-1].isoformat(),
                }).get('matches', [])
                matches.extend(fallback)
                fallback_count = len(fallback)
                football_data_health = 'available'
            except requests.RequestException:
                football_data_health = 'unavailable'

        no_provider_succeeded = (
            espn_health['successful_competitions'] == 0
            and football_data_health == 'unavailable'
        )
        if no_provider_succeeded:
            stale = self.cache.get_stale(cache_key)
            if stale is not None:
                return {
                    **stale,
                    'cached': True,
                    'stale': True,
                    'partial': True,
                }

        matches = self._enhance_and_deduplicate(
            matches,
            requested_date,
            timezone_name,
            identity_resolver=self.identity_resolver,
        )
        matches.sort(key=lambda match: (
            -match['enhanced_info']['importance_score'], match.get('utcDate', '')
        ))
        result = {
            'matches': matches,
            'featured_matches': matches[:6],
            'total_matches': len(matches),
            'date': requested_date.isoformat(),
            'timezone': timezone_name,
            'source_stats': {
                'espn_api': espn_count,
                'football_data_fallback': fallback_count,
                'total_unique': len(matches),
            },
            'match_statistics': analyze_daily_matches(matches),
            'last_updated': datetime.now().astimezone().isoformat(),
            'cached': False,
            'stale': False,
            'partial': espn_health['failed_requests'] > 0,
            'providers': {
                'espn': espn_health,
                'football_data': {'status': football_data_health},
            },
        }
        self.cache.set(cache_key, result)
        return result

    def _lock_for(self, key):
        with self._key_locks_guard:
            return self._key_locks.setdefault(key, Lock())

    def _fetch_espn(self, provider_dates):
        def fetch(league):
            league_id, league_name = league
            range_value = f'{provider_dates[0]:%Y%m%d}'
            if provider_dates[-1] != provider_dates[0]:
                range_value += f'-{provider_dates[-1]:%Y%m%d}'
            response = requests.get(
                f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard',
                params={
                    'dates': range_value,
                    'limit': 100,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return [
                converted for event in response.json().get('events', [])
                if (converted := convert_espn_to_standard_format(
                    event, league_name, league_id,
                ))
            ]

        matches = []
        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        work_items = list(ESPN_LEAGUES.items())
        futures = {executor.submit(fetch, item): item for item in work_items}
        completed, pending = wait(futures, timeout=self.fetch_deadline)
        failed = len(pending)
        successful_leagues = set()
        for future in completed:
            try:
                matches.extend(future.result())
                successful_leagues.add(futures[future][0])
            except (requests.RequestException, ValueError, TypeError):
                failed += 1
        for future in pending:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        successful = len(successful_leagues)
        status = 'available' if failed == 0 else ('unavailable' if successful == 0 else 'degraded')
        return matches, {
            'status': status,
            'successful_competitions': successful,
            'failed_competitions': len(ESPN_LEAGUES) - successful,
            'successful_requests': len(work_items) - failed,
            'failed_requests': failed,
        }

    @staticmethod
    def _provider_dates(requested_date, timezone_name):
        local_zone = ZoneInfo(timezone_name)
        local_start = datetime.combine(requested_date, time.min, local_zone)
        local_end = local_start + timedelta(days=1)
        utc_start = local_start.astimezone(timezone.utc)
        utc_end = local_end.astimezone(timezone.utc) - timedelta(microseconds=1)
        dates = {utc_start.date(), utc_end.date()}
        return sorted(dates)

    @staticmethod
    def _enhance_and_deduplicate(
        matches,
        requested_date,
        timezone_name='UTC',
        identity_resolver=None,
    ):
        normalized = []
        local_zone = ZoneInfo(timezone_name)
        for match in matches:
            try:
                kickoff = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
                if kickoff.tzinfo is None:
                    kickoff = kickoff.replace(tzinfo=timezone.utc)
                match_date = kickoff.astimezone(local_zone).date()
                if match_date != requested_date:
                    continue
                provider = 'espn' if str(match.get('id', '')).startswith('espn_') else 'football-data'
                normalized_match = dict(match)
                raw_provider_id = str(match.get('id') or '')
                if provider == 'espn' and raw_provider_id.startswith('espn_'):
                    raw_provider_id = raw_provider_id[5:]
                normalized_match['providerIds'] = {
                    **(match.get('providerIds') or {}),
                    **({provider: raw_provider_id} if raw_provider_id else {}),
                }
                normalized_match['sourceUpdatedAt'] = (
                    match.get('sourceUpdatedAt') or match.get('lastUpdated')
                )
                if identity_resolver is not None:
                    for side in ('homeTeam', 'awayTeam'):
                        team = dict(match.get(side) or {})
                        provider_id = team.get('providerId') or team.get('id')
                        resolved = identity_resolver.resolve(
                            team.get('provider') or provider,
                            provider_id,
                            team.get('name'),
                        )
                        normalized_match[side] = {**team, **resolved.as_dict()}
                competition = dict(match.get('competition') or {})
                competition_slug = {
                    'premierleague': 'premier-league',
                    'laliga': 'la-liga',
                    'bundesliga': 'bundesliga',
                    'seriea': 'serie-a',
                    'ligue1': 'ligue-1',
                    'championsleague': 'champions-league',
                }.get(normalize_alias(competition.get('name')))
                competition_provider_id = str(competition.get('providerId') or competition.get('id') or '')
                normalized_match['competition'] = {
                    **competition,
                    'canonicalId': competition.get('canonicalId') or competition_slug,
                    'provider': competition.get('provider') or provider,
                    'providerId': competition_provider_id or None,
                    'providerIds': {
                        **(competition.get('providerIds') or {}),
                        **({provider: competition_provider_id} if competition_provider_id else {}),
                    },
                }
                normalized.append(normalized_match)
            except (KeyError, TypeError, ValueError):
                continue
        merged_matches = merge_fixtures(normalized)
        return [
            {
                **match,
                'id': match['canonicalFixtureId'],
                'enhanced_info': {
                    'importance_score': calculate_match_importance(match),
                    'rivalry_factor': check_rivalry_factor(match),
                    'match_date': requested_date.isoformat(),
                    'days_from_today': 0,
                    'source': ' + '.join(match.get('sources') or []),
                },
            }
            for match in merged_matches
        ]
