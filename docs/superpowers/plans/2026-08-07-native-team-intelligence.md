# Native Team Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make verified team intelligence reachable from native fixture detail without creating a primary Team tab or weakening score privacy.

**Architecture:** Extend the existing `FixtureFetching` dependency with the already-supported canonical team-analysis request. Decode only the identity and aggregate season statistics needed by a small SwiftUI sheet; do not decode or display match-level scores. Pass the injected client from `FixtureListView` to `FixtureDetailView`, and load one team at a time on demand with explicit loading, unavailable, retry, and missing-identity states.

**Tech Stack:** Swift 5.9, SwiftUI, async/await, URLSession, XCTest/XCUITest, XcodeGen source discovery.

## Global Constraints

- Use the existing `/api/v2/teams/{canonicalId}/analysis` contract; do not add a backend endpoint.
- Preserve score privacy: team intelligence must not reveal match-level scores before the user reveals scores.
- Only offer team intelligence when the fixture has a provider-verified canonical team ID.
- Keep provider errors generic in the native UI and preserve retryability.
- Do not add dependencies, accounts, analytics, or production configuration.
- Windows cannot prove Xcode compilation; macOS CI remains the authoritative native build gate.
- Do not commit, push, deploy, or access production during this work.

---

### Task 1: Typed team-analysis contract and client request

**Files:**
- Create: `clients/ios/SoccerScanner/Models/TeamAnalysis.swift`
- Modify: `clients/ios/SoccerScanner/Networking/APIClient.swift`
- Test: `clients/ios/SoccerScannerTests/FixtureDecodingTests.swift`

**Interfaces:**
- `FixtureFetching.teamAnalysis(canonicalId: String) async throws -> TeamAnalysis`
- `TeamAnalysis` exposes optional `teamInfo` and optional aggregate `stats`; unknown response fields are ignored.

- [ ] **Step 1: Write decoding and request tests**

Test a representative response containing `team_info`, `stats`, and match arrays. Assert canonical ID/provider ID, team name, and aggregate values decode, while no match score is exposed through the typed model. Assert the request path is `/api/v2/teams/arsenal/analysis`.

- [ ] **Step 2: Run the focused native tests on an available macOS runner**

Expected on Windows: Xcode tooling unavailable; retain the tests for CI rather than claiming native verification locally.

- [ ] **Step 3: Implement the typed model and `APIClient.teamAnalysis`**

Use explicit `CodingKeys` for the server's snake_case fields and reuse the existing generic `get` error mapping.

- [ ] **Step 4: Update `PreviewFixtureClient` to conform**

Return deterministic team data for canonical IDs and throw the configured typed error for failure behavior.

- [ ] **Step 5: Re-run static Swift/source checks**

Confirm every `FixtureFetching` conformer implements the new method and no source constructs a second client.

### Task 2: Fixture-detail team intelligence surface

**Files:**
- Create: `clients/ios/SoccerScanner/Features/FixtureDetail/TeamIntelligenceView.swift`
- Modify: `clients/ios/SoccerScanner/Features/FixtureDetail/FixtureDetailView.swift`
- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListView.swift`
- Modify: `clients/ios/SoccerScanner/App/SoccerScannerApp.swift`

**Interfaces:**
- `TeamIntelligenceView(team:client:)` is a native sheet destination.
- `FixtureDetailView` receives the injected `FixtureFetching` client and presents one destination per team.

- [ ] **Step 1: Add detail affordances**

Add clearly labelled buttons for home and away teams only when `canonicalId` is non-empty. Include stable accessibility identifiers and explain that the data is provider-verified.

- [ ] **Step 2: Implement on-demand sheet states**

Use a task tied to the canonical ID. Show a progress state, verified identity/aggregate statistics, a generic unavailable state, and a retry button. If the ID is absent, show no interactive affordance and keep the existing fixture details unchanged.

- [ ] **Step 3: Preserve spoiler safety**

Do not render `recent_matches`, `upcoming_matches`, or score-bearing fields. The team sheet may show only identity and aggregate values such as played, wins, draws, losses, goals for, goals against, and goal difference.

- [ ] **Step 4: Add UI-test hooks**

Ensure the preview fixture has canonical IDs and deterministic preview data so the detail buttons and sheet can be exercised in CI without network access.

### Task 3: Verification, documentation, and review

**Files:**
- Modify: `clients/ios/README.md`
- Modify: `docs/audits/2026-08-07-native-p0-validation.md`
- Modify: `docs/release-checklist.md`
- Test: `clients/ios/SoccerScannerUITests/FixtureFlowUITests.swift`

- [ ] **Step 1: Add focused UI coverage**

Open team intelligence from fixture detail, assert the team name and aggregate labels, and assert no score-bearing element appears while scores remain hidden.

- [ ] **Step 2: Run repository-side checks**

Run the Python, Node, browser, syntax, asset, and diff checks already recorded in the audit. Run the native suite only on macOS CI.

- [ ] **Step 3: Review the diff and update the status matrix**

Mark the native team-intelligence surface as implemented/covered in code, leave macOS build and production/App Store verification separate, and retain calendar/global search as deferred scope.

- [ ] **Step 4: Record the Windows limitation honestly**

Do not state that Swift compilation or XCUITest passed locally; name the exact macOS workflow gate still required.
