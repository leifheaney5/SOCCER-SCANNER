import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest


def repository_types():
    try:
        database = importlib.import_module('soccer_scanner.persistence.database')
        identities = importlib.import_module('soccer_scanner.persistence.fixture_identities')
    except ModuleNotFoundError as error:
        pytest.fail(f'Fixture identity persistence is not implemented: {error}')
    return (
        database.DatabaseRuntime,
        database.Base,
        database.SchemaMetadata,
        identities.FixtureIdentityRepository,
    )


def fixture(
    provider,
    event_id,
    *,
    kickoff='2026-08-04T19:00:00Z',
    competition='league-a',
    home='club-a-us',
    away='club-b-us',
    mapped=True,
):
    canonical = (lambda value: value) if mapped else (lambda _value: None)
    return {
        'providerIds': {provider: event_id},
        'utcDate': kickoff,
        'competition': {
            'canonicalId': canonical(competition),
            'provider': provider,
            'providerId': f'{provider}-competition',
            'providerIds': {provider: f'{provider}-competition'},
            'name': 'League A',
        },
        'homeTeam': {
            'canonicalId': canonical(home),
            'provider': provider,
            'providerId': f'{provider}-{home}',
            'providerIds': {provider: f'{provider}-{home}'},
            'name': 'United',
        },
        'awayTeam': {
            'canonicalId': canonical(away),
            'provider': provider,
            'providerId': f'{provider}-{away}',
            'providerIds': {provider: f'{provider}-{away}'},
            'name': 'City',
        },
        'season': {'year': 2026},
        'stage': 'regular-season',
    }


def create_repository(database_path):
    DatabaseRuntime, Base, SchemaMetadata, Repository = repository_types()
    runtime = DatabaseRuntime.from_config({
        'DATABASE_URL': f'sqlite:///{database_path.as_posix()}',
        'DATABASE_POOL_SIZE': 2,
        'DATABASE_MAX_OVERFLOW': 0,
    })
    Base.metadata.create_all(runtime.engine)
    with runtime.session_scope() as session:
        if session.get(SchemaMetadata, 'schema_version') is None:
            session.add(SchemaMetadata(
                key='schema_version',
                value='20260804_01',
            ))
    return runtime, Repository(runtime)


def test_provider_alias_survives_repository_recreation_and_kickoff_change(tmp_path):
    database_path = tmp_path / 'identity.db'
    runtime, repository = create_repository(database_path)
    original = fixture('espn', '401001')
    public_id = repository.resolve([original], original)
    runtime.dispose()

    runtime, repository = create_repository(database_path)
    corrected = fixture('espn', '401001', kickoff='2026-08-04T19:45:00Z')

    assert repository.resolve([corrected], corrected) == public_id
    assert repository.get(public_id)['kickoffUtc'] == '2026-08-04T19:45:00+00:00'
    runtime.dispose()


def test_new_cross_provider_alias_joins_one_unambiguous_canonical_fixture(tmp_path):
    runtime, repository = create_repository(tmp_path / 'identity.db')
    espn = fixture('espn', '401001')
    football_data = fixture(
        'football-data',
        '9001',
        kickoff='2026-08-04T19:05:00Z',
    )
    public_id = repository.resolve([espn], espn)

    assert repository.resolve([football_data], football_data) == public_id
    assert repository.resolve([espn, football_data], espn) == public_id
    runtime.dispose()


def test_new_mapping_reconciles_existing_provider_ids_and_keeps_old_public_alias(tmp_path):
    runtime, repository = create_repository(tmp_path / 'identity.db')
    unresolved_espn = fixture('espn', '401001', mapped=False)
    unresolved_football = fixture('football-data', '9001', mapped=False)
    espn_public_id = repository.resolve([unresolved_espn], unresolved_espn)
    football_public_id = repository.resolve([unresolved_football], unresolved_football)
    assert espn_public_id != football_public_id

    mapped_espn = fixture('espn', '401001')
    mapped_football = fixture('football-data', '9001')
    survivor = repository.resolve([mapped_espn, mapped_football], mapped_espn)
    superseded = (
        football_public_id if survivor == espn_public_id else espn_public_id
    )

    assert repository.resolve_public_alias(superseded) == survivor
    assert repository.resolve([mapped_football], mapped_football) == survivor
    runtime.dispose()


def test_reversed_teams_and_same_display_name_in_different_countries_stay_distinct(tmp_path):
    runtime, repository = create_repository(tmp_path / 'identity.db')
    original = fixture('espn', '401001')
    reversed_sides = fixture(
        'football-data',
        '9001',
        home='club-b-us',
        away='club-a-us',
    )
    another_country = fixture(
        'espn',
        '401002',
        home='club-a-ca',
        away='club-b-ca',
    )

    ids = {
        repository.resolve([original], original),
        repository.resolve([reversed_sides], reversed_sides),
        repository.resolve([another_country], another_country),
    }

    assert len(ids) == 3
    runtime.dispose()


def test_unresolved_entities_are_counted_without_score_or_fixture_payload(tmp_path):
    runtime, repository = create_repository(tmp_path / 'identity.db')
    unresolved = fixture('espn', '401001', mapped=False)
    repository.resolve([unresolved], unresolved)

    report = repository.unresolved_report(limit=10)

    assert report['total'] == 3
    assert {item['kind'] for item in report['items']} == {
        'competition',
        'team',
    }
    assert all('score' not in item for item in report['items'])
    assert all('fixture' not in item for item in report['items'])
    assert all(item['lastSeenAt'].endswith('+00:00') for item in report['items'])
    runtime.dispose()


def test_repository_health_reports_schema_and_database_state(tmp_path):
    runtime, repository = create_repository(tmp_path / 'identity.db')

    health = repository.health()

    assert health == {
        'backend': 'database',
        'reachable': True,
        'schemaVersion': '20260804_01',
        'status': 'ready',
    }
    runtime.dispose()


def test_concurrent_first_observation_returns_one_public_identity(tmp_path):
    database_path = tmp_path / 'identity.db'
    first_runtime, first_repository = create_repository(database_path)
    second_runtime, second_repository = create_repository(database_path)
    start = Barrier(2)

    def resolve(repository):
        match = fixture('espn', '401001')
        start.wait(timeout=5)
        return repository.resolve([match], match)

    with ThreadPoolExecutor(max_workers=2) as executor:
        public_ids = list(executor.map(
            resolve,
            (first_repository, second_repository),
        ))

    assert len(set(public_ids)) == 1
    first_runtime.dispose()
    second_runtime.dispose()
