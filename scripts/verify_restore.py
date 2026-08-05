#!/usr/bin/env python
"""Verify a restored PostgreSQL recovery point before it is promoted.

A restore is not proven by the dashboard reporting success. This script asserts
the schema revision, the presence of the identity tables, and the fixture-ID
uniqueness invariant that the durable identity registry exists to guarantee.

Usage:
    python scripts/verify_restore.py --database-url postgresql+psycopg://...

Exit status is 0 only when every check passes, so it can gate a rehearsal.
"""

import argparse
import json
import sys

from sqlalchemy import create_engine, inspect, text

EXPECTED_SCHEMA_VERSION = '20260804_01'
REQUIRED_TABLES = ('fixture_identities', 'fixture_identity_aliases', 'schema_metadata')


def _check(results, name, passed, detail):
    results.append({'check': name, 'passed': bool(passed), 'detail': detail})
    return passed


def verify(database_url, *, expected_version=EXPECTED_SCHEMA_VERSION):
    engine = create_engine(database_url)
    results = []
    with engine.connect() as connection:
        # Dialect-agnostic so the same verifier runs against a restored
        # PostgreSQL service and against a local rehearsal fixture.
        present = set(inspect(connection).get_table_names())
        missing = [name for name in REQUIRED_TABLES if name not in present]
        _check(results, 'required_tables', not missing,
               f'missing={missing}' if missing else 'all identity tables present')

        alembic_version = None
        if 'alembic_version' in present:
            row = connection.execute(text('SELECT version_num FROM alembic_version')).fetchone()
            alembic_version = row[0] if row else None
        _check(results, 'alembic_revision', alembic_version == expected_version,
               f'found={alembic_version} expected={expected_version}')

        if 'fixture_identities' in present:
            total = connection.execute(
                text('SELECT COUNT(*) FROM fixture_identities')
            ).scalar_one()
            distinct = connection.execute(
                text('SELECT COUNT(DISTINCT canonical_fixture_id) FROM fixture_identities')
            ).scalar_one()
            # The whole point of the durable registry: one row per public ID.
            _check(results, 'fixture_id_uniqueness', total == distinct,
                   f'rows={total} distinct_canonical_ids={distinct}')
            _check(results, 'fixture_identities_not_empty', total > 0,
                   f'rows={total}')
        else:
            _check(results, 'fixture_id_uniqueness', False, 'table absent')

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', required=True,
                        help='SQLAlchemy URL of the RESTORED database, never production.')
    parser.add_argument('--expected-version', default=EXPECTED_SCHEMA_VERSION)
    parser.add_argument('--json', action='store_true', help='Emit machine-readable output.')
    args = parser.parse_args(argv)

    results = verify(args.database_url, expected_version=args.expected_version)
    passed = all(item['passed'] for item in results)

    if args.json:
        print(json.dumps({'passed': passed, 'checks': results}, indent=2))
    else:
        for item in results:
            print(f"[{'PASS' if item['passed'] else 'FAIL'}] {item['check']}: {item['detail']}")
        print(f"\nRestore verification: {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
