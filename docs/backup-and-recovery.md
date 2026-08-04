# Backup and recovery

## Ownership and objectives

The production owner is responsible for PostgreSQL backup configuration, access review, success monitoring, and restore rehearsal. Initial targets for the fixture-identity foundation are:

- recovery point objective (RPO): 24 hours;
- recovery time objective (RTO): 4 hours;
- backup retention: at least 14 daily recovery points;
- restore rehearsal: quarterly and before a high-risk migration when the latest rehearsal is stale.

These are operating targets, not evidence that Railway backups are currently enabled. Record the configured schedule, retention, encryption/access controls, and latest successful restore in release evidence before declaring disaster recovery ready.

## PostgreSQL

Enable automated encrypted backups or an equivalent controlled export process. Restrict backup and restore access to production operators, monitor every scheduled result, and alert on missed or failed backups. Backups must include all Alembic-managed tables and migration state.

Before a destructive or long-running migration, capture an additional recovery point. Do not overwrite the only production database during a restore test.

## Restore rehearsal

1. Select and record a backup recovery point without exposing its credentials.
2. Restore it into a new isolated PostgreSQL service in a non-production environment.
3. Point a staging application at the restored database and a staging Redis service.
4. Run `alembic current`, then apply any forward migrations required by the tested application revision.
5. Verify table presence, alias referential integrity, unresolved-report access, deep-link lookup, fixture uniqueness, readiness, and full smoke.
6. Record start/end time, achieved RPO/RTO, row-count checks, revision, errors, and operator.
7. Remove the rehearsal resources only after explicit approval and evidence capture.

## Production recovery

Preserve the damaged service for investigation. Restore the selected recovery point into a new PostgreSQL service, validate it using the rehearsal checks, then update the `web` service reference and deploy. Keep the prior service until recovery is accepted. Never assume application rollback reverses schema or data loss.

## Redis

Redis holds reproducible cache and coordination state, so this foundation does not require Redis backups. Loss of Redis may reduce availability and triggers failed readiness, but the application can repopulate cache from providers while fixture identities remain in PostgreSQL. Durable accounts, consent, notification jobs, or device tokens must never be stored only in Redis; if future queue semantics require recovery, revise this decision before release.

## Configuration and deletion

Keep a non-secret inventory of required variable names, service references, domains, and commands in source control. Store actual credentials only in sealed operational systems and Railway. Backup retention may delay physical removal of deleted future user data; document that behavior before accounts are introduced and never promise immediate removal from retained backups without verification.
