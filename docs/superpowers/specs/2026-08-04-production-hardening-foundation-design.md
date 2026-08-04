# Production Hardening Foundation Design

## Scope

This is the first independently deployable slice of the comprehensive Soccer Scanner production brief. It resolves the two verified release blockers before broader timezone, account, notification, iOS, search, SEO, and marketing work begins:

1. Public fixture identities collide for unmapped fixtures and change when kickoff changes.
2. Railway runs two Gunicorn workers with only process-local memory state and no durable database.

The slice preserves the existing `/api/v2/fixtures` response shape and keeps `canonicalFixtureId` as the public identifier field for compatibility.

## Verified baseline

- Local `main`, `origin/main`, Railway deployment metadata, and `/health/version` all identify commit `0a9ce6efb955d285142074869a4c2339a399b15d`.
- Railway has one `web` service in one `production` environment, with no PostgreSQL, Redis, worker, cron, volume, bucket, pre-deploy command, or configured health-check path.
- `/health/ready` reports a memory cache with `shared: false` and `status: degraded`.
- The 2026-08-04 America/New_York response contained 42 fixtures but only 23 unique public IDs. Twelve IDs were duplicated across 31 fixtures.
- Two synthetic unmapped fixtures at the same kickoff receive the same ID; ten receive one shared ID; changing a provider event kickoff by 30 minutes changes its ID.
- Pre-change checks passed: 96 Python tests, 104 Chromium/WebKit tests, compileall, and 29 JavaScript syntax checks. npm audit reported zero vulnerabilities. `pip-audit` was not installed.

## Identity architecture

Provider identity, canonical matching identity, and public identity become separate concepts.

### Provider identity

A provider event is identified by the tuple `(provider, provider_event_id)`. Provider identities are immutable aliases and never include kickoff time.

### Canonical matching identity

Cross-provider matching continues to require canonical competition, ordered home team, ordered away team, compatible season/stage evidence, and kickoff within the matching tolerance. Missing or ambiguous canonical identities never trigger name-only merging. Reversed teams never match.

### Public fixture identity

`canonicalFixtureId` remains the externally visible field, but its value is assigned from durable provider aliases:

- A previously seen provider identity resolves to its stored public ID.
- A new cross-provider group matching one existing durable fixture adds its provider aliases to that fixture.
- A wholly new group receives `fx_` plus a collision-resistant digest of a provider-qualified event identity. Kickoff is excluded.
- If multiple existing durable identities are discovered during reconciliation, the oldest identity remains canonical, the other public IDs become aliases, and every provider alias resolves to the survivor.
- Production requires the durable registry. Development and tests may use an in-memory registry with identical behavior.
- Included provider fixtures without any provider event identity are rejected as malformed instead of receiving a volatile public identifier.

The database stores fixture records, provider aliases, and superseded public-ID aliases. Public lookup resolves both current and superseded IDs.

## Runtime invariant and deep links

Every composed API response is checked before caching or returning. Duplicate or missing public IDs raise an explicit identity-invariant failure; no fixture can overwrite another fixture's deep-link cache entry.

The durable registry stores the latest known kickoff and provider identities. Deep-link lookup first resolves public aliases, then checks shared cache, then performs a bounded fixture refresh around the persisted kickoff date. This allows ordinary cache expiry, worker changes, restarts, and kickoff corrections to preserve the URL.

## Persistence and migrations

SQLAlchemy owns database access and Alembic owns schema changes. The initial migration creates:

- `fixture_identities`
- `fixture_provider_aliases`
- `fixture_public_aliases`
- `identity_resolution_issues`
- `schema_metadata`

SQLite is used for isolated tests. PostgreSQL is required in production. Redis remains cache/coordination infrastructure and is never the durable source of fixture aliases.

## Railway deployment architecture for this slice

The current single web service remains the only public service. This slice adds private PostgreSQL and Redis services, a staging environment with separate persistence, and source-controlled web deployment configuration.

`railway.toml` defines:

- the Gunicorn start command;
- `alembic upgrade head` as the pre-deploy migration command;
- `/health/ready` as the deployment health check;
- restart and shutdown behavior.

Production readiness requires a reachable, schema-compatible database and a reachable shared Redis cache. External soccer-provider health does not gate readiness.

## Security and operations

- Connection strings remain Railway variables and are never logged or committed.
- Database and Redis services remain private.
- Startup validates critical production configuration.
- Identity conflicts and unresolved mappings emit structured, score-free diagnostics.
- A token-protected internal JSON report exposes unresolved identity counts and recent records without secrets or score data. Destructive operations are not included in this slice.

## Test strategy

Tests are written and observed failing before production changes. Coverage includes:

- two and ten unmapped fixtures at one kickoff;
- provider-qualified fallback IDs;
- same provider event after kickoff correction;
- cross-provider mapped fixtures and provider alias preservation;
- reversed teams and ambiguous identities;
- same club name in different countries;
- public-ID alias reconciliation;
- deep-link resolution after schedule change and cache loss;
- cache overwrite prevention and full-response uniqueness;
- migration upgrade from an empty database;
- production readiness with missing, healthy, and degraded dependencies;
- protected unresolved-mapping report;
- production smoke assertion for unique fixture IDs.

## Release boundary

This release does not introduce user accounts, persistent favorites, notifications, workers, cron jobs, or the iOS project. Those remain subsequent slices, after the identity and persistence contracts they depend on are deployed and verified.
