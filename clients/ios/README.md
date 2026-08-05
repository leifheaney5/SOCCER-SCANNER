# Soccer Scanner — iOS client

A native SwiftUI client for the Soccer Scanner v2 API. Not a `WKWebView` wrapper.

## Status

| Item | State |
| --- | --- |
| SwiftUI app, typed API client, DI, design system | written |
| Fixture vertical slice (list → detail, spoiler-safe, timezone-aware, universal links) | written |
| Unit tests (33 cases) and UI tests (5 cases) | written |
| Privacy manifest, entitlements, app icon | written and validated |
| fastlane lanes + `macos-latest` CI | written |
| **Compiled / test-run** | **BLOCKED — no macOS toolchain in the authoring environment** |
| **Submitted to the App Store** | **not submitted** |

Xcode, `xcodebuild` and the App Store upload tooling are macOS-only. This project has
therefore **never been compiled locally**. The `iOS` GitHub Actions workflow on
`macos-latest` is the verification path; treat its first green run as the point at which
"builds and tests pass" may be claimed. Until then, assume compile errors are possible.

## Layout

```
clients/ios/
  project.yml                    XcodeGen spec — the .xcodeproj is generated, not committed
  Gemfile                        fastlane toolchain
  Tools/generate_app_icon.py     reproducible 1024px App Store icon
  fastlane/                      Fastfile, Appfile, App Store metadata
  SoccerScanner/
    App/                         entry point + composition root
    Config/                      development / staging / production environments
    Models/                      Fixture, MatchStatus, AppConfig
    Networking/                  typed APIClient and APIError
    Features/                    Fixtures list, Fixture detail
    DesignSystem/                Theme, StatusBadge
    Storage/                     Keychain abstraction
    Support/                     timezone formatting, deep links, preview data
    Resources/Assets.xcassets    AppIcon, AccentColor
    PrivacyInfo.xcprivacy        declares: collects nothing, no tracking
  SoccerScannerTests/
  SoccerScannerUITests/
```

## Cross-platform invariants

Three behaviours must not diverge from the web client, and are tested on both sides:

1. **Status taxonomy** — `MatchStatus` mirrors `static/js/match-status.js`. Half time,
   extra time and penalties are distinct from generic live; abandoned is terminal;
   suspended stays active.
2. **Timezone** — the selected zone controls both displayed time and calendar-day
   membership. `TimeZone.current` is never used implicitly.
3. **Score privacy** — scores start hidden on every launch and are never persisted, and a
   status without a meaningful score never renders one.

## Local development (requires macOS)

```bash
brew install xcodegen
cd clients/ios
xcodegen generate
open SoccerScanner.xcodeproj
```

Point the app at a local backend with `SOCCER_SCANNER_ENVIRONMENT=development`.

## Release automation

Authentication uses an **App Store Connect API key**, not an Apple ID password — API keys
are non-interactive and unaffected by two-factor prompts.

| Lane | Effect |
| --- | --- |
| `fastlane test` | simulator unit + UI tests |
| `fastlane build` | signed App Store archive |
| `fastlane beta` | upload to TestFlight, internal only |
| `fastlane release_upload` | upload binary + metadata, **does not submit** |
| `fastlane release_submit` | upload **and** submit for review |

Run them from CI: **Actions → iOS → Run workflow →** choose a lane. The release job is
gated on the `app-store` environment and never runs automatically on push.

## What a human must do — this cannot be automated away

These steps require an authenticated human in Apple's portals. Nothing in this repository
can perform them.

1. **Enrol in the Apple Developer Program** (`leif@leifheaney.com`), $99/year. Requires
   payment and legal-identity verification.
2. **Register the bundle ID** — suggested `pro.soccerscanner.app` — with the
   *Associated Domains* capability enabled.
3. **Create the app record** in App Store Connect (name, primary language, SKU).
4. **Generate an App Store Connect API key** (Users and Access → Integrations → App Store
   Connect API) with *App Manager* role. Download the `.p8` **once** — it cannot be
   re-downloaded.
5. **Add repository secrets**: `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_KEY_ID`,
   `APP_STORE_CONNECT_PRIVATE_KEY` (the `.p8` contents), `APPLE_TEAM_ID`,
   `APPLE_BUNDLE_ID`.
6. **Set `APPLE_TEAM_ID` and `APPLE_BUNDLE_ID` on the Railway `web` service** so
   `/.well-known/apple-app-site-association` starts serving. Universal links do not work
   until this is done — the route currently returns 404 by design rather than publishing
   invented identifiers.
7. **Provide screenshots** for 6.7" and 6.5" devices in `fastlane/screenshots/`. The store
   listing cannot be submitted without them.
8. **Answer the privacy questionnaire** in App Store Connect to match
   `PrivacyInfo.xcprivacy`: no data collected, no tracking.
9. **Accept the Paid/Free Applications agreement**, or the build cannot be distributed.
10. **Review the listing and press Submit** (or run the `release_submit` lane once the
    listing has been reviewed at least once by a human).

### Order of operations

Do 1–5 first, then trigger **Actions → iOS → Run workflow → `beta`**. Confirm the build
appears in TestFlight and installs. Only then do 6–10 and run `release_upload`.

## Known gaps

- Only the fixture vertical slice exists. Calendar, team intelligence and search are not
  implemented natively.
- No push notifications: the notifications ADR has not been written, so APNs is
  deliberately absent.
- No accounts, matching the guest-mode decision in
  `docs/decisions/accounts-and-preferences.md`.
- Localisation is English-only; strings use `String(localized:)` so a String Catalog can be
  added without code changes.
