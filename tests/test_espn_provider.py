import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from soccer_scanner.domain.models import ProviderStatus
from soccer_scanner.providers.espn import ESPN_LEAGUES, EspnProvider, normalize_event
from soccer_scanner.providers.http import HttpObservation
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
    assert normalize_event(event(competitors=[]), 'arg.1', 'Liga Profesional') is None
    assert normalize_event(event(competitors=[{'homeAway': 'home'}]), 'arg.1', 'Liga Profesional') is None


def test_fetches_one_inclusive_date_range_per_league_and_reports_outcome():
    client = Mock()
    client.get_json.return_value = (
        {'events': [event()]},
        HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=4),
    )
    provider = EspnProvider(client, leagues={'bra.1': 'Brasileirao', 'arg.1': 'Liga Profesional'})

    outcome = provider.fetch_range(date(2026, 8, 3), date(2026, 8, 4))

    assert outcome.status is ProviderStatus.SUCCESS
    assert len(outcome.fixtures) == 2
    assert outcome.requestCount == 2
    assert client.get_json.call_count == 2
    for call in client.get_json.call_args_list:
        assert call.kwargs['params']['dates'] == '20260803-20260804'


def test_supported_league_set_is_bounded_to_twenty():
    assert len(ESPN_LEAGUES) == 20


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
