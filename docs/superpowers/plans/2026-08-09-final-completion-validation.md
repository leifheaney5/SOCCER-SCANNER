# Soccer Scanner Final Completion and Production Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining correctness, resilience, consistency, documentation, release-validation, and production-verification gaps without adding routes, expanding navigation, or reactivating Team Intelligence.

**Architecture:** Keep the existing URL-backed state, canonical fixture service, typed match-status module, provider outcome model, Redis cache, and SwiftUI client. Make timezone a shared renderer input, preserve selection through the existing state/load pipeline, model calendar results per day, give providers one absolute deadline with bounded concurrency, and extend existing registry/configuration seams only where current behavior is incomplete.

**Tech Stack:** Flask/Python, pytest, vanilla JavaScript ES modules, Node test runner, Playwright Chromium/WebKit with axe, SwiftUI/XcodeGen in macOS CI, GitHub Actions, Railway.

## Global Constraints

- Do not add application routes or expand primary navigation.
- Do not add or expand Team Intelligence; leave dormant compatibility code alone unless a crash or release blocker requires a minimal guard.
- Preserve spoiler safety, guest-only behavior, URL-backed date/timezone/filter/fixture state, canonical fixture IDs, typed provider outcomes, Redis caching, and existing deployment configuration.
- Do not add dependencies or modify CI/infrastructure configuration unless the existing repository tests prove it is required; all Python and JavaScript versions remain pinned as already configured.
- Use provider-owned values only; do not invent crest, streaming, standings, season, tournament, or fixture data.
- Any iOS compilation claim requires the macOS GitHub Actions result; Windows checks can validate source assets and test fixtures only.
- Run focused red-green tests before each production behavior change, then run the complete verification matrix before release.

---

### Task 1: Establish the audited baseline and reproduce timezone defects

**Files:**
- Create: `docs/audits/2026-08-final-completion-validation.md`
- Modify: `tests/browser/history-restoration.spec.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- Consumes: existing fixture payload helpers, Playwright web server, `state.timezone`, `state.fixture`, and `match-context.js` rendering.
- Produces: a reproducible regression test and an evidence record separating local, CI, production, and macOS verification.

- [ ] **Step 1: Record the baseline evidence**

Record the current `main` SHA, application version, migration revision, production `/health/version`, Railway deployment state, Python/Node/npm versions, existing Python/Node/browser/audit results, iOS local release-asset results, and the known Pages artifact failure. Mark each evidence source as local, CI, production, or macOS.

- [ ] **Step 2: Add a failing timezone/detail test**

Add a browser test with a fixed UTC kickoff and a browser timezone different from the selected timezone. Select the fixture while `America/New_York` is active, assert the card kickoff, detail `Local kickoff`, and source timestamp use the selected zone, then select `Europe/London` and assert the selected fixture remains open and the URL contains the preserved fixture plus the new timezone. Use a fixture crossing a UTC midnight boundary so the expected local date is explicit.

- [ ] **Step 3: Run the focused test and verify the expected failure**

Run `npx playwright test tests/browser/history-restoration.spec.js --project=chromium --grep "timezone.*selected fixture|selected timezone.*detail"`.

Expected baseline failures are the browser-local detail timestamp and the cleared selection/date after timezone change; no production code is changed before this failure is observed.

- [ ] **Step 4: Save the baseline closeout skeleton**

Create the closeout matrix with rows for each requested requirement and columns `Implemented`, `Unit tested`, `Browser tested`, `CI verified`, `Production verified`, and `Notes`. Leave unverified cells explicitly marked `pending`, `not applicable`, or `not verified` until evidence exists.

### Task 2: Make timezone formatting and selected-fixture preservation authoritative

**Files:**
- Modify: `static/js/time-zone.js`
- Modify: `static/js/fixture-renderer.js`
- Modify: `static/js/match-context.js`
- Modify: `static/js/fixtures.js`
- Modify: `static/js/calendar.js`
- Modify: `soccer_scanner/routes/pages.py`
- Modify: `tests/browser/history-restoration.spec.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`
- Modify: `tests/browser/calendar.spec.js`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `formatKickoff`, `formatDateTime`, `calendarDateInZone`, `resolveTimeZone`, the existing dashboard state, and canonical fixture route logic.
- Produces: renderers that accept the active IANA timezone, one centralized timezone-change operation, timezone-preserving copy/deep links, and correct server-side fixture-date derivation.

- [ ] **Step 1: Extend the failing tests for all date boundaries**

Cover UTC → `America/New_York`, New York → `Europe/London`, `Pacific/Auckland` → `America/Los_Angeles`, backward and forward local-date changes, mobile dialog reopening, desktop panel preservation, stale/partial fixture payloads, and browser back/forward restoration. Assert filters other than date/timezone remain unchanged and that only the expected history entry is added.

- [ ] **Step 2: Pass the selected timezone through every web renderer**

Replace browser-local `toLocaleString()` calls in match context, summary/freshness, calendar, and any fixture-detail path with the shared formatter. Keep relative freshness calculations relative, but format absolute source/update timestamps using `formatDateTime(value, activeTimeZone)` and expose the zone label where ambiguity would remain. Make `createMatchContext` receive `getTimezone: () => state.timezone` and use the same zone for kickoff, source inspector, and copied-link state.

- [ ] **Step 3: Centralize timezone changes around the selected fixture**

Capture `selectedFixtureId` and the selected match before changing state. Compute `nextDate = calendarDateInZone(selectedMatch.utcDate, nextTimezone)`, update `state.timezone` and `state.date` together, preserve compatible filters, sync the URL once, load the requested day, and reopen the same fixture only after the response contains it. If the fixture is absent or the response is partial/stale, retain the selection intent and show the existing safe unavailable state without opening stale detail content. Preserve desktop/mobile presentation and focus through the existing dialog manager.

- [ ] **Step 4: Preserve timezone context in fixture links**

Add the selected timezone to copied fixture links without adding score values. Update the canonical fixture page route/template only as needed to derive or pass the correct date for the requested timezone while preserving existing route behavior and no new routes.

- [ ] **Step 5: Run focused green verification**

Run the timezone unit tests plus the targeted Chromium and WebKit browser tests. Confirm kickoff, summary freshness, source timestamps, calendar labels, copied links, deep links, and selected-fixture presentation all use the same explicit timezone.

### Task 3: Remove duplicate status interpretation and complete streaming presentation

**Files:**
- Modify: `static/js/match-context.js`
- Modify: `static/js/fixture-renderer.js`
- Modify: `static/js/calendar.js`
- Modify: `static/js/standings.js`
- Modify: `soccer_scanner/services/streaming.py`
- Modify: `soccer_scanner/data/streaming-services.json`
- Modify: `static/css/fixtures.css`
- Modify: `tests/match-status.test.mjs`
- Modify: `tests/browser/fixtures-dashboard.spec.js`
- Modify: `tests/browser/streaming.spec.js`
- Modify: `tests/browser/accessibility.spec.js`
- Modify: `tests/test_streaming_registry.py`
- Modify: `tests/test_streaming_enrichment.py`

**Interfaces:**
- Consumes: the canonical status contract in `static/js/match-status.js`, provider streaming registry entries, and existing verified `officialUrl`/region fields.
- Produces: identical status labels/classes/descriptions across cards, featured content, calendar, and detail; compact service logo/icon presentation with safe fallbacks.

- [ ] **Step 1: Add failing status and streaming assertions**

Assert every canonical status, including half time, extra time, penalties, delayed, suspended, and abandoned, renders the same short label and accessible description in cards and detail. Add tests for local service logos, missing logos, multiple services, unknown regions, absent official URLs, legacy broadcast arrays, broken-image fallback, and explicit image dimensions.

- [ ] **Step 2: Replace local match-context status logic**

Import the canonical status module into `match-context.js`, remove `sentenceCase`, `statusText`, and raw status branching, and use the canonical label/description/group for detail output and CSS classes. Keep unknown provider values unknown; do not infer a precise state.

- [ ] **Step 3: Add registry-owned streaming logo metadata and safe rendering**

Extend only existing verified registry entries with local logo paths where assets exist. Render a compact primary icon/name/region/`+N` summary on cards and every verified service with icon, name, region, and official link in detail. Use a generic inline broadcast icon when no local logo exists, keep the service name visible, set explicit dimensions, use decorative `alt=""`, and retain `noopener noreferrer` links only for verified official URLs.

- [ ] **Step 4: Verify responsive and accessibility behavior**

Run focused Chromium/WebKit streaming and axe tests at 320px, 200%, and 400% zoom. Assert no broken images, no layout shift from missing logos, correct link semantics, and no console errors.

### Task 4: Make calendar results independently resilient and score-toggle local

**Files:**
- Modify: `static/js/calendar.js`
- Modify: `static/css/calendar.css`
- Modify: `tests/browser/calendar.spec.js`
- Modify: `tests/browser/accessibility.spec.js`

**Interfaces:**
- Consumes: the existing bounded calendar request worker, per-date API payloads, score preference module, and shared timezone formatters.
- Produces: a per-day result map with stale-request protection, day-level retry, and zero network requests when toggling scores.

- [ ] **Step 1: Add failing per-day and request-count tests**

Intercept seven date requests and make one, three, or all dates fail with typed unavailable/rate-limited responses. Assert successful days remain rendered, failed days expose a heading/status/retry control, retrying one date updates only that day, stale week responses cannot overwrite a newer week, and reveal/hide score changes perform zero fixture requests while preserving failures and scroll/view state.

- [ ] **Step 2: Introduce the per-day result state**

Store `{state, payload, error, requestId}` per date in the existing calendar module. Use bounded workers, abort the previous request set on navigation, ignore responses whose generation is stale, render each day independently, and expose retry-one/retry-failed/all actions without replacing successful days.

- [ ] **Step 3: Rerender score presentation from cached payloads**

Keep loaded payloads in memory and connect the score preference listener to calendar rerender only. Do not call the fixture endpoint or modify URL date/timezone state from score toggles.

- [ ] **Step 4: Run focused browser and axe verification**

Run calendar tests in Chromium and WebKit and the relevant accessibility tests. Confirm day-level announcements are meaningful and background refreshes do not repeatedly steal focus.

### Task 5: Add standings season-review protection

**Files:**
- Modify: `soccer_scanner/data/standings-seasons.json`
- Modify: `soccer_scanner/services/standings.py`
- Modify: `templates/league_tables.html`
- Modify: `static/js/standings.js`
- Modify: `tests/test_standings_seasons.py`
- Modify: `tests/browser/standings.spec.js`

**Interfaces:**
- Consumes: existing external standings configuration and provider embed response handling.
- Produces: deterministic split-year/calendar-year/edition expectations, verification metadata checks, and a restrained stale configuration warning without fabricated season IDs or replacement data.

- [ ] **Step 1: Add failing configuration and rendering tests**

Cover valid current split-year season, expired `reviewBy`, wrong expected season, calendar-year competition, tournament edition, missing season metadata, missing configuration, and invalid provider responses. Assert stale configurations warn and do not display unverified tables.

- [ ] **Step 2: Implement typed review state**

Add explicit season type and verification metadata validation. Calculate expected season from the configured competition type and supplied date, compare `reviewBy` and provider recognition, return typed review states, and keep existing provider errors generic.

- [ ] **Step 3: Render the restrained warning**

Render `This standings configuration is awaiting season verification.` when review is required, preserve consent/legal behavior, and avoid silently showing stale tables.

### Task 6: Run fixture providers concurrently under one shared deadline

**Files:**
- Modify: `soccer_scanner/services/fixture_service.py`
- Modify: `soccer_scanner/providers/http.py`
- Modify: `soccer_scanner/services/provider_health.py`
- Modify: `tests/test_fixture_service.py`
- Modify: `tests/test_provider_health_routes.py`

**Interfaces:**
- Consumes: existing provider adapters, cache/single-flight coordination, typed `ProviderOutcome`, and request budget/deadline utilities.
- Produces: bounded concurrent provider execution with one absolute deadline, deterministic composition, accurate timeout/exception/provider-health outcomes, and provider-specific stale fallback.

- [ ] **Step 1: Add failing timing/outcome tests**

Test both providers fast, either provider slow while the other succeeds, provider exceptions, timeout of one or both, stale fallback, deterministic ordering, duplicate-ID protection, and total elapsed time bounded by one request budget rather than provider count.

- [ ] **Step 2: Implement bounded concurrent orchestration**

Use a bounded standard-library executor or the existing task abstraction. Compute one monotonic deadline before dispatch, pass remaining budget to every provider-owned request, collect completed outcomes until the deadline, mark unfinished work typed/unavailable, and never leak provider exceptions or request context across workers.

- [ ] **Step 3: Verify cache and health behavior**

Run the focused service, cache, rate-limit, provider-health, and API tests. Confirm stale data remains available where permitted and provider health records actual outcomes without multiplying the request deadline.

### Task 7: Align documentation, SEO, summary freshness, and release evidence

**Files:**
- Modify: `static/js/fixture-renderer.js`
- Modify: `static/js/calendar.js`
- Modify: `templates/base.html`
- Modify: `templates/index.html`
- Modify: `templates/calendar.html`
- Modify: `templates/league_tables.html`
- Modify: `soccer_scanner/routes/pages.py`
- Modify: `tests/test_public_routes.py`
- Modify: `tests/test_app.py`
- Modify: `tests/browser/branding.spec.js`
- Modify: `tests/browser/accessibility.spec.js`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/architecture.md`
- Modify: `docs/api.md`
- Modify: `docs/data-sources.md`
- Modify: `docs/testing.md`
- Modify: `docs/deployment.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/decisions/accounts-and-preferences.md`
- Modify: `clients/ios/README.md`
- Create: `tests/test_documentation_consistency.py`

**Interfaces:**
- Consumes: existing route inventory, meta/robots/sitemap helpers, selected timezone state, and the guest-mode account decision.
- Produces: truthful documentation, explicit timezone summary/freshness labels, existing-route-only SEO metadata, and a closeout matrix backed by evidence.

- [ ] **Step 1: Add failing consistency and SEO tests**

Assert no active documentation claims persistent favorites, local-storage favorites, persistent score preferences, accounts, or cross-device synchronization. Assert sitemap excludes APIs, health, offline, disabled surfaces, and noindex Terms; assert canonical/OG/Twitter tags are unique and score-safe; assert robots differs correctly by environment; assert favicon, manifest, and OG image resolve.

- [ ] **Step 2: Correct summary/freshness and metadata**

Use the selected timezone for absolute update/source/stale timestamps. Preserve relative freshness where useful, add a clear zone context, remove duplicate or contradictory metadata, and keep existing SEO route boundaries and spoiler protections.

- [ ] **Step 3: Correct guest-mode and native documentation**

State that the product is guest-only, has no persistent favorites or accounts, uses session-scoped score visibility, supports URL-backed timezone/fixture state, has no cross-device sync or notifications, and does not read legacy browser favorite keys. Keep historical decision documents explicitly historical/negated.

- [ ] **Step 4: Update the closeout matrix with evidence**

For every requirement, record the exact test command, CI run or URL, and limitation. Do not mark macOS/device-only items as verified from Windows.

### Task 8: Complete iOS release-readiness and exact deployment validation

**Files:**
- Modify: `clients/ios/README.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/deployment.md`
- Modify: `tests/production-smoke.mjs`
- Modify: `tests/browser/fixtures-dashboard.spec.js`
- Modify: `tests/browser/streaming.spec.js`
- Modify: `tests/browser/accessibility.spec.js`

**Interfaces:**
- Consumes: existing macOS iOS workflow, native API/deep-link/legal tests, Railway deployment identity, and the production smoke script.
- Produces: release evidence that distinguishes Windows checks, macOS CI, and physical-device limitations; exact SHA smoke coverage for health, API, assets, timezone, spoiler safety, streaming, legal links, and responsive behavior.

- [ ] **Step 1: Add failing smoke assertions for the remaining required surfaces**

Extend production smoke with exact SHA, asset-token, fixture-state/unique-ID, scores-hidden DOM/accessibility, timezone control, no console/first-party asset failures, streaming, Terms, favicon, manifest, and 320px checks. Keep fixture data assertions score-safe.

- [ ] **Step 2: Verify native release gates without fabricating identifiers**

Run local source asset/simulator/deep-link tests and inspect entitlements/AASA/legal gates. Document that Swift compilation, VoiceOver, Dynamic Type, safe areas, signed Universal Links, network transitions, and TestFlight installation require macOS/device evidence.

- [ ] **Step 3: Run the full local matrix and macOS CI**

Run Python, compile, Node, npm audit, requirements-scoped pip audit, Chromium, WebKit, axe, production-smoke invariants, and iOS release-asset tests locally. Push the branch for GitHub CI and record Python/Node/Playwright/accessibility/dependency/iOS results by run URL.

- [ ] **Step 4: Deploy only the merged intended SHA and verify production**

After merge, confirm Railway `web` reaches terminal `SUCCESS`, compare `/health/version.commitSha` and `/health/ready.build.commitSha` to `git rev-parse HEAD`, run `BASE_URL=https://soccerscanner.pro EXPECTED_SHA=<full-sha> EXPECTED_ENVIRONMENT=production npm run smoke:production`, and save the output in the closeout evidence.

### Task 9: Final diff review and handoff

**Files:**
- Modify: `docs/audits/2026-08-final-completion-validation.md`

**Interfaces:**
- Consumes: the complete test/CI/production evidence and final Git diff.
- Produces: a clean release branch, an auditable closeout, and an explicit list of verified, unverified, deferred, and unrelated external failures.

- [ ] **Step 1: Review scope and invariants**

Inspect `git diff --check`, `git diff --stat`, route inventory, navigation, Team Intelligence references, spoiler paths, dependency files, secrets scan, and generated artifacts. Confirm no new routes, navigation destinations, Team Intelligence expansion, score leakage, or dependency changes slipped in.

- [ ] **Step 2: Run the final complete verification matrix**

Repeat the full local matrix and live smoke after the last code/doc change. Record exact counts and terminal statuses, including any GitHub Pages artifact failure that is outside the application deployment.

- [ ] **Step 3: Integrate and report**

Commit the scoped changes without co-author trailers, push, merge into `main`, verify Railway and production identity, and report the commit, PR, deployment, live SHA, tests, unresolved limitations, and closeout path.
