from datetime import date

from soccer_scanner.services.search import SearchService


class FixtureService:
    def __init__(self, payloads, failures=()):
        self.payloads = payloads
        self.failures = set(failures)
        self.requested = []

    def fixtures_for_date(self, requested_date, timezone_name):
        self.requested.append((requested_date, timezone_name))
        if requested_date in self.failures:
            raise RuntimeError('provider failure must become a partial search')
        return self.payloads.get(requested_date, {'matches': [], 'state': 'empty_confirmed'})


def match(home, away, competition, fixture_id='fx_123'):
    return {
        'canonicalFixtureId': fixture_id,
        'utcDate': '2026-08-13T18:00:00Z',
        'status': {'code': 'scheduled', 'detail': 'Scheduled'},
        'homeTeam': {'canonicalId': 'arsenal', 'name': home, 'provider': 'espn', 'providerId': '359'},
        'awayTeam': {'canonicalId': None, 'name': away, 'provider': 'espn', 'providerId': '360'},
        'competition': {'canonicalId': 'premier-league', 'name': competition, 'provider': 'espn', 'providerId': 'eng.1'},
        'score': {'fullTime': {'home': 9, 'away': 9}},
    }


def test_search_returns_teams_competitions_and_score_free_fixtures_in_a_bounded_window():
    provider = FixtureService({
        date(2026, 8, 13): {'matches': [match('Arsenal', 'Chelsea', 'Premier League')]},
    })
    service = SearchService(provider, today=date(2026, 8, 13))

    result = service.search('ars', timezone_name='America/New_York')

    assert result['state'] == 'success'
    assert {item['type'] for item in result['results']} == {'team', 'fixture'}
    assert result['results'][0]['id']
    assert all('score' not in item for item in result['results'])
    assert all('score' not in str(item) for item in result['results'])
    competition_result = service.search('premier', start_date=date(2026, 8, 13), end_date=date(2026, 8, 13))
    assert [item['type'] for item in competition_result['results']] == ['competition', 'fixture']
    assert provider.requested[:7] == [
        (date(2026, 8, 10), 'America/New_York'),
        (date(2026, 8, 11), 'America/New_York'),
        (date(2026, 8, 12), 'America/New_York'),
        (date(2026, 8, 13), 'America/New_York'),
        (date(2026, 8, 14), 'America/New_York'),
        (date(2026, 8, 15), 'America/New_York'),
        (date(2026, 8, 16), 'America/New_York'),
    ]
    assert provider.requested[7:] == [(date(2026, 8, 13), 'UTC')]


def test_search_preserves_successful_days_when_one_day_fails():
    provider = FixtureService(
        {date(2026, 8, 13): {'matches': [match('Arsenal', 'Chelsea', 'Premier League')] }},
        failures={date(2026, 8, 14)},
    )
    service = SearchService(provider, today=date(2026, 8, 13))

    result = service.search('ars', start_date=date(2026, 8, 13), end_date=date(2026, 8, 14))

    assert result['state'] == 'partial'
    assert {item['type'] for item in result['results']} == {'team', 'fixture'}
    assert result['days'] == [
        {'date': '2026-08-13', 'state': 'success', 'matches': 1},
        {'date': '2026-08-14', 'state': 'unavailable', 'matches': 0},
    ]
