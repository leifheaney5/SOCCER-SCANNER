# Soccer Scanner release checklist

This checklist is the release gate for the native iOS client and its supporting
web/API surfaces. It records repository-controlled evidence separately from
actions that require an Apple portal, a deployment owner, legal review, or a
verified support owner.

Do not treat a historical CI run, a source file, or a passing local static check
as proof that a future or uncommitted tree is buildable or ready for submission.
Record the exact commit SHA and link the evidence for every completed gate.

## Current checkout

- Audited date: 2026-08-08.
- Current branch: `main`.
- The working tree is clean after the final-completion merge. The release SHA,
  macOS CI run, merge, Railway deployment, and production smoke result are
  recorded below.
- The previous deployed baseline was
  `7759b5dd1ec33ef7b70ab87488593ad4b4c749ba`.
- Candidate release SHA: `64b6a6b625ae8ef2d9fd1606c9e54565097e2b58`.
- No Apple Developer, App Store Connect, TestFlight, or secret access is
  performed by this checklist.

## Repository-controlled and automatable

Complete these checks against the exact release commit. Attach CI logs or local
command output where applicable.

- [x] `clients/ios/SoccerScanner/Info.plist` exists, is valid XML plist data,
  and matches the XcodeGen properties: display name `Soccer Scanner`, version
  `1.0.0`, build `1`, launch-screen dictionary, non-exempt encryption flag,
  and portrait/landscape orientations. The bundle identifier remains a build
  setting; no Apple Team ID is stored here.
- [x] Generate the project with XcodeGen from `clients/ios/project.yml` and
  confirm generation succeeds on macOS in GitHub Actions.
- [x] Run the current iOS workflow on macOS. It generated the project,
  validate the privacy manifest and entitlements, build without signing,
  ran unit tests and UI tests, and retained the `.xcresult` and failure logs in
  the workflow artifacts. Successful run: GitHub Actions iOS run
  `31289973761`.
- [x] Confirm the generated target has the intended deployment target (`iOS
  17.0`), bundle identifier default (`pro.soccerscanner.app` unless the
  registered release value is supplied at build time), semantic version, and
  monotonic build number.
- [x] `clients/ios/SoccerScanner/PrivacyInfo.xcprivacy` is present in the
  source tree and declares the current no-tracking/no-collected-data posture.
  A macOS/App Store review must still confirm that it matches actual native
  behavior and App Store Connect questionnaire answers.
- [x] The associated-domains entitlement is source-controlled as
  `applinks:soccerscanner.pro`; the AASA server route has guarded logic and
  tests. It is not marked live until the identifiers and endpoint checks in
  the human section pass.
- [x] Fastlane metadata templates exist for the app name, subtitle,
  description, keywords, category, marketing URL, privacy URL, terms URL, and
  these release notes. The metadata is still subject to human content/legal
  review.
- [ ] Add and review final beta notes and a verified support URL/owner in the
  App Store metadata. No support destination is currently configured.
- [ ] Add and review final App Store screenshots for the required device
  families, or add a repeatable capture asset/automation path. Repository
  browser screenshots or simulator captures are not, by themselves, accepted
  App Store Connect evidence.
- [x] Repository validation now covers the source bundle identifier,
  deployment target, version/build, icon, entitlements, privacy manifest,
  metadata, Fastlane generation path, beta changelog wiring, simulator selector, and the iOS
  workflow's generated build settings/log capture. Generated Xcode projects and
  user state are ignored. Signed archive lanes validate the Team ID, registered
  bundle ID, build number, App Store Connect key inputs, and automatic-signing
  contract before building. The App Store submission lanes also enforce the
  legal-placeholder and verified-support-URL gates before building. A current macOS workflow
  run is still required as evidence for the generated project and simulator
  behavior. Successful duplicate push-triggered run: `31289967184`.
- [x] Run the repository verification matrix on the current candidate tree:
  Python tests (`264 passed, 72 subtests`), Node tests, smoke invariants (4),
  full Chromium and WebKit browser suites (94 each), JavaScript syntax, Python
  compile, release-asset validation, npm audit, requirements-scoped pip-audit,
  and `git diff --check`. Chromium and WebKit were run independently after the
  combined runner exposed a stale expectation plus a server cascade; both
  independent runs passed.
- [x] Run the production smoke script after the candidate deployment, with the
  exact deployed SHA and environment recorded:

  ```powershell
  $env:BASE_URL = 'https://soccerscanner.pro'
  $env:EXPECTED_SHA = '64b6a6b625ae8ef2d9fd1606c9e54565097e2b58'
  $env:EXPECTED_ENVIRONMENT = 'production'
  npm run smoke:production
  ```

  Result: passed with `status: ok`, `fixtureStatus: 200`, `fixtureState: success`,
  143 fixtures, and 143 unique IDs. The smoke also checks public robots/sitemap,
  favicon/manifest, the local
  streaming icon, Terms noindex behavior, the timezone control, asset-version
  tokens, spoiler safety, unique fixture IDs, and 320px layout safety.
- [x] Confirm production `/health/live`, `/health/ready`, `/health/version`,
  fixture responses, spoiler-safe behavior, console/static errors, public
  assets, and the 320px smoke path using the candidate production-smoke result.
  Railway deployment `3206fab7-8758-426e-8e60-ad8010695aec` reached terminal
  `SUCCESS`; both production health endpoints report the candidate SHA,
  version `2.0.0`, schema `20260804_01`, durable Postgres, and shared Redis.
- [x] Run the dependency/security checks required by `docs/testing.md`:
  `npm audit --audit-level=high` passed with 0 vulnerabilities and
  `python -m pip_audit -r requirements.txt --progress-spinner off` passed with
  no known vulnerabilities.

## Human, portal, and external-configuration blockers

Do not check an item until the named owner has supplied evidence. Never commit
the values below when they are credentials or environment-specific secrets.

- [ ] Apple Developer Program enrollment is active and the legal agreements
  needed for distribution are accepted.
- [ ] The final bundle ID is registered in the Apple Developer portal, with
  Associated Domains enabled. The repository default is not proof of
  registration.
- [ ] The Apple Team ID and final bundle ID are supplied through the approved
  release/build configuration. Do not invent either value in source control.
- [ ] The App Store Connect app record exists and is associated with the
  registered bundle ID and the intended version/build.
- [ ] App Store Connect API-key credentials and signing/provisioning values are
  configured in the approved secret store. No `.p8`, password, certificate,
  or provisioning profile belongs in this repository.
- [ ] The AASA endpoint at
  `https://soccerscanner.pro/.well-known/apple-app-site-association` returns
  the final `TEAM_ID.BUNDLE_ID` app identifier, correct paths/components,
  `200`, JSON content type, HTTPS, and no redirect. Verify both the device
  Universal Link behavior and the server response. The endpoint is expected to
  remain disabled until the identifiers are configured.
- [ ] The website Terms page has completed legal review. Its current draft
  placeholders for operating entity, effective date, registered address,
  governing law, venue, liability cap, and contact information must be
  replaced or explicitly resolved by the legal owner before submission. Do
  not fill these values with guesses.
- [ ] A real support destination and accountable support owner are approved
  and added to the App Store metadata and native Settings surface. There is
  currently no verified support URL or contact in this repository; the native
  client must not claim support is available until one exists.
- [ ] Final App Store screenshots are captured from the release build for all
  required device sizes, reviewed for spoiler leakage, and uploaded to App
  Store Connect.
- [ ] The store description, subtitle, keywords, release notes, privacy URL,
  terms URL, marketing URL, and support URL are reviewed in App Store Connect.
  Existing terms metadata points to a legal draft and is therefore not a
  submission approval.
- [ ] App Store privacy questionnaire answers match `PrivacyInfo.xcprivacy`,
  native UserDefaults usage, network requests, and any crash/analytics SDKs
  actually present. No analytics or crash reporting may be implied if it is
  not implemented.
- [ ] `FOOTBALL_DATA_API_KEY` is supplied by the deployment owner in the
  approved secret store for the environments that require secondary-provider
  coverage. It is currently documented as absent; do not commit or print the
  credential. After configuration, verify `/health/providers`, fallback, and
  partial/stale behavior without claiming identical provider coverage.
- [x] The candidate production deployment is identified by exact SHA
  `64b6a6b625ae8ef2d9fd1606c9e54565097e2b58`, and the matching production
  smoke result is attached above. Railway deployment ID:
  `3206fab7-8758-426e-8e60-ad8010695aec`.
- [ ] The release build is installed on physical devices through TestFlight;
  Dynamic Type, VoiceOver, safe areas, Universal Links, spoiler behavior, and
  representative offline/provider-error states are reviewed.
- [ ] A human release owner reviews the complete listing, legal status,
  privacy answers, support path, screenshots, and TestFlight feedback before
  choosing whether to submit. The repository's `release_submit` lane must not
  be used as a substitute for that review.

## Release decision

The release is **blocked** while any of the following remain unchecked:

1. Current macOS generation/build/unit/UI evidence.
2. Terms legal review and removal/resolution of all legal placeholders.
3. Approved support destination and owner.
4. Apple registration, Team ID/bundle ID, signing, and AASA verification.
5. Final screenshots, metadata, and privacy questionnaire review.
6. Secondary-provider decision and credential configuration where required.
7. Exact-SHA production smoke and physical-device/TestFlight review.

When all gates are satisfied, record the release SHA, CI run, smoke result,
TestFlight build number, reviewer, and submission decision in the release
record. This checklist intentionally does not authorize deployment, portal
changes, secret access, or submission.
