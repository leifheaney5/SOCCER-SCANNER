# Database migrations

Alembic is the sole production schema-change mechanism. SQLAlchemy model creation is used only for the disposable SQLite fallback; a correctly configured production service never calls `create_all`.

## Rules

- Generate and review an explicit revision for every schema change.
- Use expand-and-contract changes: add compatible structures first, backfill separately, switch readers/writers, and remove obsolete structures in a later release.
- Keep migrations deterministic, bounded, and safe to retry where practical.
- Never run migrations concurrently in every web replica.
- Never seed or delete production data implicitly during application startup.
- Record the expected schema revision and expose compatibility through readiness.
- Test upgrades on an empty database and on a production-like staging copy.

## Local validation

```powershell
$env:DATABASE_URL='sqlite:///migration-check.db'
alembic upgrade head
alembic current
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_migrations.py tests/test_fixture_identity_repository.py -q
```

Use a disposable path and remove it only after confirming it is not a working database.

## Railway ordering

The `web` service's `railway.json` runs `alembic upgrade head` in pre-deploy. Railway must complete it before starting the new application. The command connects to durable PostgreSQL through `DATABASE_URL`; it does not depend on a filesystem volume.

For a high-risk migration, confirm a recent backup and successful restore rehearsal, run against staging first, inspect locks and duration, and schedule an operator window. If a migration fails, Railway must not activate the incompatible application deployment.

## Rollback behavior

Application rollback is preferred when the migrated schema remains backward-compatible. `alembic downgrade` is never automatic and is not assumed safe. A destructive or data-transforming rollback requires a reviewed reverse migration or restoration into a new PostgreSQL service, followed by integrity and application smoke checks.

The initial revision `20260804_01` creates the fixture identity, provider alias, public alias, unresolved issue, and schema metadata tables.
