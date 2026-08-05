# Deployment and operations

## Production command

The repository `Procfile` runs:

```text
gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-2} --timeout 30 wsgi:app
```

Do not use Flask's development server in production.

## Railway

Production is connected to the GitHub `main` branch and served at `https://soccerscanner.pro`. Configure:

- `APP_ENVIRONMENT=production`
- `PUBLIC_BASE_URL=https://soccerscanner.pro`
- `TRUSTED_PROXY_HOPS=1`
- `DATABASE_URL=${{Postgres.DATABASE_URL}}` from a private Railway PostgreSQL service
- `REDIS_URL=${{Redis.REDIS_URL}}` from a private Railway Redis service
- a high-entropy sealed `OPS_ADMIN_TOKEN`
- `RAILPACK_PYTHON_VERSION=3.13.14`
- optional `FOOTBALL_DATA_API_KEY` for declared team/squad/standings capabilities
- optional `WEB_CONCURRENCY`, normally `2`

Railway supplies `PORT`, `RAILWAY_GIT_COMMIT_SHA`, `RAILWAY_ENVIRONMENT_NAME`, and deployment timestamp metadata. Production startup intentionally fails if neither the explicit nor Railway commit SHA is valid.

The checked-in `railway.json` runs `alembic upgrade head` in Railway's pre-deploy container, starts Gunicorn explicitly, and gates activation on `/health/ready`. Do not run migrations inside each web replica.

## Release procedure

1. Run all commands in [testing](testing.md) from a clean worktree.
2. Review the migration and take a backup before any high-risk database change.
3. Push the reviewed commit series to `main`.
4. Confirm the pre-deploy migration completed and observe Railway until the deployment reaches terminal `SUCCESS`; a Git push alone is not deployment evidence.
5. Record the deployment ID, Alembic revision, and `git rev-parse HEAD`.
6. Run:

   ```powershell
   $env:BASE_URL='https://soccerscanner.pro'
   $env:EXPECTED_SHA=(git rev-parse HEAD)
   npm run smoke:production
   ```

7. Confirm `/health/version` and `/health/ready` report the exact full SHA and `production`; readiness must show durable database/schema and shared Redis as ready.
8. Confirm the worktree is clean and `main` equals `origin/main`.

## Cache operations

Without `REDIS_URL`, the service uses bounded in-memory caching. This is acceptable for local development. Production readiness returns 503 because workers cannot coordinate or share warm results. Redis failure still degrades request handling to memory, while keeping the instance out of ready rotation until shared coordination recovers.

The cache stores provider-normalized fixture ranges, canonical fixture lookups, and only spoiler-sanitized browser offline snapshots. API responses themselves carry `Cache-Control: no-store`.

## Provider operation

ESPN is the default fixture source and requires no configured key. Football-Data.org is disabled when its key is absent; the capability endpoint reports affected features as `unavailable`. Provider outages can yield partial current data or bounded stale data. A confirmed empty day requires a successful authoritative provider response.

Never put provider credentials in client code, logs, screenshots, build artifacts, or committed environment files.

## Provider redundancy

As of 2026-08-05 neither `production` nor `staging` sets `FOOTBALL_DATA_API_KEY`,
so ESPN is the only fixture source. A verified production outage on 2026-08-05
returned `provider_unavailable` from `/api/v2/fixtures` while `/health/ready`
continued reporting `ready`.

Set `FOOTBALL_DATA_API_KEY` on both Railway services to activate the fallback.
`/health/providers` reports `singleProvider: true` until a second provider is
usable.

Note: `lastSuccessAt` is stamped on every request that serves that provider's
data, including a cache hit, not only on an actual upstream call. It means
"this provider's data last served a request", not "the provider was last
reached upstream". Skew between the two is bounded by `FIXTURE_CACHE_TTL`
(60s in production).

## Rollback

Use Railway's deployment history to redeploy the last known-good commit only when its schema expectations remain compatible with the migrated database. Alembic downgrades are not an automatic rollback mechanism. Follow [database migrations](database-migrations.md) and [backup and recovery](backup-and-recovery.md), then run production smoke with the rollback SHA.

## Operational checks

- `/health/live` returning 200 proves process liveness only.
- `/health/ready` shows build, database/schema, and cache state; critical production dependency degradation returns 503.
- `/health/metrics` exposes request, error, rate-limit, provider, cache, and timing aggregates for diagnosis.
- Provider error bodies remain generic; use structured server logs and request IDs to correlate failures.

Detailed procedures: [Railway deployment](railway-deployment.md) and [Railway runbook](railway-runbook.md).
