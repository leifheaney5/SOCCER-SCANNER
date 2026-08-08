# Native Fixture P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the native SwiftUI fixture workflow with truthful API decoding, date/timezone/status/search controls, race-safe loading, route-driven fixture links, and a reachable Settings/About surface.

**Architecture:** Extend the existing typed `FixtureFetching` seam and keep `FixtureListViewModel` as the single owner of day, timezone, provider state, spoiler preference, and local filters. Add a small route model consumed by the app root and list navigation; resolve fixture links through the existing `GET /api/v2/fixtures/<id>` endpoint. Keep all score privacy and canonical status behavior in the existing model and renderer boundaries.

**Tech Stack:** Swift 5.9, SwiftUI/iOS 17, Observation, XCTest/XCUITest, XcodeGen; Windows verification uses repository Python/Node gates only, while macOS CI proves Swift compilation and UI tests.

## Current execution status — 2026-08-07

The repository-controlled implementation steps in this plan are complete in the
current working tree. Unchecked execution steps that require Xcode, a simulator,
a physical device, Apple portal configuration, or production access remain
intentionally open; the exact evidence and release blockers are recorded in
`docs/audits/2026-08-07-native-p0-validation.md` and
`docs/release-checklist.md`.

## Global Constraints

- Public fixture IDs are provider-qualified SHA-256 digests returned by the API; never derive one by hand.
- Scores start hidden on every launch and are never persisted or exposed through accessibility labels before reveal.
- The JSON/API contract is camelCase and the server’s keyed `providers` object is authoritative.
- Preserve the full `MatchStatus` taxonomy; All/Live/Upcoming/Finished are filter groups, not replacement statuses.
- Old date/timezone/refresh responses must not overwrite newer selections; cancellation is not a user-facing error.
- Client-facing errors remain generic and must not expose provider exception text.
- Do not add dependencies, accounts, push notifications, a WKWebView wrapper, fabricated Apple identifiers, or fabricated legal values.
- Any changed behavior requires focused tests; iOS compilation and UI tests are unverified locally and require the `iOS` macOS workflow.
- Do not commit, push, merge, deploy, or access production from this workspace without an explicit user request.

---

### Task 1: Repair the native fixture contract and add typed fixture lookup

**Files:**
- Modify: `clients/ios/SoccerScanner/Models/Fixture.swift`
- Modify: `clients/ios/SoccerScanner/Networking/APIClient.swift`
- Modify: `clients/ios/SoccerScanner/Support/PreviewSupport.swift`
- Modify: `clients/ios/SoccerScannerTests/FixtureDecodingTests.swift`
- Modify: `clients/ios/SoccerScannerTests/FixtureListViewModelTests.swift`

**Interfaces:**
- `FixtureFetching` gains `func fixture(id: String) async throws -> Fixture`.
- `FixtureDay.providers` remains `[ProviderReport]` for existing UI logic, but decodes the API object `{ "espn": { "status": "success" } }` into deterministic provider reports sorted by name.
- `APIClient.fixture(id:)` requests `/api/v2/fixtures/<id>` and decodes the response envelope `{ "fixture": { ... } }`.
- `PreviewFixtureClient.fixture(id:)` returns the matching deterministic fixture or throws `APIError.server(status: 404)`.

- [ ] **Step 1: Write the failing decoding and lookup tests**

Add a captured keyed-provider payload to `FixtureDecodingTests` and assert that
`FixtureDay.isPartial` is true when one provider object has a non-success
status. Add a test double lookup assertion in `FixtureListViewModelTests` using
the existing preview ID and assert that an unknown ID throws a 404-shaped
`APIError`.

- [ ] **Step 2: Run the focused tests to verify the contract mismatch**

Run on macOS when available:

```text
xcodebuild test -project clients/ios/SoccerScanner.xcodeproj -scheme SoccerScanner -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:SoccerScannerTests/FixtureDecodingTests
```

Expected before the fix: the captured keyed `providers` payload cannot decode
into the current array property.

- [ ] **Step 3: Implement the keyed decoder and typed endpoint**

Decode `providers` as a keyed object with a small nested provider-outcome
record, map each entry to `ProviderReport(name:status:)`, and sort by name.
Keep compatibility with the current test fixture only if it does not weaken
the authoritative production shape. Add the envelope decoder and URL path
construction using the existing environment base URL and request/error mapping.

- [ ] **Step 4: Update deterministic preview behavior and run focused tests**

Make preview day JSON use the keyed provider shape, implement the matching
lookup, and run the decoding and model test targets. Confirm that no test or
production path fabricates a fixture ID or score.

- [ ] **Step 5: Review the diff for API-contract churn**

Confirm only the native decoder, typed endpoint seam, deterministic preview,
and their tests changed. Do not alter Flask routes or provider output.

### Task 2: Add race-safe local query state to the fixture view model

**Files:**
- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListViewModel.swift`
- Modify: `clients/ios/SoccerScannerTests/FixtureListViewModelTests.swift`
- Modify: `clients/ios/SoccerScannerTests/FixtureDecodingTests.swift` only if a shared fixture helper must move there

**Interfaces:**
- Add `FixtureStatusFilter: String, CaseIterable, Sendable` with `all`, `live`, `upcoming`, and `finished`.
- Add `FixtureFilter: Equatable, Sendable` containing `status` and `searchText`.
- Expose `public private(set) var filter` and `public var filteredFixtures: [Fixture]`.
- Preserve `selectDay(_:)`, `shiftDay(by:)`, `load()`, `toggleScores()`, and `scoreText(for:)` signatures.
- Add `func openFixture(id: String) async -> Fixture?` for route consumption; it applies the resolved route timezone/day before returning a fixture.

- [ ] **Step 1: Write failing tests for filters and request ordering**

Cover the preview fixtures with these assertions: All returns all rows; Live
returns in-progress and half-time; Upcoming excludes active/terminal rows;
Finished returns terminal finished rows; search matches home, away,
competition, and area case-insensitively; a nonempty source day with zero
filtered rows is distinguishable from `.empty`; a delayed old response cannot
replace a newer date response; and changing timezone preserves the selected
calendar day while requesting the new zone.

Use an actor-backed delayed `FixtureFetching` test double whose responses are
released by test-controlled continuations. Do not call a real provider.

- [ ] **Step 2: Run the focused view-model tests and observe failures**

Run the native `FixtureListViewModelTests` target in macOS CI or Xcode. The new
filter properties and generation behavior should fail to compile or assert
until implemented.

- [ ] **Step 3: Implement filter projections and generation guards**

Keep raw provider data in `FixtureDayViewData`. Add a normalized search haystack
from team names, competition name, and area name. Define Live as
`status.isActive`; Finished as `.finished`; Upcoming as non-active,
non-terminal scheduled/delayed/unknown statuses. Keep postponed/cancelled/
abandoned visible in All without relabelling them.

For each load, increment a private generation and capture the requested day and
timezone. After every await, apply state only when generation, day, and zone
still match. Cancel the prior task when a new UI selection supersedes it, and
ignore `APIError.cancelled` in presentation state. Preserve usable loaded data
while a refresh is in flight.

- [ ] **Step 4: Implement route fixture lookup in the model**

Use `FixtureFetching.fixture(id:)`, resolve the route timezone with
`FixtureTime.resolve`, compute the fixture day from its UTC kickoff, and load
that day under the resolved zone before returning the fixture. If lookup is
404, return `nil` without replacing the current list with a generic error.

- [ ] **Step 5: Run focused native tests and review spoiler boundaries**

Verify filters never inspect or emit score values, `scoresRevealed` remains
false for a new model, and delayed responses leave the newest state intact.

### Task 3: Expose native date, timezone, status, search, and resilient rows

**Files:**
- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListView.swift`
- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListViewModel.swift` only for bindings that Task 2 defines
- Modify: `clients/ios/SoccerScanner/Support/TimeZoneFormatting.swift` if a date-only binding helper is required
- Modify: `clients/ios/SoccerScannerUITests/FixtureFlowUITests.swift`

**Interfaces:**
- The list exposes accessibility identifiers `previous-day`, `today-day`, `next-day`, `date-picker`, `timezone-menu`, `status-filter`, `fixture-search`, `fixtures-filtered-empty`, and `settings-link`.
- `FixtureRow` remains a flexible SwiftUI layout and keeps the existing score-hidden identifiers and accessible status descriptions.

- [ ] **Step 1: Add UI-test scenarios before controls**

Add UI tests that launch deterministic stub data and verify previous/today/next
controls, the native date picker, timezone menu, status selection, search, the
filtered no-results state, detail navigation, hidden-score behavior, retry,
and the existing XXXL reachability check.

- [ ] **Step 2: Run the UI target to establish missing affordances**

Run the iOS UI target in macOS CI. The new identifiers should be absent before
implementation; Windows must record this target as unavailable.

- [ ] **Step 3: Implement compact native controls**

Place a date-navigation control group above the list with chevrons, a Today
button, and a `DatePicker` sheet/popover backed by the selected timezone’s
calendar day. Add a `Menu` containing device-local time and common zones
(`UTC`, `America/New_York`, `America/Los_Angeles`, `Europe/London`,
`Europe/Berlin`, `Asia/Tokyo`, `Australia/Sydney`). Add a segmented status
picker and `.searchable(text:)`. Every action calls the model’s existing
selection/load seam rather than duplicating network code.

- [ ] **Step 4: Implement honest empty/filter states and resilient rows**

Render “No matches are scheduled for this day” only when the source day is
empty. Render a separate “No matches match your filters” state when source data
exists but the local projection is empty. Replace the fixed 92-point status
column with a flexible leading status/time stack and a flexible team/metadata
stack; allow long names to wrap and keep the score/spoiler element independent.

- [ ] **Step 5: Run UI tests and inspect Dynamic Type identifiers**

Run the focused iOS UI target and verify the list remains navigable at XXXL.
Record that VoiceOver, Bold Text, Increased Contrast, landscape, and physical
device safe-area behavior still require macOS/device validation where not
covered by the test target.

### Task 4: Consume Universal Links through route-driven navigation

**Files:**
- Create: `clients/ios/SoccerScanner/App/AppRoute.swift`
- Modify: `clients/ios/SoccerScanner/App/SoccerScannerApp.swift`
- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListView.swift`
- Modify: `clients/ios/SoccerScanner/Support/DeepLink.swift` only for route conversion tests
- Modify: `clients/ios/SoccerScannerTests/TimeZoneAndDeepLinkTests.swift`
- Modify: `clients/ios/SoccerScannerUITests/FixtureFlowUITests.swift`

**Interfaces:**
- `AppRoute: Hashable, Sendable` includes `.fixture(id: String, timeZoneIdentifier: String?)` and safe `.unsupported(DeepLink)` handling for parsed non-fixture routes.
- `AppRouter: Observable` exposes `route: AppRoute?`, `handle(_ url: URL)`, and `consume(_ route: AppRoute)`.
- `AppContainer` no longer leaves a parsed-but-unused `pendingLink`; URL delivery forwards to the router.

- [ ] **Step 1: Write route-consumption tests**

Test URL conversion for valid fixture links, date/timezone propagation,
malformed links, unknown routes, and team/competition/calendar links that must
not navigate to a fabricated native screen. Add a UI-test launch path for a
fixture link and a missing-fixture fallback.

- [ ] **Step 2: Run route tests before implementation**

Run the focused deep-link XCTest target and the UI target on macOS CI. Windows
can only validate the source-level route parser indirectly; it cannot run
Swift tests or simulator navigation.

- [ ] **Step 3: Implement the router and list destination**

Have the app root feed both `.onOpenURL` and
`.onContinueUserActivity(NSUserActivityTypeBrowsingWeb)` into one router.
Observe route changes in the list, call `openFixture(id:)`, and push
`FixtureDetailView` only for a successful lookup. Present a clear unavailable
destination state for `nil` results and consume the route exactly once.

- [ ] **Step 4: Verify cold/warm semantics and spoiler safety**

Ensure a cold-start route is retained until the first list model is ready, a
warm route pushes from the active list, malformed URLs do nothing, and route
resolution does not reveal scores. Review that AASA configuration remains
disabled until real Apple identifiers are supplied.

### Task 5: Add native Settings/About and release validation documentation

**Files:**
- Create: `clients/ios/SoccerScanner/Features/Settings/SettingsView.swift`
- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListView.swift`
- Modify: `clients/ios/SoccerScannerUITests/FixtureFlowUITests.swift`
- Create: `docs/audits/2026-08-07-native-p0-validation.md`
- Modify: `clients/ios/README.md`
- Modify: `CHANGELOG.md` with a concise `Unreleased` entry for the native and
  mobile hardening slice

**Interfaces:**
- Settings exposes links to the existing `/privacy`, `/terms`, `/data-sources`, and website/support destinations without embedding legal claims or invented entity data.
- The screen displays app version/build from `Bundle`, selected timezone, score-spoiler explanation, data-source explanation, and environment only when non-production.
- The validation document records audited SHA `00557a8`, implementation changes, exact local commands/results, macOS CI requirement, production verification boundary, Apple-only actions, and remaining P0/P1/P2 work.

- [ ] **Step 1: Add UI coverage for Settings and legal links**

Assert the Settings route is reachable from the fixture list, the privacy and
terms links are present, the score explanation is visible without any score
value, and a non-production environment label is not rendered in production
configuration.

- [ ] **Step 2: Implement Settings/About**

Use `Form` sections and `Link` controls with system URL handling. Keep URLs
under the existing production base URL and show a concise release-blocker note
for Terms placeholders only in documentation, not as fabricated legal text in
the app.

- [ ] **Step 3: Update native README and validation evidence**

Document the navigation model, deep-link consumption, local filtering,
spoiler behavior, test strategy, and the exact distinction between green
historical/current macOS CI, Apple portal prerequisites, AASA activation, and
production smoke verification. Do not claim current HEAD is deployed or
compiled unless a fresh authoritative run proves it.

- [ ] **Step 4: Run the applicable verification matrix and review the diff**

From the implementation worktree run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
python -m compileall -q app.py wsgi.py soccer_scanner
Get-ChildItem static,tests -Recurse -File -Include *.js,*.mjs | ForEach-Object { node --check $_.FullName }
npm run test:smoke-invariants
git diff --check
```

Run `npm audit --audit-level=high`, `pip-audit -r requirements.txt`, and the
Chromium/WebKit Playwright projects when dependencies/browsers are available.
The iOS workflow must run on macOS after these changes; record its URL/SHA and
result, and do not call the native app buildable before that evidence exists.

## Execution order and review gates

Tasks 1 and 2 are model/API foundations. Task 3 depends on their public
properties. Task 4 depends on typed fixture lookup and the model’s generation
guards. Task 5 depends on the navigation surface but can be reviewed
independently. For each task, dispatch one fresh implementer, inspect its
report, generate a task-scoped diff package, dispatch a spec/quality reviewer,
and route any important finding through the fix loop before moving on. Do not
dispatch parallel implementers against overlapping Swift files.

## Self-review checklist

- [x] Every native P0 item selected for this slice maps to a task and a test.
- [x] The keyed `providers` contract mismatch is explicitly covered before UI work.
- [x] Search/status filtering is local and does not invent a backend global-search contract.
- [x] Deep links are parsed, consumed, and routed; unsupported parsed routes remain safe no-ops.
- [x] No task claims Windows can compile or run iOS tests.
- [x] No task fabricates Apple IDs, legal values, scores, fixture IDs, or provider data.
