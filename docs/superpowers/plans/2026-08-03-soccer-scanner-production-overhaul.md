# Soccer Scanner Production Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Soccer Scanner a truthful, spoiler-safe, accessible, fast, production-ready fixture product across provider failures, cross-provider identity, live updates, mobile interaction, and the approved high-value feature set.

**Architecture:** Introduce a versioned camelCase domain contract between provider adapters and the UI. Provider HTTP, cache, single-flight, outcome, and observability concerns live below a fixture orchestration service; canonical team and fixture identities live above provider namespaces. A centralized browser store owns URL, history, polling, selection, filters, favorites, and responsive surfaces. Redis is the production coordination backend with bounded in-memory fallback for development/tests.

**Tech Stack:** Python 3.12+, Flask 3.1, requests, Redis, Gunicorn, vanilla JavaScript ES modules, Jinja, CSS, pytest/unittest, Playwright Chromium/WebKit, axe-core, GitHub Actions, Railway.

**Approved references:** `docs/audits/soccer-scanner-audit.md`, `docs/superpowers/specs/2026-08-03-production-provider-foundation-design.md`, and `docs/superpowers/specs/2026-08-03-fixtures-dashboard-design.md`.

## Non-negotiable contracts

- Hidden scores never enter visible text, accessibility names, nonessential DOM attributes, metadata, dialogs, calendar exports, or offline responses until the user reveals them.
- Every ID crossing a provider boundary is qualified. Public URLs use canonical IDs.
- Unknown source data remains `null` and its section disappears; it is never guessed or converted to zero.
- `empty_confirmed` requires an authoritative successful provider response. Outages are never cached as empty days.
- Every expensive identical request is single-flight across workers when Redis is configured.
- Provider concurrency, retries, response size, cache cardinality, and request duration are bounded.
- Schedule order defaults to chronology. Product ranking only selects featured/recommended content.
- P2B data is exposed only through provider capability interfaces and documentation until a legitimate source supplies it.
- Each task follows red, green, refactor: add the focused failing test, observe the expected failure, implement the smallest coherent change, rerun the focused test, then run the relevant regression suite.

## Public domain and API contract

`soccer_scanner/domain/models.py` defines `FixtureState` values `success`, `partial`, `stale`, `empty_confirmed`, `provider_unavailable`, `rate_limited`, and `invalid_request`; `ProviderStatus`; immutable `ProviderOutcome`; cache observations; and `FixtureUnavailable`.

`/api/v2/fixtures` becomes canonical. It returns `state`, `date`, `timezone`, `matches`, `lastUpdated`, `providers`, `coverage`, `cache`, and `sourceStats`. Each match uses `canonicalFixtureId`, `providerIds`, `utcDate`, `localDate`, structured `status`, canonical teams/competition, score, verified optional fields, sources, freshness, and data quality. `/api/matches-today` remains a compatibility alias for this release.

Errors always use `{"error":{"code":"provider_unavailable","message":"Fixture providers are temporarily unavailable.","retryable":true,"retryAfterSeconds":30,"lastSuccessfulUpdate":null,"requestId":"..."}}`.

## File map

### Create

- `soccer_scanner/version.py` and `build_info.py` for immutable release identity.
- `soccer_scanner/observability.py` for request IDs, structured logs, and bounded metrics.
- `soccer_scanner/domain/models.py` and `domain/identity.py` for typed outcomes and canonical identities.
- `soccer_scanner/providers/http.py`, `providers/espn.py`, and `providers/football_data.py` for isolated provider transport/normalization.
- `soccer_scanner/services/cache_backend.py`, `rate_limit.py`, `team_identity.py`, `fixture_service.py`, and `team_service.py` for orchestration.
- `soccer_scanner/ranking/featured_match.py` and `soccer_scanner/data/team-provider-map.json`.
- `static/js/app-store.js`, `refresh-controller.js`, `favorites.js`, `calendar.js`, `ics.js`, `pwa.js`, `static/sw.js`, manifest, icons, and social image.
- Team, competition, privacy, 404, and 500 templates.
- Sanitized provider fixtures plus focused Python, browser, load, production-smoke, accessibility, and visual tests.
- `docs/data-sources.md`, `provider-mapping.md`, `testing.md`, `provider-capabilities.md`, and `CHANGELOG.md`.

### Modify

- Application factory/config/routes, legacy services, templates, dashboard modules/styles, `package.json`, Playwright config, `requirements.txt`, `.env.example`, README/docs, CI, and Railway configuration.

## Task 1: Freeze baseline and expose release identity

**Files:** audit, `version.py`, `build_info.py`, health routes, app factory, base template, `tests/test_build_info.py`, `tests/test_app.py`.

1. Preserve `docs/audits/soccer-scanner-audit.md` as pre-change evidence.
2. Add failing tests for `BuildInfo` precedence, production SHA validation, `/health/version`, build metadata in readiness, and template context.
3. Implement `load_build_info(environ)`. Use `APP_VERSION` or repository version; use `GIT_COMMIT_SHA` or `RAILWAY_GIT_COMMIT_SHA`; fail production startup on missing/malformed SHA; allow `unknown` only in development/test.
4. Inject `build.assetVersion` into every CSS/classic script. Propagate it through dynamic ES-module imports derived from `import.meta.url`.
5. Add a browser assertion that every first-party JS/CSS URL is versioned and no first-party asset fails.
6. Run focused tests; commit `feat: expose immutable build identity`.

## Task 2: Provider transport, outcomes, and observability

**Files:** domain models, `providers/http.py`, `observability.py`, config, health, provider/observability tests.

1. Add failing tests for connection/read timeout, transient-only retry, exponential jitter, bounded `Retry-After`, budget exhaustion, content type, malformed JSON, and response-size limit.
2. Implement one pooled `requests.Session` per provider with configured pool bounds. Never log keys, bodies, query secrets, or scores.
3. Add typed provider outcomes and failure categories.
4. Add bounded thread-safe counters/timers and `/health/metrics`.
5. Validate/generate `X-Request-ID`, echo it, and emit structured request/provider summaries.
6. Add log-redaction tests; commit `feat: add bounded provider transport and observability`.

## Task 3: Shared cache, single-flight, and rate limits

**Files:** `cache_backend.py`, `rate_limit.py`, config, app factory, requirements, tests.

1. Add deterministic clock tests for fresh/stale/miss/eviction/fill metrics and maximum key/value sizes.
2. Add concurrent tests proving one loader for identical keys and independent loaders for distinct keys.
3. Implement matching `MemoryCacheBackend` and `RedisCacheBackend` JSON contracts. Redis uses namespaced keys, TTLs, token-owned locks, bounded waits, and safe unlock.
4. Use Redis in production via `REDIS_URL`; allow explicit local/test memory fallback and report degraded coordination in readiness.
5. Canonicalize keys and reject unknown/high-cardinality parameters.
6. Add per-IP/global token-bucket limits with `Retry-After` and stable errors.
7. Add fake-Redis CI and optional two-process integration coverage; commit `feat: coordinate provider cache and rate limits`.

## Task 4: Normalize ESPN without fabricated metadata

**Files:** `providers/espn.py`, sanitized contracts, ESPN tests, legacy analytics.

1. Add provider contracts for every required status, missing optional fields, cup metadata, malformed competitors, nullable scores, and accented/non-European teams.
2. Test scheduled, delayed, in-progress, half-time, extra-time, penalties, finished, postponed, cancelled, suspended, abandoned, and unknown status mapping.
3. Emit provider-qualified teams and preserve raw status. Unknown never becomes scheduled.
4. Populate season/stage/round/matchday/venue/referee/aggregate/penalties/source update only when sourced.
5. Fetch one inclusive provider-date range per league; use individual dates only after an observable range rejection/malformed response.
6. Remove legacy conversion/debug prints and prove normal two-date fan-out is at most 20 calls.
7. Commit `fix: normalize ESPN fixtures without invented metadata`.

## Task 5: Canonical provider-aware team identity

**Files:** identity domain/service, mapping JSON, API, team drawer, tests/docs.

1. Add mapped, unmapped, malformed, normalized-alias, and ambiguous identity tests.
2. Use Unicode/case/punctuation normalization only to find candidates; resolve only through unique maintained mappings or corroborating provider attributes.
3. Emit `canonicalId`, `provider`, `providerId`, and `providerIds`.
4. Add `GET /api/v2/teams/<canonical_id>/analysis` and reject raw provider IDs there.
5. Request only a compatible identity from the drawer; render a terminal useful unavailable state when none exists.
6. Log safe unresolved counts; commit `fix: qualify team identities across providers`.

## Task 6: Canonical fixture identity and field-level merge

**Files:** identity, Football-data adapter, fixture service, fixture identity tests.

1. Test same fixture/different IDs, kickoff tolerance edges, reversed teams, same time/different teams, and freshness conflicts.
2. Derive `canonicalFixtureId` from canonical competition, ordered home/away identities, UTC kickoff tolerance, and optional season/stage evidence.
3. Store provider IDs separately. Merge status/score/kickoff/crest/venue/matchday/stage/emblem by explicit reliability and freshness rules.
4. Retain all sources/missing fields and remove provider-ID-only deduplication.
5. Commit `fix: deduplicate fixtures across provider namespaces`.

## Task 7: Truthful fixture orchestration

**Files:** fixture service, API, app factory, fixture-state/API tests.

1. Test every state: full success, partial, stale, authoritative empty, total unavailable, rate limited, invalid input, optional provider disabled, and five-plus ESPN fixtures with failed leagues.
2. Cache provider ranges independently of timezone composition.
3. Call configured Football-data.org on each provider-cache miss, never from a match-count threshold.
4. Never mix stale provider entries with current results; stale is only the full no-current-data fallback.
5. Raise `FixtureUnavailable` on no authority/no stale; never cache it. Emit `empty_confirmed` only from an authoritative complete response.
6. Bound workers to eight, stop submissions at soft deadline, cancel pending, await running bounded-timeout work, and shut down with `wait=True`.
7. Assert no provider thread survives a response.
8. Migrate UI to `/api/v2/fixtures` while keeping the compatibility alias.
9. Commit `fix: distinguish empty schedules from provider outages`.

## Task 8: Correct date, timezone, analytics, and ranking

**Files:** API, fixture service, featured ranking, legacy analytics, fixtures JS, tests.

1. Test impossible dates, invalid IANA zones, DST edges, local midnight, and all required timezones.
2. Validate client/server; cap date windows; canonicalize zones; compute local day/time slots with `ZoneInfo`.
3. Remove estimated attendance and heuristic broadcasts from verified context; rename any remaining ranking signal as an estimate.
4. Default schedule order to local kickoff and use favorite/status-aware deterministic featured ranking.
5. Add a URL-backed timezone selector; commit `fix: make fixture dates and ranking timezone-correct`.

## Task 9: Centralize browser state, history, and filters

**Files:** `app-store.js`, fixture modules/template/CSS, state/history Playwright spec.

1. Reproduce stale competition, clear/debounce, date/debounce, Back/Forward, filtered selection, invalid date, and query-canonicalization defects.
2. Build one immutable store with `dispatch`, request sequence tokens, and canonical URL parse/serialize.
3. Cancel debounce/obsolete fetches before committed changes.
4. Use `pushState` for date/status/competition/sort/detail; `replaceState` for search; reconstruct on `popstate`.
5. Reconcile filters after every response and clear out-of-result selection.
6. Add supported country/favorites/sort/time-window/hide-finished controls, removable mobile chips, and accent-insensitive “Search teams or competitions.”
7. Commit `fix: synchronize fixture state controls and history`.

## Task 10: Adaptive live refresh and classified recovery

**Files:** `refresh-controller.js`, fixture modules/template/CSS, polling/error tests.

1. Fake-clock test live, pre-kickoff, upcoming, and historical intervals.
2. Test visibility pause/resume, no overlap, abort, backoff, `Retry-After`, manual refresh, and preserving old data after failure.
3. Implement one timer/in-flight request, subtle updating announcements, and state preservation.
4. Render distinct invalid date/timezone, rate limit, unavailable, partial, stale, offline, timeout, and format states with guarded retry.
5. Commit `feat: refresh live fixtures without losing user state`.

## Task 11: Responsive dialogs and honest team intelligence

**Files:** context/drawer modules, team service/API, CSS, tests.

1. Test both viewport transitions, nested dialogs, Escape order, date change while open, focus restoration, stale team response, and timeout.
2. Centralize dialog stack/body lock/inert/focus/media-query lifecycle.
3. Fetch minimum shared team datasets concurrently and cache/coalesce by canonical team.
4. Preserve unknown numbers as null/Unavailable; honor provider `played`.
5. Add date, competition, home/away perspective, crests, spoiler-safe result, and stable team link.
6. Commit `fix: make team intelligence provider-aware and responsive`.

## Task 12: Navigation, cards, mobile, and accessibility

**Files:** templates/styles/renderers, `package.json`, accessibility Playwright spec.

1. Add `@axe-core/playwright` checks across fixture/filter/state/dialog/favorite/calendar/team/table/privacy/error surfaces.
2. Add Fixtures, Live, Calendar, Teams, Tables, Favorites navigation with compact mobile behavior.
3. Make cards expose one details action plus separate favorite control, semantic selection, stable height, live text, freshness, and verified venue.
4. Add granular score preference while retaining hidden-by-default/no-leak guarantees.
5. Test skip/focus/dialog/live regions/forms/forced colors/reduced motion/44px targets/safe areas/200 and 400 percent zoom/long names/crests/320px reflow.
6. Correct contrast via shared tokens and keep tables behind explicit spoiler reveal.
7. Commit `feat: complete accessible mobile fixture navigation`.

## Task 13: Security, privacy, SEO, and error pages

**Files:** app factory, routes/pages/templates, manifest/assets, CI, tests.

1. Test production HSTS behind trusted proxy HTTPS, CSP `frame-ancestors`, SofaScore compatibility, no CORS, API cache policy, and crest normalization/restriction.
2. Validate all path/query inputs; add same-origin crest proxy only if reliability/privacy tests justify it.
3. Prove keys never enter logs/responses.
4. Add privacy/data-source pages, canonical/meta/OG/Twitter/theme/icons/manifest with no scores, and useful 404/500 pages.
5. Add dependency/secret scans; commit `feat: harden security privacy and metadata`.

## Task 14: Favorites and personalized matchday

**Files:** `favorites.js`, store/renderer/template/CSS, tests/docs.

1. Test team/competition/fixture persistence, malformed data, favorites-only, Your Matches, favorite-aware feature, import/export, and clear data.
2. Implement versioned schema validation and size limits behind a repository abstraction.
3. Commit `feat: add local personalized matchday favorites`.

## Task 15: Bounded multi-day calendar

**Files:** `calendar.js`, routes/templates/CSS/store, tests.

1. Test previous/next seven days, today, agenda/calendar, jump date, timezone, and bounded prefetch.
2. Load only visible windows; prefetch adjacent composed dates with cancellation/rate awareness.
3. Commit `feat: add bounded multi-day fixture calendar`.

## Task 16: Canonical deep links and spoiler-free ICS

**Files:** page/API routes, `ics.js`, context/renderer, team/competition templates, tests.

1. Test deep-link date loading, selection/surface, hidden scores, expiry, and Copy Link.
2. Persist bounded canonical lookup and add `/fixtures/<canonical_fixture_id>`.
3. Add RFC 5545 one-fixture/visible/favorite-team exports with UTC kickoff, verified venue, canonical link, and no scores.
4. Add stable minimum-data team and competition pages.
5. Commit `feat: add fixture deep links and calendar export`.

## Task 17: Freshness inspector and verified details

**Files:** contracts/services/context/renderer/template/CSS, tests.

1. Test merged sources, freshness, coverage, retry, missing fields, and optional verified detail presence.
2. Add compact freshness label and expandable source inspector.
3. Render optional fields only when sourced.
4. Commit `feat: expose fixture source and freshness evidence`.

## Task 18: Spoiler-safe PWA

**Files:** manifest, service worker, `pwa.js`, base template, PWA tests.

1. Test installability, shell offline, recent non-live fixtures, offline timestamp, refusal to present cached live data as current, and update notice.
2. Precache immutable build-versioned shell assets.
3. Use network-first API behavior and spoiler-filtered visibly stale offline fixture data.
4. Commit `feat: add spoiler-safe offline application shell`.

## Task 19: Provider capability boundaries

**Files:** provider capability type, `docs/provider-capabilities.md`, tests.

1. Define events, lineups, statistics, broadcasts, squads, standings, and notification capabilities.
2. Unsupported capabilities return `not_supported`/`unavailable` and never synthesized content.
3. Document consent/spoiler/quiet-hours notification architecture and legitimate source prerequisites.
4. Commit `docs: define provider gated feature boundaries`.

## Task 20: CI, load, visual, docs, and release

**Files:** Playwright configs/specs/snapshots, load tests, CI, README/docs/env/changelog, production smoke.

1. Add visual states for desktop/mobile default/live/revealed/filters/sheet/drawer/empty/partial/stale/error/favorites.
2. Add simultaneous-key/timezone, multi-worker, slow-provider, 429-burst, team-coalescing, expiration, and Redis-fallback load checks.
3. CI installs deterministically and runs Python 3.12, all JS syntax, Chromium/WebKit, axe, build checks, dependency/secret scans, and safe artifacts.
4. Document all endpoints/schema/providers/cache/Redis/rate limit/spoilers/timezones/development/deployment/extension/PWA/testing.
5. Production smoke accepts `BASE_URL` and `EXPECTED_SHA`; checks root/live/ready/version, exact SHA/environment/assets, fixture state or stable error, console/assets, hidden-score safety, and 320px reflow.
6. Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`, compileall, `node --check` for every JS file, Chromium, WebKit, `git diff --check`, and security audits.
7. Commit `docs: complete production release evidence`.
8. Push the reviewable series to `main` after all local checks pass, observe Railway to terminal `SUCCESS`, run production smoke with the exact pushed SHA, verify custom-domain asset tokens, and finish with a clean tree synchronized to `origin/main`.

## Completion report

The final handoff lists baseline root causes, bugs reproduced/fixed, files and commits, provider/identity/schema decisions, UX/accessibility/security changes, exact test results, load/performance comparison, Railway deployment ID/SHA, live proof, provider limitations, Redis/Football-data.org migration steps, and intentionally deferred provider-gated features.
