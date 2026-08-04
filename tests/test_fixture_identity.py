from copy import deepcopy

import pytest

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


def unmapped_fixture(provider_id, *, kickoff='2026-08-03T19:00:00Z'):
    match = fixture(
        'espn',
        provider_id,
        kickoff,
        home=f'home-{provider_id}',
        away=f'away-{provider_id}',
    )
    match['homeTeam'].update({
        'canonicalId': None,
        'providerId': f'home-{provider_id}',
        'providerIds': {'espn': f'home-{provider_id}'},
        'name': f'Home {provider_id}',
    })
    match['awayTeam'].update({
        'canonicalId': None,
        'providerId': f'away-{provider_id}',
        'providerIds': {'espn': f'away-{provider_id}'},
        'name': f'Away {provider_id}',
    })
    match['competition'].update({
        'canonicalId': None,
        'providerId': 'unmapped-league',
        'providerIds': {'espn': 'unmapped-league'},
        'name': 'Unmapped League',
    })
    return match


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


def test_different_event_ids_from_the_same_provider_do_not_merge():
    first = fixture('espn', '401')
    second = fixture('espn', '402', '2026-08-03T19:05:00Z')

    assert not fixtures_refer_to_same_event(first, second)
    assert len(merge_fixtures([first, second])) == 2


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


def test_two_unmapped_events_at_same_kickoff_have_distinct_public_ids():
    merged = merge_fixtures([
        unmapped_fixture('401001'),
        unmapped_fixture('401002'),
    ])

    assert len(merged) == 2
    assert len({match['canonicalFixtureId'] for match in merged}) == 2


def test_ten_unmapped_events_at_same_kickoff_have_distinct_public_ids():
    merged = merge_fixtures([
        unmapped_fixture(f'4010{index:02d}')
        for index in range(10)
    ])

    assert len(merged) == 10
    assert len({match['canonicalFixtureId'] for match in merged}) == 10


def test_provider_event_public_id_survives_kickoff_correction():
    before = merge_fixtures([
        unmapped_fixture('401001', kickoff='2026-08-03T19:00:00Z'),
    ])[0]
    after = merge_fixtures([
        unmapped_fixture('401001', kickoff='2026-08-03T19:30:00Z'),
    ])[0]

    assert before['canonicalFixtureId'] == after['canonicalFixtureId']


def test_cross_provider_public_id_is_deterministic_regardless_of_input_order():
    espn = fixture('espn', '401')
    football_data = fixture('football-data', '9001', '2026-08-03T19:02:00Z')

    first = merge_fixtures([espn, football_data])[0]
    second = merge_fixtures([deepcopy(football_data), deepcopy(espn)])[0]

    assert first['canonicalFixtureId'] == second['canonicalFixtureId']


def test_fixture_without_provider_event_identity_is_rejected():
    match = unmapped_fixture('401001')
    match['providerIds'] = {}

    with pytest.raises(ValueError, match='provider event identity'):
        merge_fixtures([match])
