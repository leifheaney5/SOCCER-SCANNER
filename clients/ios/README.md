# Soccer Scanner — iOS client

A native SwiftUI client for the Soccer Scanner v2 API. It is not a web-view wrapper.

## Current scope

The fixture list is the current native surface. It loads a selected calendar day in an explicit IANA timezone, provides previous/today/next and date-picker navigation, and filters loaded fixtures locally by status and search text. A row opens native fixture detail; scores begin hidden for each launch and can be revealed or hidden from either the list toolbar or the detail screen. Team Intelligence is disabled for this release and is not exposed from native fixture detail.

Fixture links are parsed by the app root from both `onOpenURL` and Universal Link user activities. Only a validated fixture route is consumed natively; unsupported or malformed routes leave the fixture list usable. The route lookup uses the typed fixture endpoint and reports a missing fixture without inventing a destination.

Settings is available from the fixture-list toolbar. It shows the app version/build from `Bundle`, selected timezone, spoiler and data-source explanations, plus website, privacy, terms, and data-source links. The environment label appears only outside production. Its Support section truthfully states that support contact is not configured for this build; no native support link is present because this repository contains no verified support destination or owner.

## Layout

```
clients/ios/
  project.yml                    XcodeGen specification
  SoccerScanner/
    App/                         app root, composition, route state
    Config/                      development, staging, production environments
    Features/Fixtures/           fixture list and detail
    Features/Settings/           native settings/about form
    Models/                      fixture and API configuration contracts
    Networking/                  typed API client and error taxonomy
    Support/                     deep links, timezone formatting, preview data
  SoccerScannerTests/            XCTest coverage
  SoccerScannerUITests/          deterministic stub-data UI coverage
  Tools/select_simulator.py      numeric-newest simulator selection used by CI
```

## Verification boundaries

Windows cannot run Xcode, `xcodebuild`, iOS Simulator tests, or compile this target. The `.github/workflows/ios.yml` `iOS` workflow generates the Xcode project, validates the source and generated release settings, selects an available simulator, then runs the full unit/UI test scheme with signing disabled. It uploads both the `.xcresult` bundle and raw `xcodebuild` output when the run finishes.

Historical evidence recorded on 2026-08-05 shows an earlier `iOS` workflow run passed 36 unit tests and 5 UI tests. It does not verify the current release candidate. A fresh macOS workflow run for the candidate commit is required before calling this client compiled or its UI tests passing.

The native client points production configuration at `https://soccerscanner.pro`.
The audited committed HEAD was read-only smoke-verified there on 2026-08-07, but
that does not prove the current uncommitted native changes are deployed or that
Universal Links are activated; a future release SHA needs its own production and
device verification.

## Local development (macOS only)

```bash
brew install xcodegen
cd clients/ios
xcodegen generate --spec project.yml
xcodebuild test -project SoccerScanner.xcodeproj -scheme SoccerScanner -destination 'platform=iOS Simulator,name=iPhone 16' CODE_SIGNING_ALLOWED=NO CODE_SIGN_IDENTITY=""
```

The development environment uses `http://localhost:5000`; production is the default when `SOCCER_SCANNER_ENVIRONMENT` is unset or unrecognised.

## Apple and release prerequisites

Apple Developer Program enrolment, App Store Connect app-record ownership, signing identities, API-key creation, store metadata, privacy answers, and submission remain human-controlled actions. The release lanes read their App Store Connect and signing values from environment variables at release time; this repository does not contain those values.

The repository separates signing-free simulator verification from signed archive
creation. `fastlane test` and the GitHub Actions test job disable code signing.
The GitHub Actions test job runs the UI and hosted unit suites as separate
schemes so UI tests can control each app launch independently.
The manual archive lanes require `APPLE_TEAM_ID` (10-character Team ID),
`APPLE_BUNDLE_ID` (the registered bundle ID), and a numeric `BUILD_NUMBER`.
They pass `CODE_SIGN_STYLE=Automatic` and `-allowProvisioningUpdates` to
Xcode, with the App Store export configured for automatic signing. The
authenticated runner must therefore have the registered bundle ID, Associated
Domains capability, and permission to create or use its distribution profile.
Missing App Store Connect key variables fail before an archive is built.

Run `bundle exec fastlane preflight` on macOS after legal and support values are
approved to validate the source release gates without building. Run
`bundle exec fastlane beta` only from the manually dispatched workflow after
the signing and App Store Connect secrets are configured.

The `beta` lane reads the canonical `fastlane/metadata/en-US/beta_notes.txt`
file and passes it to TestFlight as the build changelog. The lane remains a
manual, authenticated release action and is not run by the repository's
simulator-test workflow.

The `release_upload` and `release_submit` lanes run a preflight before building:
they stop while the website Terms contain legal-owner placeholders or while a
verified HTTPS `fastlane/metadata/en-US/support_url.txt` is absent. The internal
beta lane is intentionally not blocked by those final legal/support gates, but
it still validates repository assets, signing inputs, and App Store Connect
credentials before building. Final screenshots remain portal-managed and are
not fabricated from browser or simulator captures by Fastlane.

The associated-domains entitlement names `applinks:soccerscanner.pro`. The server
intentionally returns no Apple App Site Association file until the required Apple
configuration is supplied. When enabled, it advertises only `/fixtures/*`, the
native route currently implemented by the client; team, competition, and calendar
web routes remain web-only until native destinations exist.

Use [the release checklist](../../docs/release-checklist.md) for the exact
repository-controlled checks and the remaining Apple, legal, support,
secondary-provider, production, and TestFlight blockers. It is intentionally
not a substitute for an authenticated macOS CI run or portal review.

## Known native gaps

- Calendar and global search do not yet have native screens. The server's
  `calendar_range_api` and `search` feature flags are currently disabled and no
  versioned native endpoint contract exists; the fixture list's local search is
  the supported search surface for this release. Team Intelligence is disabled
  across web, API, and native user-facing surfaces; its dormant compatibility
  code remains out of the release navigation.
- Physical-device accessibility validation, including VoiceOver and safe-area behaviour, requires macOS/device testing.
- The native client does not persist fixture snapshots yet: disconnected launches
  show the typed unavailable state rather than presenting unverified cached data.
  Timezone and score visibility are session-scoped; no account, notification, or
  persistent score-preference implementation exists.
- Terms remain a legal-review draft on the website; the app links to that existing page without presenting legal claims.
