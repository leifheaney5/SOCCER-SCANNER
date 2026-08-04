# Production Hardening Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate fixture-ID collisions and kickoff volatility, make fixture aliases durable, and configure Railway with PostgreSQL, Redis, migrations, and dependency-aware readiness.

**Architecture:** A registry separates provider aliases from canonical match evidence and public IDs. SQLAlchemy/Alembic persist aliases in production, Redis coordinates cache state, and the fixture service enforces response-level identity uniqueness before caching or returning data.

**Tech Stack:** Python 3.13 production runtime, Flask 3.1, SQLAlchemy 2, Alembic, psycopg 3, Redis 6, pytest, Playwright, Railway.

## Global Constraints

- Preserve the `/api/v2/fixtures` contract and `canonicalFixtureId` field.
- Scores remain hidden by default and never enter new logs or diagnostics.
- Never merge reversed teams or ambiguous name-only identities.
- Never treat an unavailable provider as an empty schedule.
- PostgreSQL owns durable aliases; Redis owns only cache and coordination state.
- Production changes use migrations and Railway private service references.
- Do not add `Co-Authored-By:` trailers to commits.

---

### Task 1: Define collision-resistant provider-qualified identities

**Files:**
- Modify: `tests/test_fixture_identity.py`
- Modify: `soccer_scanner/domain/identity.py`

**Interfaces:**
- Produces: `provider_identity_keys(fixture) -> tuple[str, ...]`
- Produces: `provider_fallback_public_id(fixture) -> str`
- Produces: `FixtureIdentityError`

- [ ] **Step 1: Add failing identity tests**

Add literal assertions proving two and ten distinct ESPN event IDs at one kickoff produce unique IDs, the same event retains its ID after a kickoff correction, cross-provider input order is deterministic, reversed teams do not merge, and a fixture without a provider event ID raises `FixtureIdentityError`.

- [ ] **Step 2: Verify the tests fail for the current collision**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_fixture_identity.py -q`

Expected: failures showing one unique ID for multiple unmapped fixtures and a changed ID after kickoff correction.

- [ ] **Step 3: Implement the minimal provider-qualified fallback**

Build public IDs from a sorted provider namespace and event ID, never kickoff. Reject empty provider identity. Keep canonical matching logic separate and unchanged.

- [ ] **Step 4: Verify focused tests pass**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_fixture_identity.py -q`

- [ ] **Step 5: Commit**

Commit: `fix: make fixture fallback identities collision resistant`

---

### Task 2: Add the durable fixture identity registry and migration

**Files:**
- Modify: `requirements.txt`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/20260804_01_fixture_identity_registry.py`
- Create: `soccer_scanner/persistence/database.py`
- Create: `soccer_scanner/persistence/fixture_identities.py`
- Create: `tests/test_fixture_identity_repository.py`
- Create: `tests/test_migrations.py`

**Interfaces:**
- Produces: `DatabaseRuntime.from_config(config)`
- Produces: `FixtureIdentityRepository.resolve(group, match_evidence) -> str`
- Produces: `FixtureIdentityRepository.resolve_public_alias(public_id) -> str | None`
- Produces: `FixtureIdentityRepository.record_resolution_issue(...)`
- Produces: `FixtureIdentityRepository.health() -> dict`

- [ ] **Step 1: Add failing repository tests**

Use a temporary SQLite database to prove provider aliases survive repository recreation, kickoff changes retain IDs, a newly observed cross-provider alias joins the existing fixture, superseded public aliases resolve to the survivor, and reversed/ambiguous candidates stay separate.

- [ ] **Step 2: Add a failing migration test**

Upgrade an empty temporary database to Alembic `head`, inspect the five required tables, and assert the schema version row exists.

- [ ] **Step 3: Verify both test files fail because persistence is absent**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_fixture_identity_repository.py tests/test_migrations.py -q`

- [ ] **Step 4: Add bounded database dependencies and runtime**

Add SQLAlchemy, Alembic, and psycopg dependency ranges compatible with Python 3.13. Normalize Railway PostgreSQL URLs, configure pool bounds, and expose transactional session scopes.

- [ ] **Step 5: Implement schema and repository transactions**

Enforce unique `(provider, provider_event_id)` aliases and unique public aliases. Resolve races by re-reading after integrity conflicts. Choose the oldest existing public identity during reconciliation and preserve superseded IDs as aliases.

- [ ] **Step 6: Verify repository and migration tests pass**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_fixture_identity_repository.py tests/test_migrations.py -q`

- [ ] **Step 7: Commit**

Commit: `feat: persist fixture identities and aliases`

---

### Task 3: Integrate durable identity and enforce response uniqueness

**Files:**
- Modify: `soccer_scanner/domain/identity.py`
- Modify: `soccer_scanner/services/fixture_service.py`
- Modify: `soccer_scanner/__init__.py`
- Modify: `soccer_scanner/config.py`
- Modify: `tests/test_fixture_service_v2.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Changes: `merge_fixtures(fixtures, identity_registry=None)`
- Produces: `assert_unique_fixture_ids(matches) -> None`
- Produces: `CanonicalFixtureService.lookup_fixture(public_id, timezone_name='UTC')`

- [ ] **Step 1: Add failing service tests**

Prove a full response contains unique IDs for ten unmapped same-kickoff events, duplicate IDs fail before cache writes, cache loss still allows deep-link recovery, a persisted alias resolves after kickoff correction, and an old public alias returns the current fixture.

- [ ] **Step 2: Verify focused failures**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_fixture_service_v2.py tests/test_app.py -q`

- [ ] **Step 3: Inject the registry and add the invariant**

Resolve each merged group through the registry, store the latest kickoff evidence, validate every response ID before deep-link cache writes, and recover a cache miss through the durable registry plus a bounded date refresh.

- [ ] **Step 4: Verify focused tests pass**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_fixture_identity.py tests/test_fixture_identity_repository.py tests/test_fixture_service_v2.py tests/test_app.py -q`

- [ ] **Step 5: Commit**

Commit: `fix: enforce durable unique fixture identities`

---

### Task 4: Add production readiness and protected mapping diagnostics

**Files:**
- Modify: `soccer_scanner/routes/health.py`
- Modify: `soccer_scanner/routes/api.py`
- Modify: `soccer_scanner/__init__.py`
- Modify: `soccer_scanner/config.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_observability.py`

**Interfaces:**
- `/health/ready` reports database, schema, and cache dependency states.
- `GET /api/internal/identity-report` requires `Authorization: Bearer <OPS_ADMIN_TOKEN>`.

- [ ] **Step 1: Add failing readiness and authorization tests**

Assert production readiness returns 503 when the database is absent or Redis is unshared, returns 200 when both are ready, never calls soccer providers, and the identity report rejects missing/wrong tokens while returning score-free unresolved counts to an authorized operator.

- [ ] **Step 2: Verify focused tests fail**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_app.py tests/test_observability.py -q`

- [ ] **Step 3: Implement dependency-aware readiness and diagnostics**

Keep liveness cheap. Add constant-time token comparison, bounded report pagination, structured issue counters, and no destructive actions.

- [ ] **Step 4: Verify focused tests pass**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_app.py tests/test_observability.py -q`

- [ ] **Step 5: Commit**

Commit: `feat: expose dependency readiness and identity diagnostics`

---

### Task 5: Add Railway configuration and operational documentation

**Files:**
- Create: `railway.toml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/deployment.md`
- Create: `docs/railway-architecture.md`
- Create: `docs/railway-deployment.md`
- Create: `docs/railway-runbook.md`
- Create: `docs/database-migrations.md`
- Create: `docs/backup-and-recovery.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Pre-deploy command: `alembic upgrade head`
- Start command: `gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-2} --timeout 30 wsgi:app`
- Health check: `/health/ready`

- [ ] **Step 1: Add configuration and safe placeholders**

Declare `DATABASE_URL`, `REDIS_URL`, `OPS_ADMIN_TOKEN`, pool bounds, environment, version, SHA, and public URL without real values.

- [ ] **Step 2: Add deployment and recovery documentation**

Document the verified before-topology, target topology, private networking, migration ordering, backup ownership, restore rehearsal, rollback limitations, and secret rotation.

- [ ] **Step 3: Update changelog and runtime architecture documentation**

Record identity semantics, migration requirements, readiness changes, and known provider limitations without exposing sensitive details.

- [ ] **Step 4: Validate configuration and docs**

Run: `git diff --check`

- [ ] **Step 5: Commit**

Commit: `docs: define Railway persistence and migration operations`

---

### Task 6: Extend production smoke and complete local verification

**Files:**
- Modify: `tests/production-smoke.mjs`
- Modify: `docs/testing.md`

**Interfaces:**
- Production smoke fails when fixture IDs are missing or duplicated.
- Production smoke verifies readiness dependencies and exact deployed SHA.

- [ ] **Step 1: Add the failing smoke assertion against a controlled duplicate payload**

Refactor the uniqueness check into an exported pure function and add a Node test fixture containing duplicate IDs.

- [ ] **Step 2: Verify the smoke regression fails before implementation**

Run the new Node test command documented in `package.json`.

- [ ] **Step 3: Implement the smoke invariant and documentation**

Assert uniqueness, dependency readiness, exact SHA, hidden-score behavior, and existing asset/console checks.

- [ ] **Step 4: Run the complete local verification matrix**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
python -m compileall -q app.py wsgi.py soccer_scanner
$files = rg --files static tests | Where-Object { $_ -match '\.(js|mjs)$' }
foreach ($file in $files) { node --check $file }
npm ci
npx playwright test --project=chromium --project=webkit
npm audit --audit-level=high
python -m pip_audit -r requirements.txt
git diff --check
```

- [ ] **Step 5: Commit**

Commit: `test: enforce fixture identity production invariants`

---

### Task 7: Provision, migrate, deploy, and verify Railway

**Files:**
- No additional source files unless live verification finds a release defect.

**Interfaces:**
- Railway production: public `web`, private PostgreSQL, private Redis.
- Railway staging: separate `web`, PostgreSQL, and Redis state.

- [ ] **Step 1: Re-read current Railway topology and verify exact targets**

Use explicit project/environment/service IDs. Do not create a database or Redis service if a suitable one appeared since baseline.

- [ ] **Step 2: Create private PostgreSQL and Redis services and reference variables**

Set `DATABASE_URL` and `REDIS_URL` through Railway service references. Set non-secret runtime configuration and generate `OPS_ADMIN_TOKEN` without printing it.

- [ ] **Step 3: Create an isolated staging environment**

Use separate PostgreSQL/Redis data and secrets. Do not share mutable production persistence.

- [ ] **Step 4: Deploy staging and observe terminal status**

Require migration success, Railway readiness, complete local/remote smoke, and schema-current evidence.

- [ ] **Step 5: Deploy production and observe terminal `SUCCESS`**

Record deployment ID, commit SHA, service topology, configuration state, and migration version.

- [ ] **Step 6: Run production smoke against the exact deployed SHA**

Run: `$env:BASE_URL='https://soccerscanner.pro'; $env:EXPECTED_SHA=(git rev-parse HEAD); npm run smoke:production`

- [ ] **Step 7: Verify live busy-date uniqueness and dependency readiness**

Assert fixture count equals unique public-ID count, aliases survive repeated requests, readiness reports PostgreSQL/Redis ready, and no first-party 4xx/5xx or console errors appear.

- [ ] **Step 8: Record the release evidence and clean state**

Update the release evidence, commit it, push the reviewed branch, verify Railway remains healthy, and confirm `git status --short` is empty.
