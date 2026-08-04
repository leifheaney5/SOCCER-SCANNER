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
- `REDIS_URL` from a Railway Redis service for cross-worker cache and single-flight coordination
- optional `FOOTBALL_DATA_API_KEY` for declared team/squad/standings capabilities
- optional `WEB_CONCURRENCY`, normally `2`

Railway supplies `PORT`, `RAILWAY_GIT_COMMIT_SHA`, `RAILWAY_ENVIRONMENT_NAME`, and deployment timestamp metadata. Production startup intentionally fails if neither the explicit nor Railway commit SHA is valid.

## Release procedure

1. Run all commands in [testing](testing.md) from a clean worktree.
2. Push the reviewed commit series to `main`.
3. Observe Railway until the deployment reaches terminal `SUCCESS`; a Git push alone is not deployment evidence.
4. Record the deployment ID and `git rev-parse HEAD`.
5. Run:

   ```powershell
   $env:BASE_URL='https://soccerscanner.pro'
   $env:EXPECTED_SHA=(git rev-parse HEAD)
   npm run smoke:production
   ```

6. Confirm `/health/version` and `/health/ready` report the exact full SHA and `production`, and that HTML JS/CSS tokens equal its first 12 characters.
7. Confirm the worktree is clean and `main` equals `origin/main`.

## Cache operations

Without `REDIS_URL`, the service uses bounded in-memory caching. This is acceptable for local development. In production, readiness reports the memory cache as degraded because workers cannot coordinate or share warm results. Redis failure also degrades to memory so fixture availability is favored over cache dependence.

The cache stores provider-normalized fixture ranges, canonical fixture lookups, and only spoiler-sanitized browser offline snapshots. API responses themselves carry `Cache-Control: no-store`.

## Provider operation

ESPN is the default fixture source and requires no configured key. Football-Data.org is disabled when its key is absent; the capability endpoint reports affected features as `unavailable`. Provider outages can yield partial current data or bounded stale data. A confirmed empty day requires a successful authoritative provider response.

Never put provider credentials in client code, logs, screenshots, build artifacts, or committed environment files.

## Rollback

Use Railway's deployment history to redeploy the last known-good commit. After rollback reaches `SUCCESS`, run production smoke with that rollback SHA. The build-derived asset token and service-worker cache name ensure clients move to the rollback's immutable shell.

## Operational checks

- `/health/live` returning 200 proves process liveness only.
- `/health/ready` also shows build and cache state; `cache.status=degraded` requires operator attention even when HTTP status is 200.
- `/health/metrics` exposes request, error, rate-limit, provider, cache, and timing aggregates for diagnosis.
- Provider error bodies remain generic; use structured server logs and request IDs to correlate failures.
