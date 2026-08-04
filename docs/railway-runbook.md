# Railway runbook

## Fast triage

1. Check `/health/live`. A failure means the process or routing path is unavailable.
2. Check `/health/ready`. Use `blocking`, `database`, and `cache` to identify the internal dependency.
3. Check `/health/version` and compare the full SHA with the intended deployment.
4. Inspect the explicitly scoped Railway deployment state and bounded runtime logs.
5. Do not use soccer-provider availability as a reason to restart a healthy service; inspect typed provider outcomes and cache state first.

## Readiness failures

| Blocking reason | Meaning | Operator action |
|---|---|---|
| `database_not_durable` | Production started without configured durable persistence | Verify the `DATABASE_URL` service reference and redeploy |
| `database_not_ready` | Connection failed or schema version differs from the application | Inspect PostgreSQL and pre-deploy migration logs; do not serve traffic until corrected |
| `shared_cache_not_ready` | Redis is absent, unreachable, or using memory fallback | Inspect the Redis service/reference; request handling may degrade locally but the replica remains unready |
| `missing_service:*` | Application composition is incomplete | Treat as a release defect and roll back or repair the build |

Readiness performs cheap internal checks and must not contact ESPN or Football-Data.org.

## Fixture identity incident

Symptoms include duplicate public IDs, deep links resolving to the wrong match, or a uniqueness-invariant error.

1. Stop promotion and preserve the response, request ID, date, timezone, deployed SHA, and provider identifiers without scores or credentials.
2. Confirm the response fixture count equals the unique public-ID count.
3. Query `GET /api/internal/identity-report` with the protected bearer credential. Use a bounded `limit`; the endpoint is read-only.
4. Inspect provider aliases and public aliases transactionally. Do not edit production rows ad hoc.
5. Add a deterministic regression fixture before changing matching rules.
6. Deploy through staging and repeat the busy-date and deep-link checks.

## Provider incident

Use response `state`, provider status, request count, failure categories, request ID, and bounded logs. `partial` or `stale` data is valid degraded behavior. Do not translate a provider outage into an empty schedule, expose raw exception text, or disable spoiler protection while debugging.

## Database incident

If PostgreSQL is unreachable, the instance must remain unready. Check managed-service health, private references, pool saturation, and migration state. For corruption or accidental data loss, preserve the affected service and restore the selected backup into a new service first; follow [backup and recovery](backup-and-recovery.md).

## Redis incident

Redis contains reproducible cache state. Restore connectivity or replace the service, then allow the application to repopulate keys. Do not restore PostgreSQL from Redis and do not treat cache recovery as identity recovery.

## Operations credential incident

Rotate `OPS_ADMIN_TOKEN` immediately, redeploy, verify rejection of the old token and acceptance of the new token, and review access logs by request ID. The endpoint has no destructive operation.

## Release evidence

Record the environment, service, deployment ID, exact SHA, schema revision, readiness payload, smoke result, fixture/unique-ID counts, backup state, and rollback candidate. Omit secrets, connection strings, provider payloads, and scores.
