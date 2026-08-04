# Soccer Scanner Baseline Audit

**Captured:** 2026-08-03  
**Repository:** `leifheaney5/SOCCER-SCANNER`  
**Local branch:** `main` at `2e6ed98`, one documentation-only commit ahead of `origin/main`  
**Production:** [https://soccerscanner.pro/](https://soccerscanner.pro/)  
**Production source revision:** `bd036bf`, Railway deployment `883020dc-b45b-4082-8f24-25e0d2ded4cd`

This document records the behavior before the comprehensive reliability and product overhaul. The only local change ahead of the deployed source is the approved provider-foundation design; no application behavior had changed when this baseline was captured.

## Environment and installation

- Python resolved to 3.10 on the Windows workstation; CI currently uses Python 3.12.
- `python -m pip install -r requirements.txt` completed successfully with every pinned dependency already installed. Pip reported an unrelated local `-umpy` distribution warning.
- `npm install` completed successfully with zero reported vulnerabilities.
- `npx playwright install chromium webkit` completed successfully.
- No local `.env` file exists.
- `FOOTBALL_DATA_API_KEY` is not present in the local process.
- Railway exposes only Railway-provided variables; `FOOTBALL_DATA_API_KEY` is not configured in production.

A real Football-data.org credential was therefore not available for a live-key baseline. The configured-provider path will be exercised through sanitized provider contract fixtures and mocked HTTP integration tests. A real production key remains an explicit deployment prerequisite for Football-data.org-backed team details.

## Baseline commands and results

| Command | Result |
| --- | --- |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` | 16 passed in 0.90s |
| `npm test -- --reporter=line` | 22 Chromium tests passed in 23.0s |
| `npx playwright test --browser webkit --reporter=line` | 22 WebKit tests passed in 35.2s |
| `python -m compileall -q app.py wsgi.py soccer_scanner` | Passed |
| `node --check` for every file under `static/js` | Passed |
| `git diff --check` | Passed |

The first concurrent Chromium/WebKit attempt was invalid because both Playwright processes shared port 5100 and one runner terminated the common web server. Both engines passed when run serially. CI must run browser projects through one Playwright invocation or isolated ports.

## Local browser and network baseline

The existing browser suite covers the dashboard at 320, 375, 430, 768, 1024, 1280, and 1440 CSS pixels, plus narrow portrait and mobile landscape states. It passes its current assertions in Chromium and WebKit.

The passing result hides several network and contract defects:

- Every mocked crest failure requests `/static/missing-home-crest.svg` and receives a first-party 404. Multiple tests repeat the failed request.
- Only the entry scripts and styles receive the hardcoded token `20260803-dashboard-v1`. Imported modules such as `fixture-state.js`, `fixture-renderer.js`, `score-preference.js`, `match-context.js`, `team-drawer.js`, and `crest.js` are requested without a build token.
- The local Playwright server uses Flask's development server even though the production runtime is Gunicorn.
- The current suite mocks almost every fixture response and does not exercise provider timeout, 429, malformed JSON, oversized payload, shared-cache, or multi-worker behavior.
- There are no axe checks, visual baselines, PWA/offline checks, history restoration checks, adaptive polling tests, or 400 percent zoom checks.

## Production endpoint baseline

Fresh checks against the custom domain produced:

| Endpoint | Status | Observed latency | Key observation |
| --- | ---: | ---: | --- |
| `/` | 200 | 397ms | No explicit response cache policy or HSTS |
| `/health/live` | 200 | 216ms | Process-only response; no build identity |
| `/health/ready` | 200 | 169ms | Only `status` and `missing`; no version/SHA/provider degradation |
| `/api/matches-today?date=2026-08-03&timezone=America/New_York` cold | 200 | 1252ms | Six fixtures; 40 ESPN requests |
| Same API request, immediate warm | 200 | 160ms | Final-response process cache hit |
| `/teams` | 200 | 145ms | Hidden legacy surface; downstream team calls fail without Football-data.org |
| `/league-tables` | 200 | 137ms | Hidden SofaScore surface with score-spoiler exposure risk |

The production fixture response has `cached`, `stale`, and `partial` booleans but no authoritative `state`. Its provider metadata reported 20 competitions and 40 successful ESPN requests for a single local date. Football-data.org was labeled `not_needed` because six ESPN fixtures exceeded the hardcoded threshold.

The response headers include a CSP, but:

- `Strict-Transport-Security` is absent.
- `frame-ancestors` is absent from CSP.
- HTML and API responses do not declare a deliberate `Cache-Control` policy.
- The CSP permits any HTTPS image host.

The deployed HTML uses the hardcoded asset token `20260803-dashboard-v1` and does not expose a build SHA. `/health/version` does not exist.

## Confirmed defects

### Provider correctness

1. ESPN team IDs are exposed as unqualified IDs and are passed to the Football-data.org team-analysis route. A direct production request using an ESPN team ID returned 502.
2. Fixture deduplication keys primarily on provider `id`, so the same match from ESPN and Football-data.org survives as two records.
3. When ESPN and Football-data.org both fail without stale data, the service constructs and caches a successful empty result. The UI can therefore say “No matches scheduled” during an outage.
4. Football-data.org fallback is controlled by `len(matches) < 5` rather than coverage and provider health.
5. One uncached local-day request fans out to 20 leagues across two provider dates: 40 ESPN calls. ESPN accepts an inclusive two-date range for the sampled competition, so this fan-out is unnecessary.
6. Pending provider futures are cancelled and the executor is shut down with `wait=False`, allowing already-running work to outlive the response.
7. Cache and single-flight state are process-local, so multiple Gunicorn workers can duplicate provider fills.
8. ESPN normalization fabricates season 2024, fixed 2024-25 dates, matchday 1, regular-season stage, and “Unknown Venue.”
9. Unknown ESPN status maps to scheduled rather than remaining unknown.
10. Source update time is conflated with kickoff time.
11. Provider failures are broadly swallowed, and normalization prints debugging output instead of structured logging.

### Frontend state

1. Clearing a search while its debounce is pending allows the old query to reappear in the input and URL.
2. Invalid or empty date state can fall through to a generic provider-unavailable presentation.
3. Changing filters can leave a selected fixture visible in the context panel even when it is absent from the filtered result set.
4. State changes use `replaceState` without a complete `popstate` restoration path.
5. Open tabs do not poll; live states can remain stale indefinitely.
6. Responsive context surfaces choose desktop panel or mobile dialog only when rendering. Rotation/resizing is not centrally reconciled.
7. Error handling collapses multiple API/network failures into a generic message.
8. `/teams` and `/league-tables` are not discoverable in primary navigation.
9. League tables expose externally rendered standings without an explicit spoiler reveal.

### Product and data quality

1. Schedule order is popularity/importance-first rather than predictable chronology.
2. Heuristic TV coverage and attendance estimates appear alongside provider-derived facts.
3. Missing team fields can be coerced to zero.
4. Team analysis performs overlapping sequential provider queries and has no durable shared cache.
5. There are no favorites, multi-day calendar, canonical fixture deep links, ICS export, source inspector, privacy page, manifest, or service worker.
6. Public fixture objects mix legacy field conventions and expose provider-shaped data without a documented versioned schema.

## Baseline response and failure semantics

The current API distinguishes some validation failures, but it does not use one stable error envelope. It also lacks typed success outcomes. The implementation must introduce:

- `success`
- `partial`
- `stale`
- `empty_confirmed`
- `provider_unavailable`
- `rate_limited`
- `invalid_request`

An authoritative empty day must require at least one complete provider response. An outage must never enter the normal or stale caches as an empty day.

## Performance baseline and budgets

Measured production behavior:

- Cold fixture composition: 1252ms for the sampled date.
- Immediate warm composition: 160ms.
- Upstream requests on the cold path: 40 ESPN, zero Football-data.org.
- Upstream requests on the warm path: zero, from the final-response process cache.

Release budgets:

- No more than 20 ESPN requests for the normal two-provider-date window.
- No more than one Football-data.org matches request per provider-cache miss.
- Zero upstream calls for immediate provider/final cache hits.
- One fill for concurrent identical keys across Gunicorn workers.
- Bounded provider workers, retries, cache entries, and request duration.
- No provider thread survives response completion.

## Scope decisions

The approved product direction is fixture-first:

- The dashboard remains the primary workspace.
- Team intelligence opens from provider-aware fixture context and links to stable team pages when supported.
- `/teams` becomes an intentional compatibility route until the first-class team directory is complete.
- `/league-tables` remains a discoverable secondary utility with an explicit score-spoiler reveal.
- Provider-gated match events, statistics, notifications, and broadcast data receive typed interfaces and backlog documentation, but are not fabricated when current providers cannot support them.

## Baseline conclusion

The current application is visually coherent and its narrow mocked test suite is green, but the production data path is not yet trustworthy under provider failure, cross-provider identity, or multi-worker load. The first implementation slice must establish build identity, provider HTTP/cache/outcome foundations, truthful empty/outage semantics, and observable bounded concurrency before product expansion.
