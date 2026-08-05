import unittest

from sqlalchemy import create_engine, text

from scripts.verify_restore import verify


def build_database(url, *, version='20260804_01', canonical_ids=('fx_a', 'fx_b')):
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE schema_metadata (key VARCHAR, value VARCHAR)'))
        connection.execute(text('CREATE TABLE fixture_identity_aliases (alias VARCHAR)'))
        connection.execute(text(
            'CREATE TABLE fixture_identities (id INTEGER PRIMARY KEY, canonical_fixture_id VARCHAR)'
        ))
        connection.execute(
            text('INSERT INTO alembic_version (version_num) VALUES (:version)'),
            {'version': version},
        )
        for index, canonical_id in enumerate(canonical_ids):
            connection.execute(
                text('INSERT INTO fixture_identities (id, canonical_fixture_id) VALUES (:i, :c)'),
                {'i': index, 'c': canonical_id},
            )
    return engine


def outcome(results, name):
    return next(item for item in results if item['check'] == name)['passed']


class VerifyRestoreTest(unittest.TestCase):
    def test_a_healthy_restore_passes_every_check(self):
        url = 'sqlite://'
        engine = build_database(url)

        results = verify_with_engine(engine)

        self.assertTrue(all(item['passed'] for item in results), results)

    def test_a_stale_schema_revision_fails_verification(self):
        engine = build_database('sqlite://', version='20250101_00')

        results = verify_with_engine(engine)

        self.assertFalse(outcome(results, 'alembic_revision'))

    def test_duplicate_canonical_ids_fail_the_uniqueness_invariant(self):
        # A restore that reintroduces duplicate public IDs must never be promoted.
        engine = build_database('sqlite://', canonical_ids=('fx_a', 'fx_a'))

        results = verify_with_engine(engine)

        self.assertFalse(outcome(results, 'fixture_id_uniqueness'))

    def test_an_empty_identity_table_is_reported(self):
        engine = build_database('sqlite://', canonical_ids=())

        results = verify_with_engine(engine)

        self.assertFalse(outcome(results, 'fixture_identities_not_empty'))


def verify_with_engine(engine):
    """Run the verifier against an already-open in-memory engine.

    SQLite in-memory databases vanish when the connection closes, so the test
    reuses one engine rather than reconnecting by URL.
    """
    import scripts.verify_restore as module

    original = module.create_engine
    module.create_engine = lambda url: engine
    try:
        return module.verify('sqlite://')
    finally:
        module.create_engine = original


if __name__ == '__main__':
    unittest.main()
