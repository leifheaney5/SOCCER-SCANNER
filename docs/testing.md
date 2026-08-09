# Testing and release evidence

## Local release matrix

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
python -m compileall -q app.py wsgi.py soccer_scanner
Get-ChildItem static,tests -Recurse -File -Include *.js,*.mjs | ForEach-Object { node --check $_.FullName }
npm run test:smoke-invariants
npm audit --audit-level=high
pip-audit -r requirements.txt
npx playwright test --project=chromium --project=webkit
git diff --check
```

Python coverage includes provider transport bounds, ESPN status fixtures, Football-Data.org adaptation, canonical identity and merge behavior, truthful orchestration states, fresh/stale/expired caches, Redis distributed single-flight and fallback, rate-limit bursts, concurrent timezone reuse, team services, build identity, headers, routes, and API contracts.

Browser coverage includes URL/history state, score non-leakage in DOM and accessibility content, fixture states and filters, refresh behavior, desktop/mobile dialogs, calendar day-level failures and retries, timezone-preserving deep links, PWA/offline sanitization, 320 px reflow, immutable assets, and axe scans. Synthetic screenshots cover default, revealed, filtered, context, partial, stale, empty, error, and mobile-sheet states. Team Intelligence and persistent favorites are intentionally not active surfaces.

The concurrency/load suite is deterministic and does not call external providers. Existing cache tests cover multi-worker Redis coordination, TTL expiration, and Redis fallback; browser team-drawer tests prove per-team request caching; HTTP tests exercise slow-provider budget and retry behavior.

## Native iOS gate

The native client has a separate macOS-only gate in
`.github/workflows/ios.yml`. The workflow generates the Xcode project with
XcodeGen, validates generated build settings, the privacy manifest, entitlements,
icons, metadata, legal/support release preflight, and simulator selection, then
runs the unit/UI scheme without signing. It uploads both the `.xcresult` bundle
and raw `xcodebuild` output, including when tests fail. Release lanes are manual
and are never part of the simulator-test job.

Repository-controlled checks that do not require Xcode can be run on Windows:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_ios_release_assets.py tests/test_ios_simulator_selection.py -q
python tests/test_ios_release_assets.py
```

These checks validate source release assets, the shared score-spoiler binding,
native state-fixture and broadcast wiring, CI path filters, Fastlane preflight,
metadata, and the dependency-free simulator selector. Windows cannot prove
Swift compilation, XCTest/XCUITest execution, simulator behavior, VoiceOver,
physical-device safe areas, or TestFlight installation; only a fresh successful
macOS workflow for the intended release commit proves those gates.

## Production smoke

```powershell
$env:BASE_URL='https://soccerscanner.pro'
$env:EXPECTED_SHA=(git rev-parse HEAD)
$env:EXPECTED_ENVIRONMENT='production'
npm run smoke:production
```

The smoke requires a full 40-character SHA and fails on SHA/environment/asset mismatch, non-durable or schema-incompatible persistence, unshared Redis, missing/malformed/duplicate fixture IDs, invalid fixture contracts, static or console errors, revealed-by-default scores, or horizontal overflow at 320 px.

For staging, set its public `BASE_URL` and `EXPECTED_ENVIRONMENT=staging`; all other dependency, identity, browser, and exact-SHA checks remain identical.

Production responses are live evidence and may legitimately show a stable provider error. They must never be replaced with mocked data during this check.
