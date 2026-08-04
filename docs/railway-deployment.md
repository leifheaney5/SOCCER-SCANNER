# Railway deployment

## Required production resources

Before deploying, inspect the selected project and environment. Reuse a suitable existing service; never retry an ambiguous create without listing services again.

Production requires:

- one public `web` service;
- one private managed PostgreSQL service;
- one private managed Redis service;
- `DATABASE_URL` referencing `${{Postgres.DATABASE_URL}}` using the exact PostgreSQL service name;
- `REDIS_URL` referencing `${{Redis.REDIS_URL}}` using the exact Redis service name;
- sealed `OPS_ADMIN_TOKEN` and any provider credentials;
- `APP_ENVIRONMENT=production`, `PUBLIC_BASE_URL=https://soccerscanner.pro`, `TRUSTED_PROXY_HOPS=1`, and `RAILPACK_PYTHON_VERSION=3.13.14`.

Railway injects `PORT`, deployment metadata, and the Git commit SHA. Never replace those with guessed values.

## Staging gate

Create staging with its own PostgreSQL and Redis data. Set `APP_ENVIRONMENT=staging` and a staging public origin. Apply the migration to staging, wait for terminal deployment success, and run the full remote smoke suite. Inspect readiness, runtime logs, identity uniqueness on a busy date, and Alembic revision before production promotion.

## Production release

1. Start from a clean reviewed branch and run the full matrix in [testing](testing.md).
2. Confirm the migration is backward-compatible with both the old and new application revisions.
3. Confirm the latest automated PostgreSQL backup succeeded; take an additional pre-change backup for a high-risk migration.
4. Deploy the reviewed commit to the explicitly selected production `web` service.
5. Poll the scoped deployment until Railway reports terminal `SUCCESS`. A queued or building deployment is not success.
6. Confirm pre-deploy logs show `alembic upgrade head` completed once.
7. Run `npm run smoke:production` with `EXPECTED_SHA` set to the exact deployed commit.
8. Confirm `/health/ready` reports `database.status=ready`, `database.durable=true`, `cache.backend=redis`, `cache.shared=true`, and no blocking reasons.
9. Compare total fixtures with unique `canonicalFixtureId` count on a busy date and repeat the request to confirm stability.
10. Record deployment ID, full SHA, schema revision, smoke result, and any operator follow-up.

## Rollback

Redeploy the last known-good application revision only when it is compatible with the current schema. Expand-and-contract migrations should keep that path open. Do not automatically run `alembic downgrade`; a database rollback requires a reviewed recovery decision and may require restoring into a new PostgreSQL service.

If Railway no longer retains the desired deployment, deploy the recorded Git SHA from source. After any rollback, wait for terminal success, verify readiness and schema compatibility, and run smoke against the rollback SHA.

## Secret rotation

Rotate one credential at a time through sealed Railway variables. For a bearer token, update the service variable, let Railway redeploy, verify the new token, then revoke the old distribution. For provider credentials, verify the capability state and provider error rate. Database credential rotation must be coordinated with the managed service and followed by connection/readiness checks. Never print values in logs or release evidence.
