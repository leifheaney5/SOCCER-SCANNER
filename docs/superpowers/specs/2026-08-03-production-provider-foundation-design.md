# Production and Provider Foundation Design

**Status:** Approved direction (Option A: fixture-first workspace)

**Scope:** First of four production-hardening specifications. This slice establishes trustworthy build identity, explicit fixture-result semantics, bounded and reusable provider access, accurate ESPN normalization, and the observability required to prove those behaviors. Canonical cross-provider identity and team intelligence, dashboard interaction behavior, and final accessibility/security polish remain separate follow-on specifications.

## Context and baseline evidence

The current application is deployed from `main` at `bd036bf`, but the application cannot identify that build itself. `/health/ready` returns only readiness and missing-extension names, while templates use the date-based asset token `20260803-dashboard-v1`.

The fixture service currently:

- makes 40 ESPN calls for a two-UTC-date local matchday;
- caches only the final `date|timezone` response, preventing reuse across timezones;
- starts a request-local thread pool and returns after cancelling futures even though running HTTP calls can continue;
- asks Football-data.org for fallback data only when ESPN returns fewer than five matches;
- returns and caches an empty 200 response when all providers fail and no stale value exists;
- has no explicit `fresh`, `partial`, `stale`, `empty`, or `unavailable` result state;
- fabricates ESPN season 2024, 2024–25 dates, matchday 1, `REGULAR_SEASON`, and `Unknown Venue`;
- maps unknown ESPN statuses to `SCHEDULED` and uses kickoff as `lastUpdated`;
- logs ESPN conversion failures with `print`;
- reports provider-specific IDs as though the combined result were already canonical.

The deployed API reproduced the 40-call fan-out with six local fixtures. A separate cold request completed in roughly 470 ms and its immediate cache hit in roughly 92 ms, but both carried metadata for 40 ESPN requests. A live ESPN probe confirmed that a `YYYYMMDD-YYYYMMDD` date range returns the union available from the two individual dates for the sampled league. This permits one request per league for a two-day range, reducing the cold ceiling from 40 to 20 ESPN calls.

## Goals

This slice will:

1. Make the running application and every HTML asset reference identify the deployed build.
2. Distinguish a legitimate empty matchday from provider unavailability.
3. Preserve stale successful data only within an explicit stale window.
4. Normalize ESPN facts without invented values and retain raw status diagnostics safely.
5. Reduce a two-date ESPN fetch from 40 calls to at most 20 and reuse provider responses across timezones.
6. Bound concurrency, retries, response size, and request lifetime without leaving worker threads running after the response.
7. Call Football-data.org based on provider coverage, not an unrelated match-count threshold.
8. Expose safe provider/cache timing and count metadata to tests and structured logs.
9. Define stable provider-result and normalized-fixture interfaces for the canonical-identity specification.

## Non-goals and boundaries

This slice does not implement fuzzy cross-provider team mapping, canonical match merging, team-analysis caching, browser history, live polling, route retirement, or visual changes. It may add the fields those later slices require, but it will not guess provider mappings or claim cross-provider results are canonical before the canonical-identity slice lands.

The Flask/Jinja/vanilla-JavaScript architecture, existing compatibility routes, CSP approach, score privacy invariant, and black/white/lime visual system remain unchanged.

## Architecture

### Build metadata

Add a focused `BuildInfo` value created once during application startup. It contains:

- `application_version`: `APP_VERSION`, falling back to `soccer_scanner.version.__version__`, whose repository-owned default is the single application-version source;
- `commit_sha`: first non-empty value from `GIT_COMMIT_SHA` and `RAILWAY_GIT_COMMIT_SHA`, normalized to a full lowercase hexadecimal SHA when valid, otherwise `unknown` outside production;
- `build_timestamp`: `BUILD_TIMESTAMP` or `RAILWAY_DEPLOYMENT_CREATED_AT` when present, otherwise `null`;
- `environment`: `APP_ENVIRONMENT`, `RAILWAY_ENVIRONMENT_NAME`, or `development`;
- `asset_version`: the first 12 characters of a known commit SHA, otherwise a filesystem-safe application-version token.

`BuildInfo` is stored in `app.extensions`, injected into templates, and used for every first-party CSS and JavaScript query token. An HTML document and all modules it references therefore share one build-derived token. All first-party ES-module imports also include the same token; a new HTML shell cannot silently mix old unversioned modules with new entry points.

`GET /health/version` returns the four public build fields. `GET /health/ready` retains `status` and `missing`, adds the same nested `build` object, and remains 503 only when required extensions are absent. Neither endpoint exposes arbitrary environment data.

Startup emits one structured `application_started` log containing the short SHA, application version, and environment. Production startup fails fast if the commit SHA is missing or malformed; development and tests may use `unknown`.

### Provider HTTP boundary

Introduce a provider HTTP client shared by ESPN and Football-data.org adapters. It owns:

- a pooled `requests.Session` per provider;
- connect/read timeouts from configuration;
- a maximum JSON response size before parsing;
- JSON content validation;
- safe transient retries for connection errors, timeouts, 429, and 5xx responses;
- short exponential backoff with bounded jitter;
- `Retry-After` support capped by the remaining request budget;
- no retry for other 4xx responses;
- elapsed time, attempt count, status category, timeout, and rate-limit observations;
- provider-specific exceptions that never contain full response bodies.

Authorization headers, API keys, full URLs containing secrets, response payloads, and scores are never logged.

### Provider response cache and single-flight

Keep the existing bounded in-process cache model but separate reusable provider resources from rendered local-date results.

Provider cache keys are:

- ESPN: `espn|<league-id>|<provider-date-range>`;
- Football-data.org matches: `football-data|matches|<date-from>|<date-to>`.

The ESPN adapter requests one inclusive date range per configured league. A one-day local span uses `YYYYMMDD`; a two-day span uses `YYYYMMDD-YYYYMMDD`. The adapter must verify with contract tests that range results cover both individual provider dates and must fall back to individual-date calls only when the range response is observably unsupported or malformed. The normal two-date ceiling is therefore 20 ESPN calls, not 40.

Provider cache entries retain `fetched_at`, `fresh_until`, `stale_until`, outcome metadata, and sanitized normalized fixtures. A key-scoped single-flight lock ensures concurrent users share one upstream fill. Because the provider keys omit the visitor timezone, overlapping timezone requests reuse the same league/date resources.

Stale provider resources are never mixed into an otherwise current `fresh` or `partial` response. They are eligible only when current providers cannot produce usable data and the service is evaluating the composed `stale` fallback.

The final local-date response remains cached by `date|timezone`, but it is a cheap composition cache rather than the only cache. Unavailable results are never written to either cache.

### Bounded concurrency and deadline behavior

ESPN league work uses a request-scoped executor with a configured maximum of eight workers. The orchestration layer stops submitting new work when its soft deadline is exhausted, cancels work that has not started, and waits for every already-running request to finish under its shorter socket timeout before returning. Executor shutdown uses `wait=True` and `cancel_futures=True`; no provider thread survives the API response.

The request budget is propagated into retry decisions so a backoff cannot exceed the remaining budget. Provider metadata distinguishes completed, timed out, cancelled-before-start, rate-limited, and invalid-payload requests.

### Provider outcome interface

Each adapter returns a `ProviderOutcome` with:

- `provider`: stable provider name;
- `status`: `success`, `partial`, `unavailable`, or `disabled`;
- `fixtures`: normalized fixtures from successful requests;
- `successful_requests`, `failed_requests`, `timeout_count`, and `rate_limit_count`;
- `requested_resources` and `completed_resources`;
- `started_at`, `completed_at`, and `duration_ms`;
- `source_updated_at` when the provider supplies it;
- safe failure categories by resource, without raw bodies.

`disabled` means the provider is intentionally unavailable because required configuration is absent. It is not silently reported as `not_needed`. A disabled optional provider does not make a successful ESPN response partial, but coverage metadata makes the limitation explicit.

### Fixture-result state model

The orchestration result has exactly one top-level `state`:

- `fresh`: current provider data is usable, within the normal cache window, and no provider failure reduced coverage;
- `partial`: usable current fixtures exist, but one or more configured provider resources failed;
- `stale`: current providers could not produce usable data, but a previously successful result remains inside the stale window;
- `empty`: at least one authoritative provider completed enough of the requested coverage to confirm zero fixtures for the visitor's local date;
- `unavailable`: no provider produced usable current data, no provider authoritatively confirmed an empty day, and no valid stale result exists.

State selection is deterministic:

1. Filter normalized provider fixtures to the requested local calendar date.
2. If current fixtures exist, return `partial` when configured coverage failed, otherwise `fresh`.
3. If no fixture exists and at least one provider completed authoritative date coverage, return `empty`; an ESPN outcome is authoritative only when every requested league resource completed successfully, while a successful Football-data.org date-span response is authoritative for its configured coverage. Provider-health metadata may still show reduced optional coverage.
4. Otherwise, return `stale` when a prior successful response remains within the stale window.
5. Otherwise, raise `FixtureUnavailable` and return HTTP 503 with `state: unavailable`.

HTTP 503 responses contain only a generic message, stable error code, requested date, retryability, and correlation ID. Detailed provider failures remain server-side. Successful responses include:

- `state`, `date`, `timezone`, `matches`, and `last_updated`;
- `providers` with safe aggregate health;
- `cache` with `status`, `age_seconds`, and stale-window metadata;
- `source_stats.raw_matches` and `source_stats.normalized_matches`.

The existing `cached`, `stale`, and `partial` booleans remain temporarily for compatibility and are derived from `state`. `total_unique` is removed until the canonical-identity slice can prove uniqueness.

### ESPN normalization

Move ESPN conversion into a provider adapter that accepts both the scoreboard response context and an event. It returns a normalized fixture retaining explicit provider identity:

- `provider: espn` and `provider_match_id`;
- provider-aware home and away teams with `provider: espn` and `provider_team_id`;
- kickoff timestamp and a distinct `source_updated_at`;
- normalized competition name/code/country/emblem plus the raw league ID;
- numeric scores or `null`;
- venue, season, stage, round, matchday, and status only when supported by payload evidence;
- `raw_status` for diagnostics.

No missing fact receives an invented placeholder. Missing venue, season, stage, round, or matchday is `null` and omitted by later presentation code.

Status normalization explicitly covers scheduled, pre-match, in progress, first half, half-time, second half, extra time, extra-time half-time, penalty shootout, delayed, interrupted, suspended, postponed, cancelled/canceled, abandoned, finished, awarded, and unknown. Unknown statuses map to `UNKNOWN`, retain `raw_status`, and never default to scheduled.

Competition aliases normalize Champions League, Europa League, Conference League, country, and division names through a single table shared with the future canonicalizer. Scores accept integers and integer strings; every other value becomes `null`. Conversion failures use structured warning logs containing provider, event ID, league ID, and failure category only.

### Football-data.org fallback behavior

When configured, Football-data.org receives one cached matches request for the provider date span on every provider-cache miss, not only when ESPN produces fewer than five unrelated fixtures. This provides independent coverage and future canonical-merge input while limiting the fallback to one request per reusable date span.

A missing API key yields a `disabled` outcome. HTTP 429 yields a rate-limited `unavailable` outcome after honoring a bounded `Retry-After`; it is never treated as an empty matchday. Timeouts, invalid JSON, oversized bodies, and other provider failures are categorized consistently with ESPN.

## Observability

Every incoming request receives or generates a correlation ID, returned as `X-Request-ID` and included in safe error bodies. Structured JSON logs record:

- requested local date and validated timezone;
- response state and end-to-end duration;
- composition-cache and provider-cache hit/miss/stale/eviction counts;
- provider request count, latency, status category, timeout, and rate-limit counts;
- partial, stale, empty, and unavailable counters;
- raw and normalized fixture counts.

Logs omit scores, API keys, authorization headers, full payloads, and personal information.

A thread-safe in-process metrics registry exposes safe aggregate counters and timing summaries through `GET /health/metrics`. It reports process-lifetime aggregates only and does not accept dimensions from user input, preventing unbounded cardinality.

## Error and recovery behavior

Provider errors never cross the adapter boundary as raw `requests` exceptions. The fixture service translates outcomes into the state algorithm. Recovery after an outage replaces stale data with a fresh successful result and refreshes both provider and composition caches. A previous unavailable attempt cannot poison recovery because unavailable results are not cached.

The UI contract for this slice is limited to exposing the new state values without changing layout. Existing renderers continue to show distinct empty, partial, stale, and request-error treatments; the later dashboard specification will add refresh, offline, and timeout-specific behavior.

## Test design

### Unit and service tests

Add deterministic tests for:

- build metadata precedence, validation, safe fallback, ready/version responses, and asset version propagation;
- total provider failure with and without stale cache;
- one authoritative provider confirming an empty day;
- partial ESPN league failures with usable matches;
- Football-data.org 429, timeout, invalid JSON, oversized JSON, non-retryable 4xx, and recovery;
- retry count, backoff bounds, `Retry-After`, and request-budget exhaustion;
- provider cache reuse across same/different timezones;
- same-key cache stampede prevention and different-key concurrency;
- stale expiry and unavailable non-caching;
- no provider worker remaining after response completion;
- local-date filtering across UTC boundaries and daylight-saving transitions;
- all supported ESPN statuses and unknown-status preservation;
- dynamic/missing season, stage, round, matchday, venue, emblem, score, and source-update metadata;
- competition aliases and numeric score coercion;
- structured logs and metrics without score/API-key/payload leakage.

### Provider contract fixtures

Store small sanitized JSON documents under `tests/fixtures/providers/` for scheduled, live, half-time, extra-time/shootout, postponed/cancelled, missing metadata, schema variation, invalid JSON, Football-data.org scheduled/finished, and the sampled two-day ESPN range. Ordinary tests never call live providers.

### Browser and production smoke

Extend the mocked browser payloads to require a valid `state` and cache/provider metadata. Add a separate read-only production smoke command that accepts `BASE_URL` and `EXPECTED_SHA`, then verifies:

- `/`, `/health/live`, `/health/ready`, and `/health/version` return 200;
- ready/version report the exact expected SHA and environment;
- every first-party CSS and JavaScript URL uses the expected short SHA;
- the fixture API returns HTTP 200 with `fresh`, `partial`, `stale`, or `empty`, or HTTP 503 with `unavailable`;
- the page exits its loading state without uncaught JavaScript errors.

The smoke test must not require third-party fixtures to exist on a specific date.

## Performance acceptance

The implementation records before/after request counts and latency. Acceptance requires:

- at most 20 ESPN calls for the normal two-provider-date, 20-league cold path when range queries are supported;
- at most one Football-data.org matches call for the same date span;
- zero repeated upstream calls for an immediate composition-cache hit;
- reuse of overlapping provider resources across timezone cache misses;
- one upstream fill for concurrent requests sharing a provider key;
- no provider thread active after the API response;
- bounded provider cache size and explicit eviction metrics.

Cached response latency is measured in the same environment as the baseline; no unsupported absolute latency claim is made.

## Documentation and deployment contract

Update README, API, architecture, and deployment documentation with the build variables, state model, provider cache keys, retry/deadline rules, metrics fields, test commands, smoke command, and Railway verification procedure.

Railway deployment verification is authoritative only when:

1. the deployment reaches terminal `SUCCESS` for the intended full SHA;
2. `/health/ready` and `/health/version` return that same SHA;
3. the production smoke suite passes with `EXPECTED_SHA=<full-sha>`;
4. production HTML references asset tokens derived from that SHA.

## Follow-on interfaces

The canonical-identity specification consumes provider-aware normalized fixtures and `ProviderOutcome` values from this slice. It will add canonical team/competition/match IDs, mapping provenance/confidence, cross-provider merge precedence, conflict reporting, and genuine canonical counts without changing the state or provider-cache contracts defined here.
