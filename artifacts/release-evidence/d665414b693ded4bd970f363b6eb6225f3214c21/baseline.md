# Baseline evidence — captured 2026-08-04

## Local
branch: feat/deliberate-guest-mode
HEAD: 8943dfed2c9e63692f938c4e66bb033ab3269a37
main: d665414b693ded4bd970f363b6eb6225f3214c21

## Production /health/version
{"assetVersion":"d665414b693d","buildTimestamp":null,"commitSha":"d665414b693ded4bd970f363b6eb6225f3214c21","environment":"production","version":"2.0.0"}

## Production /health/ready
{"blocking":[],"build":{"assetVersion":"d665414b693d","buildTimestamp":null,"commitSha":"d665414b693ded4bd970f363b6eb6225f3214c21","environment":"production","version":"2.0.0"},"cache":{"backend":"redis","shared":true,"status":"ready"},"database":{"backend":"database","durable":true,"reachable":true,"schemaVersion":"20260804_01","status":"ready"},"missing":[],"status":"ready"}

## Gates
pytest: 119 passed
node --check: all JS/MJS OK
compileall: OK
smoke-invariants: 4/4 pass
npm audit --audit-level=high: 0 vulnerabilities
pip-audit: TOOL NOT INSTALLED (blocked)
git diff --check: clean
