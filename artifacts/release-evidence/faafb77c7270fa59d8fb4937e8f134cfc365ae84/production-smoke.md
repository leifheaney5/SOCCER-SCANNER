# Production release evidence — faafb77c7270fa59d8fb4937e8f134cfc365ae84

Deployed 2026-08-05. Railway production deployment: SUCCESS, branch main.

## /health/version
{"assetVersion":"faafb77c7270","buildTimestamp":null,"commitSha":"faafb77c7270fa59d8fb4937e8f134cfc365ae84","environment":"production","version":"2.0.0"}


## /health/ready
{"blocking":[],"build":{"assetVersion":"faafb77c7270","buildTimestamp":null,"commitSha":"faafb77c7270fa59d8fb4937e8f134cfc365ae84","environment":"production","version":"2.0.0"},"cache":{"backend":"redis","shared":true,"status":"ready"},"database":{"backend":"database","durable":true,"reachable":true,"schemaVersion":"20260804_01","status":"ready"},"missing":[],"providers":{"lastSuccessAt":null,"providers":[],"singleProvider":true,"status":"unknown"},"rateLimit":{"backend":"redis","degraded":false,"shared":true,"status":"ready"},"status":"ready"}


## Synthetic monitor
PASS live — HTTP 200
PASS ready — HTTP 200 blocking=[]
PASS providers — status=ok
PASS fixtures — HTTP 200 with 54 fixtures returned

Synthetic monitor passed against https://soccerscanner.pro

## Route checks
/terms HTTP 200
/robots.txt HTTP 200
/sitemap.xml HTTP 200
/api/v2/app-config HTTP 200
/.well-known/apple-app-site-association HTTP 404 (404 expected: Apple IDs unconfigured)

## Gates at merge
pytest 179 passed, 5 subtests
node --test 38 passed
playwright chromium+webkit 102 (1 known WebKit flake, see below)
npm audit 0 vulnerabilities
pip-audit no known vulnerabilities

## Known limitations at this revision
- ProviderHealthRegistry is per-gunicorn-worker, so /health/providers alternates
  between 'ok' and 'unknown' across WEB_CONCURRENCY workers. Verified in production:
  8 sequential requests returned 4x ok / 4x unknown. Outage detection is unaffected
  (the monitor's fixtures probe hits the real endpoint), but per-provider diagnosis
  is unreliable. Fix: back the registry with Redis, as the rate limiter already is.
- FOOTBALL_DATA_API_KEY unset: ESPN remains a single point of failure.
- tests/browser/fixtures-dashboard.spec.js:367 flakes ~1 in 8-18 on WebKit only.
