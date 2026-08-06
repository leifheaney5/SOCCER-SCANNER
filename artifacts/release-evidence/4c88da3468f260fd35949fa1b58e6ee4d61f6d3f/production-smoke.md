# Close-out production evidence — 4c88da3468f260fd35949fa1b58e6ee4d61f6d3f

Deployed 2026-08-06. Railway production: SUCCESS.

## /health/version
{"assetVersion":"4c88da3468f2","buildTimestamp":null,"commitSha":"4c88da3468f260fd35949fa1b58e6ee4d61f6d3f","environment":"production","version":"2.0.0"}


## /health/ready
{"blocking":[],"build":{"assetVersion":"4c88da3468f2","buildTimestamp":null,"commitSha":"4c88da3468f260fd35949fa1b58e6ee4d61f6d3f","environment":"production","version":"2.0.0"},"cache":{"backend":"redis","shared":true,"status":"ready"},"database":{"backend":"database","durable":true,"reachable":true,"schemaVersion":"20260804_01","status":"ready"},"missing":[],"providers":{"degraded":false,"lastSuccessAt":"2026-08-06T23:40:43.702500+00:00","providers":[{"detail":null,"lastObservedAt":"2026-08-06T23:40:43.702500+00:00","lastSuccessAt":"2026-08-06T23:40:43.702500+00:00","name":"espn","status":"ok"},{"detail":null,"lastObservedAt":"2026-08-06T23:40:43.708800+00:00","lastSuccessAt":null,"name":"football-data","status":"disabled"}],"shared":true,"singleProvider":true,"status":"ok"},"rateLimit":{"backend":"redis","degraded":false,"shared":true,"status":"ready"},"status":"ready"}


## Synthetic monitor
PASS live — HTTP 200
PASS ready — HTTP 200 blocking=[]
PASS providers — status=ok
PASS fixtures — HTTP 200 with 64 fixtures returned

Synthetic monitor passed against https://soccerscanner.pro

## Country resolution against live data
fixtures=64 with-country=9 distinct-countries=6
  Argentine Liga Profesional de F�tbol -> Argentina
  Bolivian Liga Profesional -> Bolivia
  English Carabao Cup -> England
  Mexican Liga de Expansi�n MX -> Mexico
  Peruvian Liga 1 -> Peru
  Venezuelan Primera Divisi�n -> Venezuela

## Gates
231 Python + 72 subtests; 41 Node; 162 Playwright (chromium+webkit); npm audit 0; pip-audit 0
Merged WITHOUT CI (GitHub Actions unavailable). Compensating control: full suite in a
clean virtualenv with only declared dependencies — 232 passed.
