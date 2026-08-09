# ESPN Team Crests and Temporary Team Intelligence Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Preserve every official ESPN team crest supplied by supported payload shapes and temporarily remove Team Intelligence from all user-facing web, native, and API surfaces.

**Architecture:** Keep crest ownership in the ESPN provider normalization boundary: choose the first valid provider URL from `team.logo` or the provider's `team.logos` collection, then use ESPN's official default team-logo asset when that provider has no crest. Pass the selected URL unchanged through the canonical fixture contract. Disable Team Intelligence through the existing server feature-flag registry, guard its page/API routes, and remove the web/native launch controls while leaving dormant implementation code available for a later re-enable.

**Tech Stack:** Python 3, Flask, pytest, vanilla ES modules, Playwright Chromium/WebKit, SwiftUI XCTest/UI tests.

## Global Constraints

- Preserve provider-sourced values; do not invent, download, or hand-map crest URLs. ESPN's official default team-logo asset is the only provider fallback.
- Keep the existing friendly competition category icon behavior and uncommitted work intact.
- Do not add dependencies or modify CI/infrastructure configuration.
- Team Intelligence must be unavailable to users while its feature flag default is false.
- Any change under `clients/ios/` is locally unverified on Windows and must be labeled that way.
- Run focused tests, the canonical release matrix, and `git diff --check` before reporting completion.

### Task 1: Normalize all supported ESPN team-logo payloads

**Files:**
- Modify: `soccer_scanner/providers/espn.py`
- Test: `tests/test_espn_provider.py`

**Interfaces:**
- `normalize_event()` continues returning `homeTeam.crest` and `awayTeam.crest` as provider URLs or `None`.
- Add a small private helper that reads `logo` first, then the first valid URL from `logos[].href` or `logos[].url`.

- [ ] Write a failing unit test proving a team with no singular `logo` but a valid `logos` collection retains its official URL.
- [ ] Run the focused test and confirm it fails because the current adapter returns `None`.
- [ ] Write a failing unit test proving a team with no provider crest receives ESPN's official default team-logo asset.
- [ ] Implement the minimal helper and use it in `_team()` with the official ESPN default only when no crest is supplied.
- [ ] Run the focused provider tests and confirm both singular and collection payloads pass.

### Task 2: Disable Team Intelligence user-facing surfaces

**Files:**
- Modify: `soccer_scanner/services/feature_flags.py`
- Modify: `soccer_scanner/routes/pages.py`
- Modify: `soccer_scanner/routes/api.py`
- Modify: `static/js/fixtures.js`
- Modify: `static/js/match-context.js`
- Modify: `templates/matches_today.html`
- Modify: `clients/ios/SoccerScanner/Features/FixtureDetail/FixtureDetailView.swift`
- Test: `tests/test_app.py`
- Test: `tests/test_public_routes.py`
- Test: `tests/browser/fixtures-dashboard.spec.js`
- Test: `tests/browser/accessibility.spec.js`
- Test: `tests/browser/visual-states.spec.js`
- Test: `clients/ios/SoccerScannerUITests/FixtureFlowUITests.swift`

**Interfaces:**
- `FeatureFlagRegistry.as_dict()` reports `team_intelligence: false` by default.
- Team page and analysis endpoints return the existing generic 404 envelope while disabled.
- Fixture context renders team crests/names but no intelligence buttons or drawer.
- Native fixture detail renders match data without a Team Intelligence section or sheet.

- [ ] Update tests first to assert disabled routes, absent dashboard controls/drawer, and native detail without intelligence entry points.
- [ ] Run the focused tests and confirm they fail against the current enabled implementation.
- [ ] Set the flag default false, guard the routes, remove the dashboard drawer/context controls, and remove the native launch surface.
- [ ] Run focused Python/browser tests; run iOS tests only where the local environment supports them and record Windows/macOS verification limits.

### Task 3: Document the release behavior

**Files:**
- Modify: `README.md`
- Modify: `docs/api.md`
- Modify: `docs/data-sources.md`
- Modify: `CHANGELOG.md`

- [ ] Remove Team Intelligence from active product descriptions.
- [ ] Document that the analysis routes are temporarily unavailable rather than deleting their contract history.
- [ ] Record the ESPN crest normalization and temporary feature removal under `Unreleased`.

### Task 4: Verify the complete change

- [ ] Run `git diff --check` and review the full diff.
- [ ] Run Python, Node, browser Chromium/WebKit, iOS asset/simulator, dependency-audit, syntax, and compile checks from `docs/testing.md`.
- [ ] Report exact results, including any unavailable local gate, and leave changes uncommitted unless separately requested.
