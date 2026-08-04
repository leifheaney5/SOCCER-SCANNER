# Soccer Scanner

Soccer Scanner 2.0 is a spoiler-safe football fixture workspace built with Flask and vanilla JavaScript. The production site is [soccerscanner.pro](https://soccerscanner.pro).

## What it does

- Scans fixtures by local calendar date and IANA timezone across supported ESPN competitions.
- Keeps every score out of rendered DOM and accessibility content until the visitor explicitly reveals scores.
- Groups fixtures by competition with canonical team identities, crest fallbacks, deterministic de-duplication, source freshness, and data-quality evidence.
- Provides shareable filter and fixture URLs, a seven-day calendar, spoiler-free `.ics` exports, local favorites, team intelligence, and explicitly gated league-table embeds.
- Represents success, confirmed empty, partial, stale, rate-limited, and unavailable provider outcomes truthfully.
- Runs as an installable PWA. Offline fixture snapshots omit live fixtures and recursively remove scores before storage.

## Runtime architecture

The browser calls the versioned canonical endpoint `GET /api/v2/fixtures`. Flask coordinates typed ESPN and optional Football-Data.org adapters through a bounded provider deadline. Results are normalized, assigned canonical identities, merged, cached, and filtered back to the requested local date. Redis provides shared cache and single-flight coordination when configured; a size-bounded memory cache is the development fallback and reports degraded readiness in production.

See [architecture](docs/architecture.md), [API contract](docs/api.md), [data sources](docs/data-sources.md), [provider mapping](docs/provider-mapping.md), and [provider capabilities](docs/provider-capabilities.md).

## Local development

Requirements:

- Python 3.12
- Node.js 22 and npm 10

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm ci
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`. ESPN fixture coverage works without a credential. `FOOTBALL_DATA_API_KEY` is optional and enables declared Football-Data.org capabilities. Never commit `.env`.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `FOOTBALL_DATA_API_KEY` | Optional team, squad, and standings provider credential | unset |
| `REDIS_URL` | Shared production cache and cross-worker single-flight | memory fallback |
| `APP_ENVIRONMENT` | Build/runtime environment; production requires a commit SHA | Railway environment or `development` |
| `GIT_COMMIT_SHA` | Exact deployed Git revision | Railway commit SHA fallback |
| `PUBLIC_BASE_URL` | Canonical public origin | `https://soccerscanner.pro` |
| `TRUSTED_PROXY_HOPS` | Number of trusted reverse-proxy hops | `1` |
| `PORT` | HTTP port | `5000` |
| `WEB_CONCURRENCY` | Gunicorn workers | `2` |

The remaining timeout, cache, rate-limit, and provider bounds are defined in `soccer_scanner/config.py` and documented in [deployment](docs/deployment.md).

## Tests

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
python -m compileall -q app.py wsgi.py soccer_scanner
npm ci
npx playwright install chromium webkit
npm test
```

CI also checks every JavaScript file, serious/critical axe violations, dependency audits, committed secrets, concurrent cache/provider behavior, and synthetic visual-state artifacts. See [testing](docs/testing.md).

## Production verification

After Railway reports terminal `SUCCESS`, verify the exact revision rather than inferring deployment from Git:

```powershell
$env:BASE_URL='https://soccerscanner.pro'
$env:EXPECTED_SHA=(git rev-parse HEAD)
npm run smoke:production
```

The smoke checks root/live/ready/version, exact SHA and asset tokens, the fixture success/error contract, first-party asset and console failures, default hidden-score safety, and 320 px reflow.

## Privacy and boundaries

Score preference and favorites stay in browser `localStorage`; there are no user accounts. Client favorites are not notification consent. Events, lineups, detailed statistics, broadcast listings, and notifications remain unavailable until legitimate providers and required consent infrastructure exist.
