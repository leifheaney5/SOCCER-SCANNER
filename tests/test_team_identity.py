import json

from soccer_scanner.services.team_identity import TeamIdentityResolver


def resolver(tmp_path, teams):
    path = tmp_path / 'teams.json'
    path.write_text(json.dumps({'teams': teams}), encoding='utf-8')
    return TeamIdentityResolver.from_file(path)


def test_resolves_by_qualified_provider_id_and_emits_all_known_ids(tmp_path):
    identities = resolver(tmp_path, [{
        'canonicalId': 'arsenal',
        'name': 'Arsenal',
        'aliases': ['Arsenal FC'],
        'providerIds': {'espn': '359', 'football-data': '57'},
    }])

    result = identities.resolve('espn', '359', 'Arsenal FC')

    assert result.canonicalId == 'arsenal'
    assert result.provider == 'espn'
    assert result.providerId == '359'
    assert result.providerIds == {'espn': '359', 'football-data': '57'}


def test_unique_maintained_alias_is_unicode_case_and_punctuation_insensitive(tmp_path):
    identities = resolver(tmp_path, [{
        'canonicalId': 'sao-paulo',
        'name': 'São Paulo',
        'aliases': ['São Paulo FC'],
        'providerIds': {'espn': '2026'},
    }])

    result = identities.resolve('espn', 'new-id', 'SAO-PAULO F.C.')

    assert result.canonicalId == 'sao-paulo'
    assert result.providerId == 'new-id'


def test_ambiguous_alias_does_not_guess(tmp_path):
    identities = resolver(tmp_path, [
        {
            'canonicalId': 'united-a',
            'name': 'United',
            'aliases': [],
            'providerIds': {'espn': '1'},
        },
        {
            'canonicalId': 'united-b',
            'name': 'United',
            'aliases': [],
            'providerIds': {'football-data': '2'},
        },
    ])

    result = identities.resolve('espn', 'not-mapped', 'United')

    assert result.canonicalId is None
    assert result.providerIds == {'espn': 'not-mapped'}


def test_unknown_and_malformed_teams_remain_provider_qualified(tmp_path):
    identities = resolver(tmp_path, [])

    unknown = identities.resolve('espn', '999', 'Unknown Athletic')
    malformed = identities.resolve('', '', '')

    assert unknown.canonicalId is None
    assert unknown.providerIds == {'espn': '999'}
    assert malformed.canonicalId is None
    assert malformed.provider is None
    assert malformed.providerIds == {}


def test_canonical_provider_lookup_never_accepts_raw_provider_ids(tmp_path):
    identities = resolver(tmp_path, [{
        'canonicalId': 'arsenal',
        'name': 'Arsenal',
        'aliases': [],
        'providerIds': {'espn': '359', 'football-data': '57'},
    }])

    assert identities.provider_id('arsenal', 'football-data') == '57'
    assert identities.provider_id('359', 'football-data') is None
    assert identities.provider_id('57', 'football-data') is None
