# Backup and recovery

**Current status: NOT CONFIGURED.** As of 2026-08-04 no backup schedule is enabled on any
Soccer Scanner volume. This document is the procedure to enable it and the evidence that
must be captured afterwards. Do not describe disaster recovery as operational until the
evidence section at the bottom is filled in.

## Why this cannot be automated from this repository

Railway exposes backup configuration **only in the dashboard**. Verified 2026-08-04:

- `railway volume update` accepts only `--mount-path` and `--name`.
- `railway volume list --json` returns no backup, schedule, or retention field.
- The Railway MCP `update_volume` tool accepts only `volume_id`, `name`, `mount_path`,
  `service_id`, `environment_id`.

There is therefore no CLI, API, or infrastructure-as-code path. Enabling backups is a
manual operator action. Everything else on this page — verification, rehearsal, and
evidence — is automated and lives in `scripts/verify_restore.py`.

## What Railway actually provides

Per Railway's backup reference:

| Schedule | Frequency | Retention |
| --- | --- | --- |
| Daily | every 24 hours | kept 6 days |
| Weekly | every 7 days | kept 1 month |
| Monthly | every 30 days | kept 3 months |

Multiple schedules can run on one volume simultaneously, and manual backups can be
triggered on demand (limited to 50% of the volume's total size).

**Correction to previous documentation:** an earlier revision of this page targeted
"at least 14 daily recovery points". That is **not achievable** on Railway — the daily
schedule retains 6. The objectives below have been restated to what the platform can
actually deliver.

## Objectives (achievable on Railway)

| Objective | Target | Basis |
| --- | --- | --- |
| RPO | 24 hours | daily schedule |
| RTO | 4 hours | restore + verify + service re-reference |
| Short-term recovery points | 6 (daily) | platform retention |
| Medium-term recovery points | ~4 (weekly, 1 month) | platform retention |
| Long-term recovery points | ~3 (monthly, 3 months) | platform retention |
| Rehearsal cadence | quarterly, and before any destructive migration | policy |

## Required configuration

Enable **all three schedules** on the production PostgreSQL volume. They are additive and
together give same-week, same-month, and same-quarter recovery points.

Target volume — production:

| Field | Value |
| --- | --- |
| Project | `soccer-scanner` (`933a7441-1b02-440a-b5a4-7e639a8584db`) |
| Environment | `production` (`ec80c102-87e2-4edf-88c1-c563e827dc8b`) |
| Service | `Postgres` |
| Mount path | `/var/lib/postgresql/data` |

### Operator steps

1. Open the Railway dashboard → project `soccer-scanner` → environment `production`.
2. Select the `Postgres` service → **Settings** → **Backups** tab.
3. Enable **Daily**, **Weekly**, and **Monthly**.
4. Trigger one **manual backup** immediately so a recovery point exists before the first
   scheduled run.
5. Record the configured schedules and the first successful backup timestamp in the
   evidence table below.
6. Repeat for the `staging` `Postgres-5eke` service if staging data becomes non-disposable.
   Staging is currently disposable, so backups there are optional.

### Redis

Redis holds reproducible cache and rate-limit coordination state only. Backups are **not
required**. Losing Redis degrades readiness but the application repopulates from providers
while fixture identities remain in PostgreSQL. If durable accounts, notification jobs, or
device tokens are ever stored in Redis, revise this decision before that release.

## Restore rehearsal

> **Critical caveat:** Railway states that restoring a backup **removes any newer backups
> created after the one being restored**. Never rehearse by restoring in place on
> production. Always restore into a scratch environment.

1. Create a scratch environment (for example `restore-rehearsal`).
2. Restore the chosen recovery point into a PostgreSQL service in that environment:
   Backups tab → locate by date stamp → **Restore** → review staged changes → **Deploy**.
3. Record the backup's timestamp and the restore start time.
4. Run the automated verifier against the restored database:

   ```bash
   python scripts/verify_restore.py --database-url "$RESTORED_DATABASE_URL"
   ```

   It asserts the identity tables exist, `alembic_version` is `20260804_01`, the
   `fixture_identities` table is non-empty, and every `canonical_fixture_id` is unique.
   Exit status is non-zero on any failure, so it can gate the rehearsal.
5. Point a staging application instance at the restored database and a scratch Redis
   service, then confirm `/health/ready` reports `status: ready` with `blocking: []`.
6. Record restore end time. Compute **RTO** (start → verified) and **RPO** (backup
   timestamp → simulated failure time).
7. Delete the scratch environment only after evidence is captured.

## Production recovery

Preserve the damaged service for investigation — do not delete it. Restore the selected
recovery point into a **new** PostgreSQL service, validate it with
`scripts/verify_restore.py`, then repoint the `web` service's `DATABASE_URL` reference and
deploy. Keep the prior service until recovery is accepted. Application rollback does not
reverse schema or data loss.

## Monitoring

Railway deployment healthchecks are not backup monitoring. Until backup-age alerting
exists, an operator must confirm the latest backup date during each weekly ops review.
Backup-age reporting is a planned capability of the operations dashboard.

## Evidence — to be completed by the operator

| Item | Value | Captured by | Date |
| --- | --- | --- | --- |
| Schedules enabled | _not yet configured_ | | |
| Retention confirmed | _not yet configured_ | | |
| Encryption / access controls | _not yet recorded_ | | |
| Latest successful backup | _none_ | | |
| Restore rehearsal performed | _never_ | | |
| Achieved RPO | _unmeasured_ | | |
| Achieved RTO | _unmeasured_ | | |
| `verify_restore.py` result | _not run against a restore_ | | |

Copy the completed table into `artifacts/release-evidence/<full-sha>/backup-restore.md`.

## Configuration and deletion

Keep a non-secret inventory of required variable names, service references, domains, and
commands in source control. Store credentials only in Railway and sealed operational
systems. Backup retention delays physical removal of deleted data; document that behaviour
before accounts are introduced and never promise immediate removal from retained backups.
