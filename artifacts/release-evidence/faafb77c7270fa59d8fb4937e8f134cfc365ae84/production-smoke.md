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

## Continuous monitoring — confirmed live

The scheduled synthetic monitor is firing against production and passing:

    2026-08-05T20:15:14Z  schedule  completed  success
    2026-08-05T21:48:00Z  schedule  completed  success

This is the definitive evidence for Phase 1's headline exit criterion — a
production fixture outage now produces a failed workflow run without anyone
watching. Before this merge, nothing did.

Observed caveat: the workflow declares `*/15 * * * *`, but the two observed runs
were ~93 minutes apart. GitHub Actions treats `schedule` as best-effort and
throttles it under load, so the real detection window is wider than 15 minutes.
Do not document a 15-minute guarantee. If a tighter bound is required, an
external uptime service is the correct mechanism.

## Final revision

Production settled on `4ad7d2bc511f724c89e97173538df8ce51ad049a` (the merge
above plus a documentation revert). Verified: `blocking: []`, shared Redis rate
limiting ready, durable PostgreSQL at schema `20260804_01`, monitor 4/4.
