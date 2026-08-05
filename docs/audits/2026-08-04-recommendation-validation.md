# Recommendation validation matrix — 2026-08-04

Audited revision (deployed `main`): `d665414b693ded4bd970f363b6eb6225f3214c21`
Local working revision: `8943dfed2c9e63692f938c4e66bb033ab3269a37` (branch `feat/deliberate-guest-mode`)
Previous audit baseline: `0a9ce6efb955d285142074869a4c2339a399b15d`

## Phase 0 — verified baseline

| Check | Result | Evidence |
| --- | --- | --- |
| Local `main` SHA | `d665414b693ded4bd970f363b6eb6225f3214c21` | `git rev-parse main` |
| Deployed SHA | `d665414b693ded4bd970f363b6eb6225f3214c21` | `/health/version` `commitSha` |
| SHA match | **Yes** | deployed == audited `main` |
| Railway deploy terminal state | `SUCCESS` | deployment `4cce22ef-698b-47da-8879-da650896e767`, branch `main`, commit `d665414` |
| `/health/live` | `200 {"status":"ok"}` | curl |
| `/health/ready` | `200`, `status: ready`, `blocking: []` | curl |
| Durable PostgreSQL | `durable: true`, `reachable: true`, `schemaVersion: 20260804_01` | `/health/ready` |
| Shared Redis | `backend: redis`, `shared: true` | `/health/ready` |
| Python tests | 119 passed | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` |
| JS/MJS syntax | all pass | `node --check` over `static`, `tests` |
| `compileall` | pass | `app.py wsgi.py soccer_scanner` |
| Smoke invariants | 4/4 pass | `npm run test:smoke-invariants` |
| `npm audit --audit-level=high` | 0 vulnerabilities | npm |
| `pip-audit` | **blocked** — binary not installed | `pip-audit: command not found` |
| `git diff --check` | clean | git |

### Real Railway topology (CLI-verified, not from documentation)

Project `soccer-scanner` — `933a7441-1b02-440a-b5a4-7e639a8584db`, plan `pro`.

**production** (`ec80c102-87e2-4edf-88c1-c563e827dc8b`)

| Service | State | Notes |
| --- | --- | --- |
| `web` | serving | healthcheck `/health/ready` (300s), preDeploy `alembic upgrade head`, `gunicorn … --workers ${WEB_CONCURRENCY:-2}`, 1 replica, `us-west2` |
| `Postgres` | RUNNING | private, volume-backed, `us-west2` |
| `Redis` | RUNNING | private, volume-backed, `us-west2` |

Domains: `soccerscanner.pro` (custom, ACTIVE, port 8080) and `web-production-c10a4.up.railway.app`.
Variables present (values redacted): `DATABASE_URL`, `REDIS_URL`, `OPS_ADMIN_TOKEN`, `PUBLIC_BASE_URL`, `TRUSTED_PROXY_HOPS`, `APP_ENVIRONMENT`, `APP_VERSION`, DB pool tuning.

**staging** (`79a12172-2ed1-45f5-9aac-846bd313b970`)

| Service | State | Notes |
| --- | --- | --- |
| `web-staging` | serving | same manifest; `web-staging-staging-eec1.up.railway.app` |
| `Postgres-5eke` | RUNNING | volume `postgres-volume-mKs4`, 0.8 GB / 48.8 GB |
| `Redis-Yl2w` | RUNNING | volume `redis-volume-DnL7` |
| `Postgres-IZlv` | RUNNING | **duplicate/orphan — no service reference found** |
| `Redis-ZvsD` | RUNNING | **duplicate/orphan — no service reference found** |

**Findings not present in existing documentation:**

1. Staging runs **two Postgres and two Redis instances**. Only one pair is referenced by `web-staging`. The other pair is billed, volume-backed, and unmanaged. This is a live cost and confusion defect.
2. There is **no worker service** and **no cron service** in either environment. No `cronSchedule` is set on any service.
3. There are **no configured backups, retention policy, or restore rehearsal evidence** obtainable from the CLI surface used here.
4. No external uptime or synthetic monitoring is configured; Railway healthchecks are deploy-gating only, not continuous monitoring.

## Status legend

`implemented` · `implemented_with_follow_up` · `partial` · `not_implemented` · `blocked` · `not_applicable`

## A. Preserved fixture-identity work (regression boundary)

| Requirement | Status | Repository evidence | Production evidence | Tests |
| --- | --- | --- | --- | --- |
| Durable PostgreSQL identity registry | `implemented` | `soccer_scanner/persistence/fixture_identities.py` | `/health/ready` `database.durable=true` | `tests/test_fixture_identity_repository.py` |
| Provider alias registry | `implemented` | same module | schema `20260804_01` live | same |
| Alembic migration | `implemented` | `migrations/versions/20260804_01_fixture_identity_registry.py` | `schemaVersion: 20260804_01` | migration applied via preDeploy |
| Collision-resistant fallback IDs | `implemented` | `soccer_scanner/domain/identity.py` | — | `tests/test_fixture_identity.py` |
| Batched identity resolution | `implemented` | `soccer_scanner/services/fixture_service.py` (commit `4e02886`) | — | `tests/test_fixture_identity_repository.py` |
| Kickoff-independent public IDs | `implemented` | `soccer_scanner/domain/identity.py` | — | `tests/test_fixture_identity.py` |
| Fixture-ID uniqueness invariant | `implemented` | runtime invariant | — | `tests/production-smoke-invariants.test.mjs` (2 cases) |
| Alias-based link recovery | `implemented` | `pages.py::_fixture_from_link` | — | covered |
| Exact-SHA smoke verification | `implemented` | smoke harness | `/health/version` exact match | smoke |
| Readiness requires durable PG + shared Redis | `implemented` | `soccer_scanner/routes/health.py` | `blocking: []` | smoke invariant 4 |

**No regression detected.** All 119 Python tests and 4 smoke invariants pass at baseline. This work is preserved as-is.

## B. P0 — Accounts, favorites, defaults

| Requirement | Status | Evidence | Remaining |
| --- | --- | --- | --- |
| ADR deciding accounts vs no accounts | `implemented` | `docs/decisions/accounts-and-preferences.md`, accepted 2026-08-04 | — |
| Decision outcome | — | **Deliberate guest mode.** No accounts this release. | — |
| Remove persistent guest favorites | `partial` | uncommitted working tree removes favorites module, URL state, filtering, ranking, import/export | needs commit + full gate run |
| Hide Favorites navigation / buttons / filter | `partial` | `templates/base.html`, `templates/matches_today.html` diffs | needs commit |
| Session-scoped score preference | `partial` | `static/js/score-preference.js` switched to `sessionStorage` | needs commit |
| Timezone not persisted indefinitely | `partial` | URL-backed only | verify after timezone work |
| No fake anonymous accounts | `implemented` | no user tables, no auth code | — |

**Note:** the ADR chose guest mode, which is a defensible reading of the brief, but the brief's *default recommendation* was accounts because iOS sync and notifications are planned. The ADR documents reconsideration triggers. Recorded as an intentionally deferred decision, not a gap.

## C. P0 — Defects confirmed by reproduction

| # | Defect | Status | Evidence (file:line) |
| --- | --- | --- | --- |
| 1 | Deep link forces `timezone='UTC'` while passing a *local* date — opens the wrong calendar day | `not_implemented` | `soccer_scanner/routes/pages.py:62-63` (`date=match.get('localDate')`, `timezone='UTC'`) |
| 2 | Header timezone control beside score toggle | `not_implemented` | absent from `templates/base.html` / `matches_today.html` |
| 3 | Browser-local time formatting instead of selected timezone | `not_implemented` | `fixture-renderer.js:54,60,274`; `calendar.js:68`; `match-context.js:39,97`; `teams.js:144,170-171,348,382,425,477` — all `toLocale*` with no `timeZone` option |
| 4 | Status taxonomy collapses HT/ET/PEN into generic Live; no DELAYED/ABANDONED/SUSPENDED | `not_implemented` | `fixture-state.js:1` and `refresh-controller.js:2` both define ad-hoc `LIVE_STATUSES` sets |
| 5 | Streaming region extracted by backend, dropped by frontend | `partial` | backend `espn.py:109` emits `region`; frontend `fixture-renderer.js:192` renders `Streaming: names` only — no region, logo, or link |
| 6 | Process-local rate limiting in production | `not_implemented` | `soccer_scanner/__init__.py:74` constructs `MemoryRateLimiter` unconditionally; production runs 2+ gunicorn workers → per-worker limits |
| 7 | Standings season hardcoded | `not_implemented` | `templates/league_tables.html:21-26` — literal SofaScore season IDs and `25/26` labels |
| 8 | Calendar issues 7 independent per-day requests | `partial` | `calendar.js:97` per-day `fetch` in bounded worker pool; no range endpoint |
| 9 | Country filter depends on `competition.area.name` | `partial` | `fixtures.js:121` — populated only if provider supplies `area`; control self-hides when empty |
| 10 | Icon suite is SVG-only | `not_implemented` | `static/` contains only `favicon.svg`, `social-card.svg` — no PNG, apple-touch-icon, 192/512, maskable |

## D. P0/P1 — Missing routes and platform surfaces

Route inventory from `soccer_scanner/routes/pages.py`: `fixtures`, `legacy_fixtures`, `teams`, `league_tables`, `calendar`, `privacy`, `data_sources`, `offline`, `fixture_link`, `fixture_calendar`, `team_page`, `competition_page`. Plus `routes/api.py` and `routes/health.py`.

| Requirement | Status | Evidence |
| --- | --- | --- |
| `/terms` | `not_implemented` | no route |
| `robots.txt` | `not_implemented` | no route, no static file |
| XML sitemap | `not_implemented` | no route |
| `/.well-known/apple-app-site-association` | `not_implemented` | no route |
| `/api/v2/app-config` | `not_implemented` | absent from `routes/api.py` |
| Header logo mark | `not_implemented` | `templates/base.html` — text wordmark only |
| Global search | `not_implemented` | no search API or UI |
| Feature flags | `not_implemented` | no flag module |
| Operations dashboard | `not_implemented` | `OPS_ADMIN_TOKEN` exists in production env but no dashboard route consumes it |
| OpenAPI `openapi/soccer-scanner-v2.yaml` | `not_implemented` | directory absent |
| iOS SwiftUI project `clients/ios/` | `not_implemented` | directory absent |
| APNs | `not_applicable` (pending notification ADR) | guest mode; no accounts |
| `docs/reliability-and-slos.md` | `not_implemented` | absent |
| `docs/analytics.md` | `not_implemented` | absent |
| `docs/decisions/notifications.md` | `not_implemented` | absent |
| `docs/seo.md` | `not_implemented` | absent |
| `marketing/` workspace | `not_implemented` | absent |
| `docs/versioning-and-release-management.md` | `not_implemented` | absent |
| `docs/release-checklist.md` | `not_implemented` | absent |

## E. Railway operations

| Requirement | Status | Evidence | Remaining |
| --- | --- | --- | --- |
| Public web/API service | `implemented` | production `web` serving `soccerscanner.pro` | — |
| Private PostgreSQL | `implemented` | production `Postgres` RUNNING | — |
| Private Redis | `implemented` | production `Redis` RUNNING | — |
| Pre-deploy Alembic migration | `implemented` | `preDeployCommand: ["alembic upgrade head"]` on both web services | — |
| `/health/ready` healthcheck | `implemented` | manifest `healthcheckPath: /health/ready`, timeout 300 | — |
| Correct custom domain | `implemented` | `soccerscanner.pro` ACTIVE | — |
| Isolated staging environment | `implemented` | separate environment with own web/PG/Redis | — |
| Separate staging PG and Redis | `implemented_with_follow_up` | present, but **duplicated** | remove orphan `Postgres-IZlv`, `Redis-ZvsD` |
| Worker service | `not_applicable` | no durable background work exists yet under guest mode | revisit if notifications/search indexing land |
| Cron jobs | `not_implemented` | no `cronSchedule` on any service | justified jobs: standings verification, sitemap generation, backup verification |
| Backup schedule / retention / encryption | `blocked` | not obtainable via authenticated CLI surface used | operator steps below |
| Latest successful backup | `blocked` | — | operator steps below |
| Restore rehearsal, RPO, RTO | `blocked` | never performed | operator steps below |
| External uptime monitoring | `not_implemented` | none configured | — |
| Synthetic API monitoring | `not_implemented` | none | — |
| Error tracking | `not_implemented` | none | — |
| Capacity / eviction / backup-age alerts | `not_implemented` | none | — |
| Cost controls documentation | `not_implemented` | — | orphan services are active waste |

### Blocked: backup and disaster recovery — exact operator steps

Disaster recovery is **not** implemented. Documentation alone is insufficient and no restore has ever been rehearsed. To unblock, an operator with Railway dashboard access must:

1. Open Railway → project `soccer-scanner` → environment `production` → service `Postgres` → **Backups**.
2. Record: schedule, retention window, encryption-at-rest statement, and the timestamp of the most recent successful backup.
3. Create a scratch environment, restore the newest backup into it, and record wall-clock restore duration (**RTO**) and the backup's age at restore (**RPO**).
4. Against the restored database, verify `alembic current` reports `20260804_01` and that `fixture_identities` row count is within tolerance of production.
5. Destroy the scratch environment and record results in `artifacts/release-evidence/<sha>/backup-restore.md`.

These steps require interactive dashboard authentication. The Railway MCP server in this session is **unauthenticated** and the session is non-interactive, so this cannot be completed here. The CLI (`railway whoami` → `Leif Heaney`) provided topology but not backup administration.

## F. Provider, PWA, and data-quality items

| Requirement | Status | Evidence |
| --- | --- | --- |
| ESPN truncation detection | `not_implemented` | `providers/espn.py` uses fixed `limit=500` with no total detection |
| One overall orchestration deadline | `not_implemented` | per-provider deadlines |
| Shared long-lived league metadata cache | `partial` | `services/cache.py` exists; metadata failure still drops fixtures |
| PWA excludes ET/PEN from offline cache | `not_implemented` | offline cache uses the same incomplete live-status set |
| Recompute counts/featured after sanitization | `not_implemented` | — |
| Team Intelligence partial states | `partial` | `services/team_analytics.py`, `team_identity.py` (102 lines, ~6 mappings) |
| Sorting not overwritten by grouping | `not_implemented` | `groupMatches()` in `fixtures.js` |
| `popstate` restores fixture context | `not_implemented` | `selectedFixtureId` reset unconditionally |

## G. Completion pass — work landed in this session

Branch `feat/deliberate-guest-mode`. Each item below is backed by a passing test, not by documentation.

| # | Commit | Requirement | New status | Evidence |
| --- | --- | --- | --- | --- |
| 1 | `53bba48` | Remove persistent guest favorites, hide favorites nav/controls, session-scope score preference | `implemented` | `tests/browser/favorites.spec.js`, `tests/test_app.py` guest assertions |
| 2 | `2b20d81` | Evidence-backed recommendation validation matrix | `implemented` | this document; `artifacts/release-evidence/d665414…/baseline.md` |
| 3 | `5f2de6e` | Shared timezone module (`formatKickoff`, `formatFixtureDate`, `calendarDateInZone`, `todayInZone`, `formatTimezoneLabel`) | `implemented` | `tests/time-zone.test.mjs` — 9 tests incl. DST transition and 5-zone midnight crossover |
| 4 | `5f2de6e` | Canonical 12-state match-status taxonomy with full behaviour contract | `implemented` | `tests/match-status.test.mjs` — 9 tests |
| 5 | `5f2de6e` | Deep-link timezone repair | `implemented` | `tests/test_app.py` — 3 tests across New York, Los Angeles, London, Tokyo, Sydney |
| 6 | `827cfef` | Shared Redis rate limiting with atomic single-round-trip check | `implemented` | `tests/test_rate_limit.py` — cross-worker, atomicity, per-key isolation, degradation |
| 7 | `827cfef` | Per-surface rate-limit policies and `RateLimit-*` headers | `implemented` | `tests/test_rate_limit.py` |
| 8 | `827cfef` | Readiness blocks production when limiting is not shared | `implemented` | `tests/test_app.py` production readiness tests |
| 9 | `827cfef` | `/health/metrics` protected by operations token | `implemented` | `tests/test_rate_limit.py` |
| 10 | `0addb19` | `/terms` route, required sections, footer link, no invented legal entity | `implemented` | `tests/test_public_routes.py` |
| 11 | `0addb19` | `robots.txt` and XML sitemap excluding API/health | `implemented` | `tests/test_public_routes.py` |
| 12 | `0addb19` | Server-enforced feature flags with owner and expiry | `implemented` | `soccer_scanner/services/feature_flags.py`, app-config tests |
| 13 | `0addb19` | `/api/v2/app-config` with no secret leakage | `implemented` | `tests/test_public_routes.py` |
| 14 | `0addb19` | AASA served as JSON without redirect, only when Apple IDs configured | `implemented_with_follow_up` | `tests/test_public_routes.py`; **blocked** on real Apple Team/bundle ID |
| 15 | `f2a750a` | Client renders every kickoff/date in the selected zone | `implemented` | Chromium + WebKit 51/51; server log confirms `time-zone.js` loaded |
| 16 | `f2a750a` | HT/ET/PEN/DELAYED/ABANDONED render distinctly; abandoned terminal; suspended keeps refreshing | `implemented` | `tests/match-status.test.mjs`, browser suites |
| 17 | `f2a750a` | Grouping no longer discards the selected sort | `implemented` | `groupMatches(matches, sort)`; browser suites |

### Gate results after this work

| Gate | Result |
| --- | --- |
| Python | 144 passed, 5 subtests |
| Node module tests | 22 passed |
| Playwright Chromium | 51 passed |
| Playwright WebKit | 51 passed |
| `node --check` | all pass |
| `npm audit --audit-level=high` | 0 vulnerabilities |

### Deployment status

**Not deployed.** All work above is committed to `feat/deliberate-guest-mode` and has **not** been merged, staged, or promoted. Production remains on `d665414`. Steps 32–36 of the implementation order (staging deploy, exact-SHA staging smoke, production deploy, exact-SHA production smoke, final matrix evidence) are outstanding.

### Not started

Streaming registry and UI; header timezone control and searchable selector; header logo and full icon suite; country-filter resolution; browser-history fixture restoration; calendar range endpoint and partial-failure handling; team intelligence partial states; standings season configuration; ESPN truncation detection and single provider deadline; PWA offline recomputation; global search; mobile-first 320px pass; operations dashboard; monitoring and alerting; SLO/analytics/notification ADRs; SEO documentation; marketing workspace; release governance; OpenAPI contract; iOS SwiftUI project, vertical slice and CI; APNs.

## H. Summary counts

| Status | Count |
| --- | --- |
| `implemented` | 18 |
| `implemented_with_follow_up` | 1 |
| `partial` | 9 |
| `not_implemented` | 34 |
| `blocked` | 3 |
| `not_applicable` | 2 |

The completed fixture-identity and Railway-persistence programme is genuinely done, deployed, and verified at the exact SHA. Essentially all of the broader product, timezone, streaming, legal, SEO, marketing, operations, and iOS scope remains unimplemented.
