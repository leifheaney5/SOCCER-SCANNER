# Railway architecture

## Verified baseline on 2026-08-04

The production project had one `production` environment and one public `web` service. It had no PostgreSQL, Redis, worker, cron, staging environment, volume, bucket, pre-deploy command, or deployment health-check path. The web service ran two Gunicorn workers, so its process-local cache could not coordinate fixture fills or retain aliases across restarts.

This is a dated evidence snapshot, not a promise about current Railway state. Re-run the topology inventory before every infrastructure change.

## Target foundation

```text
Internet
   |
   v
web (only public service)
   |-- private DATABASE_URL --> PostgreSQL
   `-- private REDIS_URL -----> Redis
```

- `web` owns Flask pages, the versioned API, readiness, and bounded provider requests.
- PostgreSQL is the durable source of fixture public IDs, provider aliases, public aliases, schema state, and unresolved identity issues.
- Redis is disposable shared cache and single-flight coordination. It is not a source of truth.
- PostgreSQL and Redis remain private and have no public TCP proxy unless a separately approved operational need exists.
- No persistent volume is attached to `web`; deployments remain stateless.
- A worker and scheduler are intentionally absent from this foundation because no durable background-job path exists yet. Notification delivery, reconciliation, and cleanup must move to dedicated private services before those features ship.

## Environments

`staging` and `production` use separate PostgreSQL, Redis, variables, secrets, and data. Staging is the migration and smoke-test gate; it must never reference mutable production persistence. Local development uses disposable SQLite and memory cache unless the developer explicitly supplies local services.

Only production serves `soccerscanner.pro`. Staging uses a separate Railway domain or staging subdomain and is not a canonical public origin.

## Deployment lifecycle

1. Railpack builds the pinned Python runtime and locked dependencies.
2. Railway runs `alembic upgrade head` once in pre-deploy against PostgreSQL.
3. Railway starts Gunicorn on its injected `PORT`.
4. `/health/ready` verifies required internal services, durable schema-current persistence, and shared Redis.
5. Railway activates the deployment only after readiness passes.
6. Independent production smoke verifies the exact full commit SHA and fixture-ID uniqueness.

External soccer-provider availability never gates readiness. Provider failures are handled as typed partial, stale, rate-limited, or unavailable outcomes after traffic is accepted.

## Configuration ownership

`railway.json` owns the `web` service builder, migration command, start command, health check, and restart policy. Railway owns service resources and variables. Do not commit connection strings or secrets, and do not configure the same service with a second Config-as-Code format.

See [Railway deployment](railway-deployment.md), [runbook](railway-runbook.md), and [database migrations](database-migrations.md).
