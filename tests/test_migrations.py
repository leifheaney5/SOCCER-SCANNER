import os
from pathlib import Path
import sqlite3
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrades_an_empty_database_to_fixture_identity_schema(tmp_path):
    database_path = tmp_path / 'migration.db'
    environment = {
        **os.environ,
        'DATABASE_URL': f'sqlite:///{database_path.as_posix()}',
    }
    result = subprocess.run(
        [sys.executable, '-m', 'alembic', '-c', 'alembic.ini', 'upgrade', 'head'],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        schema_version = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()

    assert {
        'alembic_version',
        'fixture_identities',
        'fixture_provider_aliases',
        'fixture_public_aliases',
        'identity_resolution_issues',
        'schema_metadata',
    } <= tables
    assert schema_version == ('20260804_01',)
