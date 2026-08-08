# Native P0 validation — 2026-08-07

## Scope and audited baseline

This record covers the uncommitted native fixture P0 slice and the related mobile-web
filter/safe-area P1 slice. The native slice now includes local advanced filtering,
provider/freshness detail context, refresh-failure retention, and explicit missing
metadata states. The audited baseline is
`00557a8aee66c48663560f9b1380c6e2bd4b78ed` (`00557a8`), whose subject is
`docs: refresh the verified-state block to the current revision`. This document does
not claim that the current working tree is committed, compiled, or deployed.
**Production commit:** verified as the audited baseline; the uncommitted working-tree
slice is not present in production.

## Feature-status matrix

| Area | Implemented in code | Exposed in UI | Automated evidence | Production/App Store status |
| --- | --- | --- | --- | --- |
| Native fixture list | Date navigation, timezone, status/search/advanced filters, cancellation guards, spoiler-safe rows | Yes, native SwiftUI list and filter sheet | Swift source tests and UI-test scenarios; current macOS execution still required | Not production-verified; not build-certified on Windows |
| Native fixture detail | Status, teams, hidden/revealed score, kickoff/timezone, competition/country/venue, broadcasts, freshness/missing-data states, and canonical-ID-gated score-safe team intelligence | Yes, native detail route and on-demand team sheet | Swift decoding/client tests and UI-test assertions for detail/team-intelligence spoiler boundary | Not production-verified; macOS build and physical-device review required |
| Native routing | Cold/warm URL, `onOpenURL`, browsing activity, date/timezone state, unsupported/missing-fixture fallback | Yes, route-driven navigation | Deep-link and router tests | AASA activation and device behavior remain external gates |
| Native disconnected state | Typed unavailable/retry state; no persisted fixture snapshots or unverified offline scores | Yes, honest unavailable surface | Failure UI scenario and model error tests | Native offline storage remains a separate P1 decision |
| Mobile web controls | Compact primary toolbar, bottom-sheet filters, focus trap/return, safe-area offset, narrow-width layout | Yes, responsive dashboard | 184 Chromium/WebKit tests, axe and 200%/400% reflow coverage | Audited HEAD smoke-verified in production; uncommitted changes are not deployed |
| Provider/reliability safeguards | Shared request budget, stale ESPN metadata fallback, typed partial/error states, shared health registry | Surfaced through web/native status and notices | Full Python/Node suites and smoke invariants | Audited HEAD production-ready; ESPN healthy, Football-Data explicitly disabled |
| Settings/legal surfaces | Version/build, timezone, spoiler/data-source explanation, privacy/terms links, honest support placeholder | Yes, native Settings/About | Native source/UI coverage and release-asset checks | Legal/support review and Apple metadata remain blocked |
| iOS release assets and CI | Info.plist, privacy manifest, entitlements, icons, Fastlane metadata/beta notes, raw build logs | Release tooling only | Standalone release validator and YAML/source checks | Fresh macOS workflow for this uncommitted slice still required |

## Implementation inventory

- The decoder accepts the API's keyed provider-outcome object; the typed client can
  look up a fixture by its server-provided public ID.
- Fixture detail now binds to the list model's spoiler state and provides its own
  reveal/hide action; dismissing detail preserves the same session-scoped choice.
- The list owns explicit day/timezone selection, local status/search filtering, and
  cancellation/generation protection for superseded loads. Advanced filtering
  covers competition, country/area, time window, deterministic sort, and hide-
  finished with draft Apply/Close/Reset semantics.
- Native detail now carries day-level provider reports and freshness age, labels
  unavailable competition/country/venue and streaming metadata explicitly, and
  distinguishes a score that is hidden from a score that is unavailable. It
  preserves every provider-reported broadcast entry, labels its type and region,
  and states that availability may vary. When a
  canonical team ID is present, detail also opens a typed, on-demand team
  intelligence sheet that models only provider-verified identity and aggregate
  statistics; score-bearing match arrays are intentionally excluded.
- Deterministic native UI coverage now exercises distinct partial, stale, empty,
  retryable, and provider-reported broadcast states in addition to loaded data.
- Refresh failures retain usable native fixture rows and expose a generic typed
  error notice for retry, rather than replacing a loaded list with an empty error
  surface.
- Valid fixture Universal Links are consumed into native detail navigation; malformed
  and unsupported routes are non-navigating, missing fixtures retain a usable list,
  and valid `date=YYYY-MM-DD` route state is validated and applied to the native
  calendar day.
- Native UI scenarios now cover both cold-start and warm-state fixture links, plus
  Bold Text, Increased Contrast, Differentiate Without Color, Button Shapes, Reduce
  Motion, and largest Dynamic Type launch settings. These remain macOS execution
  evidence rather than Windows proof.
- The AASA route advertises fixture detail links while explicitly excluding the
  score-free `/fixtures/*.ics` calendar downloads; team, competition, and calendar
  paths remain web-only instead of being intercepted by an unsupported native route.
- The native list refreshes when the app returns to the foreground, while retaining
  the existing pull-to-refresh and generation guards. Native fixture rows remain
  spoiler-safe and expose score-hidden/unavailable states separately.
- At accessibility Dynamic Type sizes, native fixture rows switch to a vertical
  wrapping layout and the status picker becomes a menu; normal-size rows retain
  their existing geometry. Deterministic XXXL/long-content and landscape UI
  scenarios cover row content, date selection, detail metadata, and filter actions.
- Provider fan-out now shares one request-scoped monotonic budget across providers
  and their metadata lookups; a slow first provider cannot multiply the configured
  deadline before the next provider starts.
- ESPN league metadata uses the shared cache's stale window when a refresh request
  fails, preserving otherwise usable fixtures while marking the provider outcome
  partial with an explicit stale-metadata failure category.
- The fixture toolbar now reaches a Form-based Settings/About screen with version,
  build, selected timezone, spoiler/data-source explanations, a non-linking Support
  section that states support contact is not configured for this build, and
  production-origin website/privacy/terms/data-source links. The non-production
  environment is not shown for production configuration.
- Deterministic UI coverage now asserts the Settings route, privacy/terms links,
  score explanation without score presentation, and production environment-label
  suppression.
- The linked privacy page now distinguishes browser session storage from native
  iOS behavior: native score visibility is in-memory per launch, request IDs are
  operational trace values rather than account identifiers, and no analytics,
  crash-reporting, or advertising SDKs are present. A source check also ensures
  the app root imports `Observation` before using `@Observable`.
- The mobile web fixture toolbar now moves secondary filters into an accessible native
  bottom-sheet dialog at mobile widths, with draft Apply/Close/Escape behavior and focus
  restoration; desktop keeps the existing inline controls.
- The installed-PWA shell now opts into `viewport-fit=cover` and applies safe-area
  insets to the header, content, footer, toolbar, and mobile filter/dialog surfaces;
  the mobile sticky toolbar offset includes the top inset so it stays below the
  enlarged standalone header.
- On mobile web, search and All/Live/Upcoming/Finished remain visible primary
  controls outside the advanced sheet; the sheet retains competition, country,
  time, sort, hide-finished, timezone, and clear controls. The PWA update notice
  also respects the bottom safe-area inset.
- Mobile web sort choices now contribute to the active-filter announcement/count;
  refreshed competition/country options also reconcile an open draft so stale
  selections cannot be reapplied. The compact toolbar is covered at 320x568,
  375x667, 390x844, and 430x932 in both browser engines.
- The mobile filter dialog now has an explicit Tab/Shift+Tab loop in addition to
  native modal semantics, with Chromium and WebKit focus-restoration coverage.
- Mobile match-sheet backdrop closing now lets the post-render close callback
  restore focus to the newly rendered fixture trigger, avoiding WebKit's native
  modal-focus race.
- The compact mobile date controls and Filters button occupy separate rows at
  320, 375, 390, and 430 pixels; geometry regressions run in both browser engines.
- Automated mobile-web reflow coverage now checks effective 200% and 400% zoom
  widths without horizontal document or fixture-card overflow in Chromium and WebKit.
- The iOS workflow now validates generated bundle/deployment/icon settings and
  source release assets, captures raw `xcodebuild` output alongside the
  `.xcresult`, and no longer assumes `xcpretty` is installed. The Fastlane
  project-generation lane now resolves `project.yml` from its actual CI working
  directory. Its path filters also include the shared release validator and
  Terms preflight input. These workflow changes still require a current macOS run.
- Simulator selection is now delegated to the dependency-free
  `clients/ios/Tools/select_simulator.py` helper, which parses numeric iOS
  runtime components and prefers the shortest available iPhone name on the
  newest runtime; its selection and no-device failure paths are unit-tested.
- The manual Fastlane beta lane now reads the canonical TestFlight beta-notes
  file and passes its contents as the upload changelog; source validation guards
  that wiring. Ruby/Fastlane execution remains unavailable on this Windows host.
- The Fastlane App Store submission lanes now run a repository-controlled
  preflight before building: legal Terms placeholders and a missing or invalid
  HTTPS support URL stop the lane, and the shared release-asset validator runs
  before a submission build. Signed archive lanes now validate the Apple Team ID,
  registered bundle ID, numeric build number, and App Store Connect key inputs
  before starting a build, then use automatic signing with provisioning updates
  enabled. The support URL remains intentionally absent until a verified owner
  and destination are supplied.
- A public `fastlane preflight` lane validates legal/support and repository
  release gates without requiring an archive or App Store Connect credentials.
  Final screenshots are explicitly portal-managed; Fastlane does not treat
  browser or simulator captures as App Store artwork.
- The source release validator now requires every repository-controlled App Store
  metadata template (identity, listing text, URLs, release notes, and beta notes)
  to exist and be non-empty; support remains an explicit human-owned gate.

The Settings form deliberately has no native support-contact link: the repository
contains no verified support destination or support owner. Its visible non-linking Support
section is a release blocker until an owner and destination are established. The Terms link
targets the existing website route; that route is an engineering draft with legal-owner
placeholders and must receive legal review before reliance.

## Local verification on 2026-08-07

| Command | Result |
| --- | --- |
| `Get-Command xcodebuild, swift, swiftc, ruby, bundle, pip-audit` | None of these tools are available on this Windows host; no native XCTest/XCUITest, Ruby/Fastlane, or pip-audit command was run. |
| `python tests/test_ios_release_assets.py` | Passed: 13 source checks covering plist, privacy, entitlement, icon, metadata, beta-changelog wiring, Fastlane, submission preflight, automatic-signing contract, generated-artifact hygiene, Observation import, detail spoiler binding, native state-fixture and broadcast wiring, simulator-selector wiring, and workflow checks. |
| `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q` | Passed: 253 tests and 72 subtests in 5.67 seconds. |
| `python -m compileall -q app.py wsgi.py soccer_scanner` | Passed (exit 0). |
| `Get-ChildItem static,tests -Recurse -File -Include *.js,*.mjs \| ForEach-Object { node --check $_.FullName }` | Passed (exit 0). |
| `npm run test:smoke-invariants` | Passed: 4 tests, 0 failures. |
| `npm run test:node` | Passed: 41 tests, 0 failures. |
| `npm audit --audit-level=high` | Passed: 0 vulnerabilities. |
| `pip-audit -r requirements.txt` | Unavailable: `pip-audit` is not installed on this Windows host. |
| `npx playwright --version` | Available: Playwright 1.62.1. |
| `npx playwright test tests/browser/fixtures-dashboard.spec.js -g "narrow mobile keeps|dashboard has no horizontal overflow at (320|375|390|430)x" --project=chromium --project=webkit` | Passed: 10 focused tests across Chromium and WebKit (11.8 seconds). |
| `npx playwright test tests/browser/accessibility.spec.js -g "reflows without horizontal scrolling" --project=chromium --project=webkit` | Passed: 4 focused 200%/400% reflow tests across Chromium and WebKit in 7.2 seconds. |
| `npx playwright test --project=chromium --reporter=dot` | Passed: 92 Chromium tests in 1.3 minutes. |
| `npx playwright test --project=webkit --reporter=dot` | Passed: 92 WebKit tests in 2.0 minutes. |
| `npx playwright test --project=chromium --project=webkit --reporter=dot` | Passed: 184 tests across Chromium and WebKit in 3.1 minutes after the WebKit close-focus fix. |
| `git diff --check` | Passed (exit 0). |

## Production verification on 2026-08-07

The public production endpoints were checked read-only against the audited baseline.
`/health/version` and `/health/ready` reported the exact HEAD
`00557a8aee66c48663560f9b1380c6e2bd4b78ed`, environment `production`, asset version
`00557a8aee66`, durable PostgreSQL/schema `20260804_01`, shared Redis, and ready
status. ESPN reported `ok`; Football-Data reported `disabled`, not a fabricated
success. The exact command below passed with 79 fixture records and 79 unique IDs:

```powershell
$env:BASE_URL='https://soccerscanner.pro'
$env:EXPECTED_SHA=(git rev-parse HEAD)
$env:EXPECTED_ENVIRONMENT='production'
npm run smoke:production
```

The smoke result was `status: ok`, `fixtureStatus: 200`, and `fixtureState: success`.
The AASA endpoint intentionally returned `404` because Apple Team ID and bundle ID
are not configured; this is the guarded behavior, not evidence of Universal Link
activation.

## macOS CI evidence and requirement

The existing audit records a historical `iOS` GitHub Actions run on 2026-08-05 with
36 unit tests and 5 UI tests, all passing. That run predates this working-tree slice
and is historical evidence only. The required current evidence is a new successful
`iOS` workflow on `macos-latest` for the commit containing this work, with its run URL,
commit SHA, and result recorded here. No such current run exists in this record.

## Production boundary

The read-only production smoke above verifies the audited committed baseline only.
It does not verify the current uncommitted working tree, a Railway deployment event,
or native iOS behavior. No deployment, restart, migration, production data access,
or secret access was performed.

## Human-only Apple actions

- Establish Apple Developer Program and App Store Connect ownership.
- Create or confirm the App Store Connect app record, signing configuration, and
  release-time secrets outside this repository.
- Review legal Terms content and its owner-provided placeholders.
- Configure the Apple Team/bundle values required for the server's AASA response,
  then verify Universal Links on a device or simulator against the deployed origin.
- Review store metadata, privacy answers, screenshots, TestFlight distribution, and
  any submission decision.

## Remaining work

### P0 release blockers

- A fresh macOS `iOS` workflow must compile and run the native tests for this slice.
- A verified support owner and destination are required before replacing the visible
  non-linking support status with a support link.
- Legal review must complete the Terms placeholders before the linked terms can be
  relied upon.
- Apple portal configuration and AASA activation require human action and deployment
  verification.
- A future release commit containing this working-tree slice still needs its own
  terminal deployment-success record and exact-SHA production smoke.

### P1 remaining work

- Physical-device accessibility validation for VoiceOver, Bold Text, Increased
  Contrast, landscape, Dynamic Type, and safe-area behaviour; the new scene-phase
  refresh and date-aware Universal Link behavior still require current macOS CI and
  device/simulator execution.
- Native fixture snapshots are not persisted yet. A disconnected native launch
  shows the typed unavailable state instead of presenting unverified cached data;
  implementing spoiler-safe native offline storage remains a separate P1 decision.
- Native calendar and global-search surfaces remain deferred because the server
  feature flags `calendar_range_api` and `search` are disabled and there is no
  versioned native endpoint contract to consume. The fixture list's local search
  covers the loaded day. Team intelligence is now reachable from fixture detail;
  a dedicated native team route remains deferred.
- Provider capability differences and secondary-provider production configuration
  still need an authorized production verification pass.

### P2 / later scope

- Operations dashboard, OpenAPI contract, SLOs, analytics, release governance, and
  the notifications decision/infrastructure.
- Accounts, persistent preferences, and notifications remain out of scope until their
  privacy, consent, identity, and data-lifecycle prerequisites are selected.
