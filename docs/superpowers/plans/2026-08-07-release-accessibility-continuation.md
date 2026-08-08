# Release and native accessibility continuation plan

This continuation closes the remaining repository-controlled gaps found after
the native fixture P0 slice. Apple portal, legal, support-owner, production,
and macOS/Xcode actions remain external and are not assumed complete here.

## Global Constraints

- Do not read secrets, access production, deploy, commit, push, or run Apple release lanes.
- Do not add dependencies; preserve the pinned Python/npm dependency policy.
- Scores remain hidden by default and must never enter accessibility output before reveal.
- Preserve the full MatchStatus taxonomy and the camelCase API contract.
- Changes must be source-controlled, tested, and documented without inventing Apple or legal values.

## Task 1: Wire TestFlight beta notes into the release lane

**Files:**

- Modify: `clients/ios/fastlane/Fastfile`
- Modify: `tests/test_ios_release_assets.py`
- Modify: `clients/ios/README.md` if the lane behavior needs documentation

The existing `clients/ios/fastlane/metadata/en-US/beta_notes.txt` is the
canonical TestFlight changelog. The `beta` lane must read that repository file
using a path stable when Fastlane is invoked from `clients/ios`, then pass its
contents to `upload_to_testflight` as the changelog. Add source-level
validation that fails if the lane stops wiring the canonical file. Do not add
secrets, signing behavior, or a new dependency.

## Task 2: Make native fixture rows adaptive at accessibility sizes

**Files:**

- Modify: `clients/ios/SoccerScanner/Features/Fixtures/FixtureListView.swift`
- Modify: `clients/ios/SoccerScanner/Support/PreviewSupport.swift`
- Modify: `clients/ios/SoccerScannerUITests/FixtureFlowUITests.swift`
- Modify: `clients/ios/SoccerScanner/Features/FixtureDetail/FixtureDetailView.swift` only if needed

At accessibility Dynamic Type sizes, long team and competition names must not
be forced through the normal three-column row geometry. Use SwiftUI environment
values to provide an adaptive, readable layout while preserving row IDs,
spoiler-safe score labels, and status text. Extend deterministic UI-test data
and UI coverage for long content, date/status controls, detail content, filter
actions, and landscape. Windows cannot compile this target; document that
macOS CI remains the verifier.

## Verification and review

Run focused source tests after each task, then the repository matrix. Review
each task's actual diff and preserve the existing uncommitted worktree.
