from datetime import date
from unittest.mock import Mock

from soccer_scanner.domain.models import ProviderStatus
from soccer_scanner.providers.football_data import FootballDataProvider, normalize_match
from soccer_scanner.providers.http import HttpObservation
from soccer_scanner.services.team_identity import TeamIdentityResolver


def raw_match():
    return {
        'id': 9001,
        'utcDate': '2026-08-03T19:00:00Z',
        'status': 'IN_PLAY',
        'lastUpdated': '2026-08-03T19:02:00Z',
        'homeTeam': {'id': 57, 'name': 'Arsenal FC', 'shortName': 'Arsenal', 'tla': 'ARS', 'crest': 'https://crest.test/a.png'},
        'awayTeam': {'id': 61, 'name': 'Chelsea FC', 'shortName': 'Chelsea', 'tla': 'CHE', 'crest': None},
        'competition': {'id': 2021, 'name': 'Premier League', 'code': 'PL', 'type': 'LEAGUE', 'emblem': None},
        'score': {'winner': None, 'duration': 'REGULAR', 'fullTime': {'home': 1, 'away': 0}},
        'season': {'id': 1900, 'startDate': '2026-08-01', 'endDate': '2027-05-30', 'currentMatchday': 1},
        'stage': 'REGULAR_SEASON',
        'matchday': 1,
        'venue': None,
        'referees': [],
    }


def test_normalizes_football_data_match_with_qualified_ids_and_nulls():
    resolver = TeamIdentityResolver([{
        'canonicalId': 'arsenal', 'name': 'Arsenal', 'aliases': ['Arsenal FC'],
        'providerIds': {'football-data': '57'},
    }])

    match = normalize_match(raw_match(), resolver)

    assert match['providerIds'] == {'football-data': '9001'}
    assert match['homeTeam']['canonicalId'] == 'arsenal'
    assert match['awayTeam']['canonicalId'] is None
    assert match['status']['code'] == 'in_progress'
    assert match['venue'] is None
    assert match['referees'] is None


def test_fetch_range_calls_configured_provider_once_even_for_empty_results():
    client = Mock()
    client.get_json.return_value = (
        {'matches': []},
        HttpObservation(requestCount=1, timeoutCount=0, rateLimitCount=0, durationMs=2),
    )
    provider = FootballDataProvider(client, TeamIdentityResolver([]), enabled=True)

    outcome = provider.fetch_range(date(2026, 8, 3), date(2026, 8, 4))

    assert outcome.status is ProviderStatus.SUCCESS
    assert outcome.fixtures == ()
    assert client.get_json.call_args.kwargs['params'] == {
        'dateFrom': '2026-08-03', 'dateTo': '2026-08-04',
    }


def test_disabled_provider_is_explicit_and_makes_no_request():
    client = Mock()
    provider = FootballDataProvider(client, TeamIdentityResolver([]), enabled=False)

    outcome = provider.fetch_range(date(2026, 8, 3), date(2026, 8, 4))

    assert outcome.status is ProviderStatus.DISABLED
    client.get_json.assert_not_called()
