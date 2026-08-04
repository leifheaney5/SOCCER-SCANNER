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

Browser coverage includes URL/history state, score non-leakage in DOM and accessibility content, fixture states and filters, refresh behavior, desktop/mobile dialogs, team request caching, favorites, calendar, deep links, PWA/offline sanitization, 320 px reflow, immutable assets, and axe scans. Synthetic screenshots cover default, revealed, filtered, context, favorite, partial, stale, empty, error, mobile sheet, and team drawer states. They are evidence artifacts, not pixel snapshots of provider data.

The concurrency/load suite is deterministic and does not call external providers. Existing cache tests cover multi-worker Redis coordination, TTL expiration, and Redis fallback; browser team-drawer tests prove per-team request caching; HTTP tests exercise slow-provider budget and retry behavior.

## Production smoke

```powershell
$env:BASE_URL='https://soccerscanner.pro'
$env:EXPECTED_SHA=(git rev-parse HEAD)
npm run smoke:production
```

The smoke requires a full 40-character SHA and fails on SHA/environment/asset mismatch, non-durable or schema-incompatible persistence, unshared Redis, missing/malformed/duplicate fixture IDs, invalid fixture contracts, static or console errors, revealed-by-default scores, or horizontal overflow at 320 px.

Production responses are live evidence and may legitimately show a stable provider error. They must never be replaced with mocked data during this check.
