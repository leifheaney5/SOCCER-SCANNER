from soccer_scanner.ranking.featured_match import select_featured_match


def match(identifier, status, kickoff, *, teams=(), interest=0):
    return {
        'canonicalFixtureId': identifier,
        'utcDate': kickoff,
        'status': {'code': status},
        'homeTeam': {'canonicalId': teams[0] if teams else 'home'},
        'awayTeam': {'canonicalId': teams[1] if len(teams) > 1 else 'away'},
        'interestEstimate': interest,
    }


def test_featured_ranking_prefers_favorite_live_then_other_live():
    matches = [
        match('other-live', 'in_progress', '2026-08-03T19:00:00Z'),
        match('favorite-live', 'half_time', '2026-08-03T20:00:00Z', teams=('arsenal', 'chelsea')),
        match('favorite-upcoming', 'scheduled', '2026-08-03T18:00:00Z', teams=('arsenal', 'city')),
    ]

    assert select_featured_match(matches, favorite_team_ids={'arsenal'})['canonicalFixtureId'] == 'favorite-live'
    assert select_featured_match(matches)['canonicalFixtureId'] == 'other-live'


def test_featured_ranking_is_deterministic_for_upcoming_and_finished_matches():
    upcoming = [
        match('later-interesting', 'scheduled', '2026-08-03T21:00:00Z', interest=80),
        match('sooner', 'scheduled', '2026-08-03T20:00:00Z', interest=10),
    ]
    finished = [
        match('older', 'finished', '2026-08-03T16:00:00Z'),
        match('recent', 'finished', '2026-08-03T18:00:00Z'),
    ]

    assert select_featured_match(upcoming)['canonicalFixtureId'] == 'sooner'
    assert select_featured_match(finished)['canonicalFixtureId'] == 'recent'
