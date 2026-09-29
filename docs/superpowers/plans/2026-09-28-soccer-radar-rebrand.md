# Soccer Radar Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the fixture-load fix and a coherent Soccer Radar rebrand with `https://soccer-radar.com` as canonical, while preserving `soccerscanner.pro` routes and existing app links.

**Architecture:** Keep the current Flask service, API contract, iOS bundle ID, storage namespaces, and visual system. Configure the new public origin, redirect legacy content requests to equivalent new-host URLs, update web and iOS user-facing identities, and keep both hosts associated with Universal Links. Serve AASA directly on each host. Attach and verify the new hostname on the existing Railway web service before changing its production canonical-origin variable.

**Tech Stack:** Flask, pytest, Jinja, vanilla JavaScript ES modules, Node `node:test`, Playwright Chromium/WebKit, Swift/XcodeGen, GitHub Actions, Railway.

**Spec:** `docs/superpowers/specs/2026-09-28-soccer-radar-rebrand.md`

## Global Constraints

- Product name: `Soccer Radar`; canonical website origin: `https://soccer-radar.com`.
- Keep `soccerscanner.pro` active, redirect its public content routes and query strings to the corresponding new-host URL, and retain it in Universal Link configuration.
- Serve `/.well-known/apple-app-site-association` directly on both hosts; Apple Universal Links cannot use a redirected AASA file.
- Preserve the existing layout, colors, app icon geometry, bundle ID, repo/package/service identifiers, cache keys, and browser-storage keys. Keep the existing `streaming` API field compatible; add `whereToWatch` for TV plus streaming options.
- Do not submit an App Store/TestFlight build; a macOS iOS workflow must verify source changes.
- Do not change production domain or variables until Railway's required DNS target and TLS are verified.
- Keep dated audits, release evidence, and historical plans unchanged; update current docs and metadata.

## Review Focus

- A legacy host with a port, mixed case, or trailing dot still redirects to the configured canonical origin, while an unknown host cannot control `Location`.
- Redirects preserve encoded paths and query strings for fixture deep links, calendar downloads, and API GET requests.
- Both AASA routes serve valid configured JSON directly; the legacy AASA request is exempt from the content redirect.
- An unrecognized host never becomes a redirect destination, and Railway health probes continue to reach readiness; AASA remains absent when Apple identifiers are unset and serves valid JSON on both hosts when configured.
- Rebranding does not change the bundle ID, public fixture IDs, browser storage keys, or hidden-score behavior.

---

### Task 1: Canonical web origin and legacy-host redirects

**Files:**
- Modify: `soccer_scanner/config.py`
- Modify: `soccer_scanner/__init__.py`
- Test: `tests/test_public_routes.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `PUBLIC_BASE_URL` and Flask's configured request host.
- Produces: a configured `LEGACY_PUBLIC_HOSTS` tuple and an application-level redirect to the configured public origin for requests addressed to `soccerscanner.pro`.

- [x] **Step 1: Add failing host and origin tests**

```python
def test_legacy_domain_redirect_preserves_path_and_query(self):
    app = create_app({'TESTING': True, 'PUBLIC_BASE_URL': 'https://soccer-radar.com'})
    response = app.test_client().get(
        '/fixtures/fx_0123456789abcdef01234567?date=2026-08-05&timezone=UTC',
        headers={'Host': 'soccerscanner.pro'},
        follow_redirects=False,
    )

    self.assertEqual(response.status_code, 301)
    self.assertEqual(
        response.headers['Location'],
        'https://soccer-radar.com/fixtures/fx_0123456789abcdef01234567?date=2026-08-05&timezone=UTC',
    )


def test_legacy_domain_redirect_preserves_percent_encoding(self):
    app = create_app({'TESTING': True, 'PUBLIC_BASE_URL': 'https://soccer-radar.com'})
    response = app.test_client().get(
        '/fixtures/fx%2F012345?filter=home%2Faway',
        headers={'Host': 'soccerscanner.pro'},
        environ_overrides={'RAW_URI': '/fixtures/fx%2F012345?filter=home%2Faway'},
        follow_redirects=False,
    )

    self.assertEqual(response.status_code, 301)
    self.assertEqual(
        response.headers['Location'],
        'https://soccer-radar.com/fixtures/fx%2F012345?filter=home%2Faway',
    )


def test_canonical_domain_does_not_redirect(self):
    app = create_app({'TESTING': True, 'PUBLIC_BASE_URL': 'https://soccer-radar.com'})
    response = app.test_client().get('/', headers={'Host': 'soccer-radar.com'}, follow_redirects=False)
    self.assertEqual(response.status_code, 200)


def test_unknown_host_does_not_redirect(self):
    app = create_app({'TESTING': True, 'PUBLIC_BASE_URL': 'https://soccer-radar.com'})
    response = app.test_client().get('/', headers={'Host': 'attacker.example'}, follow_redirects=False)
    self.assertNotEqual(response.status_code, 301)
    self.assertIsNone(response.headers.get('Location'))


def test_aasa_is_served_directly_on_both_hosts(self):
    app = create_app({
        'TESTING': True,
        'APPLE_TEAM_ID': 'ABCDE12345',
        'APPLE_BUNDLE_ID': 'pro.soccerscanner.app',
    })
    client = app.test_client()

    for host in ('soccerscanner.pro', 'soccer-radar.com'):
        with self.subTest(host=host):
            response = client.get(
                '/.well-known/apple-app-site-association',
                headers={'Host': host},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'application/json')
```

Run: `python -m pytest tests/test_public_routes.py -q`

Expected: legacy-host tests fail because redirects do not exist yet; the existing configured-origin consumers still use the old default.

- [x] **Step 2: Implement a configured-origin redirect**

Add the new default origin and the exact legacy-host allowlist to `Config`. Register a `before_request` handler after request-observation setup. Exempt the AASA path so it is served directly on both hosts. Normalize `request.host` only for comparison; construct `Location` from the configured base plus the raw request target path and original query bytes. Preserve percent-encoding using the server-provided raw URI when available, with a safe path fallback. Never use incoming host or forwarded-host headers to construct the destination:

```python
host = request.host.partition(':')[0].rstrip('.').lower()
if host in app.config['LEGACY_PUBLIC_HOSTS'] and request.path != '/.well-known/apple-app-site-association':
    raw_uri = request.environ.get('RAW_URI')
    raw_path = raw_uri.partition('?')[0] if raw_uri else request.path
    location = f"{app.config['PUBLIC_BASE_URL']}{raw_path}"
    if request.query_string:
        location = f"{location}?{request.query_string.decode('latin-1')}"
    return redirect(location, code=301)
```

Keep existing `PUBLIC_BASE_URL` consumers as the canonical source for page metadata, sitemap, robots, AASA and fixture calendar links. Do not derive redirect destinations from request headers.

- [x] **Step 3: Verify route contracts**

Run: `python -m pytest tests/test_public_routes.py tests/test_app.py -q`

Expected: legacy content paths and queries redirect to the new origin; canonical-host pages remain 200; both hosts serve AASA without redirect; existing route, readiness, and security tests pass.

---

### Task 2: Web brand, metadata, and PWA identity

**Files:**
- Modify: `templates/base.html` and current page templates under `templates/`
- Modify: `templates/404.html`, `templates/500.html`, `templates/offline.html`
- Modify: `static/manifest.webmanifest`, `static/favicon.svg`, `static/js/pwa.js`
- Modify: `tests/browser/branding.spec.js`, `tests/browser/pwa.spec.js`

**Interfaces:**
- Consumes: the canonical public origin injected by `soccer_scanner/__init__.py` and the existing product visual tokens.
- Produces: Soccer Radar text and metadata across rendered website and installed PWA surfaces without changing page behavior or layout.

- [x] **Step 1: Update web acceptance assertions first**

Change branding assertions to expect `Soccer Radar home`, the Soccer Radar footer, and the Soccer Radar manifest name. Add assertions that canonical and Open Graph URLs, sitemap, and robots output use `https://soccer-radar.com` under the production config.

Run: `npx playwright test tests/browser/branding.spec.js tests/browser/pwa.spec.js --project=chromium`

Expected: the updated identity assertions fail against current Soccer Scanner text and manifest values.

- [x] **Step 2: Update visible and machine-readable identity**

Replace current customer-facing name strings in page titles, header and footer labels, error/offline copy, JSON-LD, Open Graph, Twitter metadata, PWA manifest and update notice. Set `PUBLIC_BASE_URL` defaults and URL examples to the new canonical origin. Change the favicon's accessible label while preserving its SVG geometry and existing CSS/color tokens. Leave technical `soccer-scanner:*` storage/cache names untouched.

- [x] **Step 3: Verify web identity and route metadata**

Run: `npx playwright test tests/browser/branding.spec.js tests/browser/pwa.spec.js --project=chromium --project=webkit`

Run: `python -m pytest tests/test_public_routes.py tests/test_app.py -q`

Expected: both browsers report Soccer Radar identity; canonical, social, sitemap and robots URLs use the new origin; page layout and existing spoiler controls remain unchanged.

---

### Task 3: iOS display name, metadata, and dual-domain links

**Files:**
- Modify: `clients/ios/SoccerScanner/Info.plist`
- Modify: `clients/ios/project.yml`
- Modify: `clients/ios/SoccerScanner/SoccerScanner.entitlements`
- Modify: `clients/ios/SoccerScanner/Config/AppEnvironment.swift`
- Modify: `clients/ios/SoccerScanner/Features/Settings/SettingsView.swift`
- Modify: `clients/ios/SoccerScanner/Support/DeepLink.swift`
- Modify: `clients/ios/fastlane/metadata/en-US/`
- Modify: `clients/ios/README.md`
- Test: `tests/test_ios_release_assets.py`
- Test: `clients/ios/SoccerScannerTests/TimeZoneAndDeepLinkTests.swift`

**Interfaces:**
- Consumes: the existing production API path, bundle identifier `pro.soccerscanner.app`, AASA route, and deep-link host allowlist.
- Produces: the Soccer Radar display/store identity and support for both `soccer-radar.com` and `soccerscanner.pro` Universal Links.

- [x] **Step 1: Pin the app identity and host compatibility**

Update source-contract assertions for the display name, website, marketing URL, AASA entitlements for both domains, and unchanged bundle identifier. Add deep-link tests that accept equivalent fixture links on both hosts and continue rejecting an unrelated host.

Run: `python -m pytest tests/test_ios_release_assets.py -q`

Expected: the new Soccer Radar and dual-domain assertions fail against the current native source.

- [x] **Step 2: Update native configuration and current store copy**

Set the display name and current marketing metadata to Soccer Radar; set the production API/site origin to `https://soccer-radar.com`; list both `applinks:` domains in XcodeGen and entitlements; allow both hosts in `DeepLink.parse`; and change the Settings website label. Preserve the registered bundle ID, app icon geometry, app version/build, and existing store/legal disclosures.

- [ ] **Step 3: Verify source and macOS build contracts**

Run: `python -m pytest tests/test_ios_release_assets.py -q`

Run: the pushed candidate's GitHub Actions `iOS` workflow and require all simulator unit/UI jobs to pass.

Expected: local source checks pass; hosted macOS workflow proves generated project settings, Swift compilation, unit tests, and UI tests. No signed archive or store submission is created.

---

### Task 4: Monitoring, API examples, and current documentation

**Files:**
- Modify: `.github/workflows/synthetic-monitor.yml`
- Modify: `tests/synthetic-monitor.mjs`
- Test: `tests/synthetic-monitor.test.mjs`
- Modify: `openapi/soccer-scanner-v2.yaml`
- Modify: `README.md`, `CHANGELOG.md`, `docs/deployment.md`, `docs/railway-deployment.md`, `docs/railway-runbook.md`, `docs/release-checklist.md`, and `clients/ios/README.md`

**Interfaces:**
- Consumes: the canonical public origin and the monitor's existing `MONITOR_BASE_URL` override.
- Produces: new default monitoring/API/documentation URLs while preserving caller-supplied monitor targets and historical evidence.

- [x] **Step 1: Add a test for the canonical monitor default**

Add an assertion that the monitor's no-override target is `https://soccer-radar.com`; retain existing tests for explicit target overrides and provider-state behavior.

Run: `node --test tests/synthetic-monitor.test.mjs`

Expected: the new default-origin assertion fails against the current `soccerscanner.pro` fallback.

- [x] **Step 2: Update active integration references**

Update monitor defaults, OpenAPI server URL, current production setup/release instructions, README URLs, release checklist, and changelog. Keep the archived audit/evidence files and dated historical plans unchanged. Document Railway domain attachment before setting `PUBLIC_BASE_URL`, the route-preserving legacy content redirect, and the direct AASA exception.

- [x] **Step 3: Verify monitor and docs contracts**

Run: `node --test tests/synthetic-monitor.test.mjs`

Run: `python -m pytest tests/test_public_routes.py tests/test_ios_release_assets.py -q`

Expected: default monitor and API documentation use Soccer Radar; explicit target overrides, AASA gating, and historical records remain intact.

---

### Task 5: Provider-backed “Where to watch” on every fixture

**Files:**
- Modify: `soccer_scanner/providers/espn.py`
- Modify: `soccer_scanner/services/streaming.py`, `soccer_scanner/services/fixture_service.py`, `soccer_scanner/data/streaming-services.json`
- Modify: `static/js/fixture-renderer.js`, `static/js/match-context.js`, and matching styles
- Modify: `clients/ios/SoccerScanner/Models/Fixture.swift`, `clients/ios/SoccerScanner/Features/FixtureDetail/FixtureDetailView.swift`
- Modify: `docs/api.md`, `tests/test_espn_provider.py`, streaming service tests, web browser tests, and iOS source-contract tests

**Interfaces:**
- Consumes: ESPN’s reported broadcast name, type, and region; the existing verified service registry; existing raw `broadcasts` and `streaming` response fields.
- Produces: additive `whereToWatch` entries for `TV` and `STREAMING`, retaining each source-provided type and region plus a verified official URL and local logo path where available. Unknown providers remain unlinked. `streaming` continues to contain only streaming options.

- [ ] **Step 1: Add failing provider, API, and presentation checks**

Cover ESPN `TV` entries and duplicate handling; verified `ESPN`, `Paramount+`, and `USA Network` official destinations; unknown provider link suppression; additive API output while preserving the existing streaming field; web card/detail rendering for all options and a per-fixture no-listing state; and iOS details with safe provider links and a no-listing state.

Run: `python -m pytest tests/test_espn_provider.py tests/test_streaming_registry.py tests/test_fixture_service_v2.py -q`

Run: `npx playwright test tests/browser/streaming.spec.js --project=chromium --project=webkit`

Expected: new tests fail because ESPN TV entries are filtered out and clients only consume streaming entries.

- [ ] **Step 2: Preserve TV and streaming options and enrich only verified services**

Normalize named ESPN `TV` entries alongside `STREAMING`; make the registry describe both types without guessing names, regions, links, or logos. Build the additive `whereToWatch` list from provider broadcasts while preserving legacy `broadcasts` and streaming-only behavior. Register only independently verified official provider URLs; use logos already present in the repository and show the provider name when no local logo exists. Keep web external links HTTPS-only and `noopener noreferrer`; decode the additive field optionally on iOS and fall back to raw broadcasts for older payloads.

- [ ] **Step 3: Render every fixture honestly on web and iOS**

Show each reported option, type, and supplied region on fixture cards and the web detail panel. Show the appropriate provider name as a link when the official URL is verified. If the provider reports no broadcasts, show “Broadcast listing not provided” in the fixture watch area. Add equivalent iOS fixture detail rendering with native `Link`; do not create a logo asset without a trusted source asset.

- [ ] **Step 4: Document and verify the additive contract**

Update the API example and focused tests; run the task checks above and iOS source checks. Then run the documented local release matrix. iOS compilation remains pending the candidate’s macOS workflow.

---

### Task 6: Candidate release, domain cutover, and production proof

**Files:**
- Review: all changes from Tasks 1–4 plus fixture fix commit `1fa66f5`
- Update: `todo.md` only after its exact task checks pass

**Interfaces:**
- Consumes: passing local task checks, GitHub CI, hosted iOS workflow, Railway service `web`, and the verified DNS target for `soccer-radar.com`.
- Produces: one merged commit series containing the fixture fix and rebrand, with exact-SHA production verification on the new canonical host.

- [ ] **Step 1: Run focused and full repository checks**

Run the Task 1–5 focused checks, then the exact local release matrix in `docs/testing.md` from a clean worktree. Push the complete candidate branch and require both GitHub `CI` and `iOS` workflows for the exact head SHA to pass. Keep ledger tasks unchecked until their associated commands exit 0.

- [ ] **Step 2: Add and verify the production domain before canonical cutover**

Use the already linked project `933a7441-1b02-440a-b5a4-7e639a8584db`, environment `ec80c102-87e2-4edf-88c1-c563e827dc8b` (`production`), service `750aa23f-65eb-4c5c-a936-8b365480fc90` (`web`). Add `soccer-radar.com` on port `8080` with `railway domain soccer-radar.com --service web --environment production --port 8080 --json`; verify with `railway domain status soccer-radar.com --service web --environment production --json`. Confirm Railway's exact DNS record and active TLS before changing application configuration. Keep the existing old domain attached.

- [ ] **Step 3: Set the canonical origin and merge the candidate**

Set `PUBLIC_BASE_URL=https://soccer-radar.com` for production with `railway variable set PUBLIC_BASE_URL=https://soccer-radar.com --service web --environment production --skip-deploys --json`, then merge the reviewed candidate into `main` and push `main` so Railway deploys the source revision. Use the fast-forward path only if `main` remains an ancestor of the candidate; otherwise stop and review the divergence before merging.

- [ ] **Step 4: Verify the exact deployment and both domains**

Poll the deployment created for the merged SHA until its status is `SUCCESS`. Run the documented production smoke with `BASE_URL=https://soccer-radar.com`, `EXPECTED_SHA` equal to the full merged SHA, and `EXPECTED_ENVIRONMENT=production`. Verify the legacy-host redirect preserves a representative fixture route, date, timezone, and query; verify both AASA routes return directly and canonical page metadata uses the new host; compare `/health/version` and `/health/ready` to the exact merged SHA.

- [ ] **Step 5: Record release evidence and close only verified tasks**

Capture task command, stdout/stderr, final result, exit status, and log path in `todo.md`. Leave any task whose local command, hosted workflow, domain verification, or deployment proof did not pass unchecked. Confirm the merged worktree is clean and `main` equals `origin/main`.

---
