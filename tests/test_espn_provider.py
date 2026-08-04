import json
import threading
import time
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from soccer_scanner.domain.models import ProviderStatus
from soccer_scanner.providers.espn import EspnProvider, normalize_event
from soccer_scanner.providers.http import HttpObservation
from soccer_scanner.services.cache_backend import MemoryCacheBackend
from soccer_scanner.services.team_identity import TeamIdentityResolver


FIXTURES = Path(__file__).parent / 'fixtures' / 'providers'


def event(*, status=None, competitors=None, competition=None):
    competition_payload = {
        'competitors': competitors if competitors is not None else [
            {
                'homeAway': 'home',
                'score': '2',
                'team': {
                    'id': '10',
                    'displayName': 'São Paulo FC',
                    'abbreviation': 'SAO',
                    'logo': 'https://example.test/home.png',
                },
            },
            {
                'homeAway': 'away',
                'score': None,
                'team': {
                    'id': '20',
                    'displayName': 'Atletico Tucuman',
                    'abbreviation': 'ATU',
                },
            },
        ],
    }
    competition_payload.update(competition or {})
    return {
        'id': '401234',
        'date': '2026-08-04T00:30:00Z',
        'status': {'type': status or {
            'name': 'STATUS_SCHEDULED',
            'state': 'pre',
            'completed': False,
        }},
        'competitions': [competition_payload],
        'season': {'year': 2026, 'displayName': '2026'},
    }


def test_normalizes_every_status_without_treating_unknown_as_scheduled():
    statuses = json.loads((FIXTURES / 'espn_statuses.json').read_text(encoding='utf-8'))
    expected = {
        'scheduled': 'scheduled',
        'delayed': 'delayed',
        'in_progress': 'in_progress',
        'half_time': 'half_time',
        'extra_time': 'extra_time',
        'penalties': 'penalties',
        'finished': 'finished',
        'postponed': 'postponed',
        'cancelled': 'cancelled',
        'suspended': 'suspended',
        'abandoned': 'abandoned',
        'unknown': 'unknown',
    }

    for name, status in statuses.items():
        normalized = normalize_event(event(status=status), 'bra.1', 'Brasileirao')
        assert normalized['status']['code'] == expected[name]
        assert normalized['status']['raw'] == status['name']


def test_normalizes_provider_qualified_teams_nullable_scores_and_sourced_fields():
    normalized = normalize_event(
        event(competition={
            'venue': {'fullName': 'Estadio do Morumbi'},
            'notes': [{'headline': 'Quarterfinal'}],
            'type': {'abbreviation': 'QF'},
        }),
        'bra.1',
        'Brasileirao',
    )

    assert normalized['providerIds'] == {'espn': '401234'}
    assert normalized['homeTeam']['provider'] == 'espn'
    assert normalized['homeTeam']['providerId'] == '10'
    assert normalized['homeTeam']['name'] == 'São Paulo FC'
    assert normalized['awayTeam']['providerId'] == '20'
    assert normalized['score']['fullTime'] == {'home': 2, 'away': None}
    assert normalized['season'] == {'year': 2026, 'name': '2026'}
    assert normalized['stage'] == 'QF'
    assert normalized['round'] == 'Quarterfinal'
    assert normalized['venue'] == 'Estadio do Morumbi'
    assert normalized['referees'] is None


def test_normalizes_only_named_espn_streaming_services():
    normalized = normalize_event(
        event(competition={
            'broadcasts': [
                {
                    'type': {'shortName': 'STREAMING'},
                    'media': {'shortName': 'Apple TV'},
                    'region': 'us',
                },
                {
                    'type': {'shortName': 'STREAMING'},
                    'media': {'shortName': 'Apple TV'},
                },
                {
                    'type': {'shortName': 'TV'},
                    'media': {'shortName': 'ESPN'},
                },
                {'type': {'shortName': 'STREAMING'}, 'media': {}},
            ],
        }),
        'bra.1',
        'Brasileirao',
    )

    assert normalized['broadcasts'] == [
        {'name': 'Apple TV', 'type': 'STREAMING', 'region': 'us'},
    ]


def test_missing_optional_fields_remain_null_and_malformed_competitors_are_rejected():
    minimal = event()
    minimal.pop('season')
    normalized = normalize_event(minimal, 'arg.1', 'Liga Profesional')

    assert normalized['season'] is None
    assert normalized['stage'] is None
    assert normalized['round'] is None
    assert normalized['matchday'] is None
    assert normalized['venue'] is None
    assert normalized['referees'] is None
    assert normalized['broadcasts'] == []
    assert normalize_event(event(competitors=[]), 'arg.1', 'Liga Profesional') is None
    assert normalize_event(event(competitors=[{'homeAway': 'home'}]), 'arg.1', 'Liga Profesional') is None


def test_fetches_each_global_provider_date_without_exceeding_response_bound():
    first_event = event()
    first_event['uid'] = 's:600~l:3903~e:401234'
    second_event = event()
    second_event['id'] = '401235'
    second_event['uid'] = 's:600~l:3903~e:401235'
    client = Mock()
    client.get_json.side_effect = [
        (
            {'events': [first_event]},
            HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
        ),
        (
            {'events': [second_event]},
            HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
        ),
    ]
    provider = EspnProvider(
        client,
        league_metadata={'3903': {'name': 'Brasileirão', 'slug': 'bra.1'}},
    )

    outcome = provider.fetch_range(date(2026, 8, 3), date(2026, 8, 4))

    assert outcome.status is ProviderStatus.SUCCESS
    assert len(outcome.fixtures) == 2
    assert outcome.requestCount == 2
    assert client.get_json.call_count == 2
    assert [call.args[0] for call in client.get_json.call_args_list] == [
        'sports/soccer/all/scoreboard',
        'sports/soccer/all/scoreboard',
    ]
    assert [call.kwargs['params']['dates'] for call in client.get_json.call_args_list] == [
        '20260803',
        '20260804',
    ]


def test_global_scoreboard_normalizes_multiple_provider_leagues_in_one_request():
    first = event()
    first['uid'] = 's:600~l:620~e:401234'
    second = event()
    second['id'] = '401235'
    second['uid'] = 's:600~l:19425~e:401235'
    second['competitions'][0]['competitors'][0]['team']['id'] = '30'
    second['competitions'][0]['competitors'][1]['team']['id'] = '40'
    client = Mock()
    client.get_json.return_value = (
        {'events': [first, second]},
        HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
    )
    provider = EspnProvider(
        client,
        league_metadata={
            '620': {'name': 'MLS', 'slug': 'usa.1'},
            '19425': {'name': 'Leagues Cup', 'slug': 'concacaf.leagues.cup'},
        },
    )

    outcome = provider.fetch_range(date(2026, 8, 4), date(2026, 8, 4))

    assert client.get_json.call_count == 1
    assert client.get_json.call_args.args[0] == 'sports/soccer/all/scoreboard'
    assert [fixture['competition']['name'] for fixture in outcome.fixtures] == [
        'MLS',
        'Leagues Cup',
    ]
    assert [fixture['competition']['providerId'] for fixture in outcome.fixtures] == [
        '620',
        '19425',
    ]


def test_global_scoreboard_caches_one_summary_resolution_per_league():
    global_event = event()
    global_event['uid'] = 's:600~l:19425~e:401234'
    client = Mock()
    client.get_json.side_effect = [
        (
            {'events': [global_event]},
            HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
        ),
        (
            {
                'header': {
                    'league': {
                        'id': '19425',
                        'name': 'Leagues Cup',
                        'slug': 'concacaf.leagues.cup',
                        'logos': [{'href': 'https://example.test/leagues-cup.png'}],
                    },
                },
            },
            HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
        ),
        (
            {'events': [global_event]},
            HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
        ),
    ]
    provider = EspnProvider(client, cache=MemoryCacheBackend())

    first = provider.fetch_range(date(2026, 8, 4), date(2026, 8, 4))
    second = provider.fetch_range(date(2026, 8, 4), date(2026, 8, 4))

    assert first.fixtures[0]['competition']['name'] == 'Leagues Cup'
    assert second.fixtures[0]['competition']['name'] == 'Leagues Cup'
    assert [call.args[0] for call in client.get_json.call_args_list] == [
        'sports/soccer/all/scoreboard',
        'sports/soccer/all/summary',
        'sports/soccer/all/scoreboard',
    ]


def test_adapter_resolves_canonical_identity_only_through_registry():
    identities = TeamIdentityResolver([{
        'canonicalId': 'sao-paulo',
        'name': 'São Paulo',
        'aliases': ['São Paulo FC'],
        'providerIds': {'espn': '10'},
    }])

    normalized = normalize_event(event(), 'bra.1', 'Brasileirao', identities)

    assert normalized['homeTeam']['canonicalId'] == 'sao-paulo'
    assert normalized['awayTeam']['canonicalId'] is None


def test_provider_concurrency_is_bounded_and_workers_finish_before_return():
    class ConcurrentClient:
        def __init__(self):
            self.active = 0
            self.maximum = 0
            self.lock = threading.Lock()

        def get_json(self, path, **kwargs):
            with self.lock:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
            time.sleep(0.02)
            with self.lock:
                self.active -= 1
            if path == 'sports/soccer/all/scoreboard':
                events = []
                for index in range(12):
                    item = event()
                    item['id'] = str(401234 + index)
                    item['uid'] = f's:600~l:{3900 + index}~e:{401234 + index}'
                    events.append(item)
                return {'events': events}, HttpObservation(1, 0, 0, 20)
            event_id = kwargs['params']['event']
            league_id = str(3900 + int(event_id) - 401234)
            return {
                'header': {
                    'league': {
                        'id': league_id,
                        'name': f'League {league_id}',
                        'slug': f'league.{league_id}',
                    },
                },
            }, HttpObservation(1, 0, 0, 20)

    client = ConcurrentClient()
    provider = EspnProvider(client, max_workers=4)

    provider.fetch_range(date(2026, 8, 3), date(2026, 8, 3))

    assert 1 < client.maximum <= 4
    assert not any(thread.name.startswith('soccer-espn') for thread in threading.enumerate())
