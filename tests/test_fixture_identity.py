from copy import deepcopy

from soccer_scanner.domain.identity import (
    fixtures_refer_to_same_event,
    merge_fixtures,
)


def fixture(provider, provider_id, kickoff='2026-08-03T19:00:00Z', *, home='arsenal', away='chelsea'):
    return {
        'canonicalFixtureId': None,
        'providerIds': {provider: provider_id},
        'utcDate': kickoff,
        'status': {'code': 'scheduled', 'raw': 'RAW', 'completed': False},
        'homeTeam': {
            'canonicalId': home,
            'provider': provider,
            'providerId': f'{provider}-home',
            'providerIds': {provider: f'{provider}-home'},
            'name': 'Arsenal',
            'crest': None,
        },
        'awayTeam': {
            'canonicalId': away,
            'provider': provider,
            'providerId': f'{provider}-away',
            'providerIds': {provider: f'{provider}-away'},
            'name': 'Chelsea',
            'crest': None,
        },
        'competition': {
            'canonicalId': 'premier-league',
            'provider': provider,
            'providerId': f'{provider}-pl',
            'providerIds': {provider: f'{provider}-pl'},
            'name': 'Premier League',
            'emblem': None,
        },
        'score': {'winner': None, 'fullTime': {'home': None, 'away': None}},
        'season': {'year': 2026, 'name': '2026-27'},
        'stage': 'regular-season',
        'round': None,
        'matchday': None,
        'venue': None,
        'referees': None,
        'sourceUpdatedAt': '2026-08-03T12:00:00Z',
        'sources': [provider],
    }


def test_same_fixture_with_different_provider_ids_and_kickoff_within_tolerance_matches():
    espn = fixture('espn', '401', '2026-08-03T19:00:00Z')
    football_data = fixture('football-data', '9001', '2026-08-03T19:09:59Z')

    assert fixtures_refer_to_same_event(espn, football_data)


def test_kickoff_tolerance_edge_reversed_teams_and_different_teams_do_not_merge():
    original = fixture('espn', '401')
    at_edge = fixture('football-data', '9001', '2026-08-03T19:10:00Z')
    outside = fixture('football-data', '9002', '2026-08-03T19:10:01Z')
    reversed_sides = fixture('football-data', '9003', home='chelsea', away='arsenal')
    different_team = fixture('football-data', '9004', away='liverpool')

    assert fixtures_refer_to_same_event(original, at_edge)
    assert not fixtures_refer_to_same_event(original, outside)
    assert not fixtures_refer_to_same_event(original, reversed_sides)
    assert not fixtures_refer_to_same_event(original, different_team)


def test_merge_keeps_both_provider_ids_and_uses_fresh_reliable_fields():
    espn = fixture('espn', '401')
    espn.update({
        'status': {'code': 'in_progress', 'raw': 'STATUS_IN_PROGRESS', 'completed': False},
        'score': {'winner': None, 'fullTime': {'home': 1, 'away': 0}},
        'venue': 'Emirates Stadium',
        'sourceUpdatedAt': '2026-08-03T19:20:00Z',
    })
    football_data = fixture('football-data', '9001', '2026-08-03T19:01:00Z')
    football_data.update({
        'status': {'code': 'scheduled', 'raw': 'TIMED', 'completed': False},
        'score': {'winner': None, 'fullTime': {'home': None, 'away': None}},
        'matchday': 1,
        'sourceUpdatedAt': '2026-08-03T18:00:00Z',
    })
    football_data['homeTeam']['crest'] = 'https://crests.test/arsenal.png'

    merged = merge_fixtures([football_data, espn])

    assert len(merged) == 1
    match = merged[0]
    assert match['canonicalFixtureId'].startswith('fx_')
    assert match['providerIds'] == {'football-data': '9001', 'espn': '401'}
    assert match['status']['code'] == 'in_progress'
    assert match['score']['fullTime'] == {'home': 1, 'away': 0}
    assert match['venue'] == 'Emirates Stadium'
    assert match['matchday'] == 1
    assert match['homeTeam']['crest'] == 'https://crests.test/arsenal.png'
    assert match['sources'] == ['espn', 'football-data']
    assert 'referees' in match['dataQuality']['missingFields']


def test_merge_keeps_provider_sourced_broadcasts():
    espn = fixture('espn', '401')
    espn['broadcasts'] = [
        {'name': 'Apple TV', 'type': 'STREAMING', 'region': 'us'},
    ]
    football_data = fixture('football-data', '9001')

    merged = merge_fixtures([football_data, espn])

    assert merged[0]['broadcasts'] == [
        {'name': 'Apple TV', 'type': 'STREAMING', 'region': 'us'},
    ]


def test_freshness_conflict_is_deterministic_regardless_of_input_order():
    older = fixture('espn', '401')
    older['venue'] = 'Old venue'
    newer = fixture('football-data', '9001')
    newer['venue'] = 'Verified venue'
    newer['sourceUpdatedAt'] = '2026-08-03T13:00:00Z'

    first = merge_fixtures([older, newer])[0]
    second = merge_fixtures([deepcopy(newer), deepcopy(older)])[0]

    assert first['canonicalFixtureId'] == second['canonicalFixtureId']
    assert first['venue'] == second['venue'] == 'Verified venue'
