# iOS Deployment Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository's iOS archive, TestFlight, metadata, and CI paths explicit and fail early on missing Apple-controlled inputs without fabricating them.

**Architecture:** Keep simulator verification signing-free. Use automatic App Store signing only in the manual Fastlane release path, with the registered team and bundle identifiers supplied at runtime and `-allowProvisioningUpdates`. Keep legal, support, screenshots, and portal values as explicit human gates.

**Tech Stack:** SwiftUI/XcodeGen, Fastlane, GitHub Actions, Python source validators, pytest.

## Global Constraints

- Do not commit Apple Team IDs, credentials, provisioning profiles, legal facts, or invented support destinations.
- Preserve the generated-project model; do not commit `SoccerScanner.xcodeproj`.
- Release lanes remain manual; simulator CI never requires signing secrets.
- Keep App Store metadata truthful and spoiler-safe.
- Run the repository verification matrix before reporting readiness.

---

### Task 1: Make generated iOS artifacts unambiguous

**Files:**
- Modify: `.gitignore`
- Test: `tests/test_ios_release_assets.py`

- [x] Add explicit ignores for generated Xcode projects, workspaces, and user state.
- [x] Add a source-level assertion that the generated project remains ignored.
- [x] Run the focused release-asset tests and confirm the new assertion failed before the ignore rule, then passed after it.

### Task 2: Harden the signed archive contract

**Files:**
- Modify: `clients/ios/fastlane/Fastfile`
- Test: `tests/test_ios_release_assets.py`

- [x] Add runtime validation for `APPLE_TEAM_ID`, `APPLE_BUNDLE_ID`, and a numeric `BUILD_NUMBER` before archive work.
- [x] Make the archive lane use automatic signing with `-allowProvisioningUpdates` and explicit runtime team/bundle settings.
- [x] Keep the simulator lane signing-disabled and preserve the legal/support preflight before submission lanes.
- [x] Add source checks for the signing contract and manual-lane safety.

### Task 3: Wire CI inputs and document the operator path

**Files:**
- Modify: `.github/workflows/ios.yml`
- Modify: `clients/ios/README.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/audits/2026-08-07-native-p0-validation.md`

- [x] Pass the required release-time signing inputs through the manual workflow only.
- [x] Document the difference between simulator CI, automatic archive signing, TestFlight upload, and public submission.
- [x] Document the exact first macOS command and evidence required after the user supplies Apple configuration.
- [x] Keep unresolved legal/support/screenshots/portal items visibly blocked.

### Task 4: Verify and review

**Files:**
- Review: all changed files and `git status --short`

- [x] Run focused release checks, Python tests, Node tests, browser tests, compile/syntax checks, audit checks, and `git diff --check`.
- [x] Confirm no generated project, secret, provisioning profile, or support URL entered the worktree.
- [x] Record exact results and remaining external gates in the validation document.
