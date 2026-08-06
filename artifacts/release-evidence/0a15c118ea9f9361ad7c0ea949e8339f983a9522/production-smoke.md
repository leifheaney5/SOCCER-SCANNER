# Phase 2 production release evidence — 0a15c118ea9f9361ad7c0ea949e8339f983a9522

Deployed 2026-08-06. Railway production deployment: SUCCESS, branch main.

## /health/version
{"assetVersion":"0a15c118ea9f","buildTimestamp":null,"commitSha":"0a15c118ea9f9361ad7c0ea949e8339f983a9522","environment":"production","version":"2.0.0"}


## /health/ready
{"blocking":[],"build":{"assetVersion":"0a15c118ea9f","buildTimestamp":null,"commitSha":"0a15c118ea9f9361ad7c0ea949e8339f983a9522","environment":"production","version":"2.0.0"},"cache":{"backend":"redis","shared":true,"status":"ready"},"database":{"backend":"database","durable":true,"reachable":true,"schemaVersion":"20260804_01","status":"ready"},"missing":[],"providers":{"degraded":false,"lastSuccessAt":"2026-08-06T16:26:23.189300+00:00","providers":[{"detail":null,"lastObservedAt":"2026-08-06T16:26:23.189300+00:00","lastSuccessAt":"2026-08-06T16:26:23.189300+00:00","name":"espn","status":"ok"},{"detail":null,"lastObservedAt":"2026-08-06T16:26:23.190800+00:00","lastSuccessAt":null,"name":"football-data","status":"disabled"}],"shared":true,"singleProvider":true,"status":"ok"},"rateLimit":{"backend":"redis","degraded":false,"shared":true,"status":"ready"},"status":"ready"}


## Provider health consistency across workers
Phase 1 shipped an in-process registry; 8 sequential production requests then returned
4x ok / 4x unknown depending on which gunicorn worker answered. After the Redis-backed
registry, the same probe returns:
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']
  status=ok ['espn:ok', 'football-data:disabled']

## Icon suite
/static/icons/icon-192.png HTTP 200 image/png
/static/icons/icon-512.png HTTP 200 image/png
/static/icons/icon-maskable-512.png HTTP 200 image/png
/static/icons/apple-touch-icon.png HTTP 200 image/png
/static/icons/favicon-32.png HTTP 200 image/png
/static/social-card.png HTTP 200 image/png

## Header controls present in served HTML
app-title-mark
aria-haspopup="dialog"
id="timezone-trigger"

## Synthetic monitor
PASS live — HTTP 200
PASS ready — HTTP 200 blocking=[]
PASS providers — status=ok
PASS fixtures — HTTP 200 with 54 fixtures returned

Synthetic monitor passed against https://soccerscanner.pro

## Gates at merge
pytest 209 passed, 24 subtests (also verified in a clean venv)
node --test 38 passed
playwright chromium+webkit 144 passed
npm audit 0 vulnerabilities; pip-audit no known vulnerabilities
