# API reference

Public JSON endpoints require no client authentication. Expensive routes are protected by a bounded per-process rate limiter. Every response receives `X-Request-ID`; versioned API errors include the same request ID.

## Canonical fixture API

### `GET /api/v2/fixtures`

Query parameters:

- `date`: required format `YYYY-MM-DD`; defaults to the server's current date.
- `timezone`: IANA timezone such as `America/New_York`; defaults to `UTC`.

Unknown parameters return `400 invalid_request`. Invalid dates and timezones return `400` with typed error codes.

Successful response shape:

```json
{
  "state": "success",
  "date": "2026-08-03",
  "timezone": "America/New_York",
  "matches": [{
    "canonicalFixtureId": "fx_0123456789abcdef01234567",
    "providerIds": {"espn": "401000001"},
    "utcDate": "2026-08-03T19:00:00Z",
    "localDate": "2026-08-03",
    "status": {"code": "scheduled", "raw": "STATUS_SCHEDULED", "completed": false},
    "homeTeam": {"canonicalId": "arsenal", "name": "Arsenal", "providerIds": {"espn": "359"}},
    "awayTeam": {"canonicalId": "chelsea", "name": "Chelsea", "providerIds": {"espn": "363"}},
    "competition": {"canonicalId": "premier-league", "name": "Premier League"},
    "score": {"winner": null, "fullTime": {"home": null, "away": null}},
    "sources": ["espn"],
    "sourceUpdatedAt": "2026-08-03T18:59:00Z",
    "broadcasts": [{"name": "USA Network", "type": "TV", "region": "US"}, {"name": "Peacock", "type": "STREAMING", "region": "US"}],
    "whereToWatch": [
      {"id": "usa-network", "displayName": "USA Network", "type": "TV", "region": "US", "regionKnown": true, "officialUrl": "https://www.usanetwork.com/", "source": "espn", "observedAt": "2026-08-03T18:59:00Z"},
      {"id": "peacock", "displayName": "Peacock", "type": "STREAMING", "region": "US", "regionKnown": true, "officialUrl": "https://www.peacocktv.com/", "observedAt": "2026-08-03T18:59:00Z"}
    ],
    "broadcastCoverage": {"status": "available", "regions": [{"region": "US", "status": "available"}], "sourceUpdatedAt": "2026-08-03T18:59:00Z"},
    "streaming": [{"displayName": "Peacock", "region": "US", "regionKnown": true, "officialUrl": "https://www.peacocktv.com/", "observedAt": "2026-08-03T18:59:00Z"}],
    "dataQuality": {"missingFields": ["referees", "aggregate"]}
  }],
  "providers": {},
  "coverage": {},
  "cache": {"status": "filled", "providers": {"espn": "filled"}},
  "lastUpdated": "2026-08-03T18:59:00Z",
  "broadcastSourceFreshness": {"status": "fresh", "updatedAt": "2026-08-03T18:59:00Z"},
  "broadcastCoverageReport": {"windowDays": 30, "thresholdPercent": 90, "regions": ["US"], "competitions": []}
}
```

`whereToWatch` is an additive, render-ready list of the fixture's reported TV
and streaming options. `type` is `TV` or `STREAMING`; provider names and
regions come from the source. `officialUrl` and `logoPath` are present only
when the provider name matches the verified local service registry. Unknown
providers remain visible by name without a guessed link. The legacy `streaming`
array remains streaming-only. When registry enrichment is enabled, every
fixture includes `whereToWatch`; an empty list means no provider row is present,
not that the fixture is unavailable on TV or online. Older payloads may omit
the field. `broadcastCoverage.status` is `available`, `confirmed_none`,
`unverified`, or `stale`; `regions` carries the same state for each known
region. `confirmed_none` is reserved for an eligible source that confirms
complete coverage. The response-level report measures source freshness and
30-day competition/region coverage; “covered” requires complete-source
evidence for at least 90% of fixtures. Official links open the provider's
website; the ESPN broadcast feed does not supply a match-specific viewing URL.
Clients may persist a region preference locally; the default is all reported
regions.

### `POST /api/internal/broadcast-refresh`

Hourly GitHub Actions refresh. Requires `Authorization: Bearer <OPS_ADMIN_TOKEN>`.
It uses the existing operations token and shared Redis cache, and returns
refresh status, source metrics, and the last observation timestamp. Provider
failure preserves the previous snapshot and reports it stale; public fixture
requests do not invoke this route. Stale/unavailable refreshes return `503`
so the scheduled workflow can report upstream refresh failures.

Valid states are `success`, `empty_confirmed`, `partial`, and `stale`. Total provider failure returns `503 provider_unavailable`; a provider-limited total failure or application burst limit returns `429 rate_limited` with `Retry-After`.

### `GET /api/v2/fixtures/{canonicalFixtureId}`

Returns a recently cached canonical fixture as `{"fixture": ...}`. Invalid IDs return `400`; expired or unknown links return `404`.

### `GET /api/v2/search`

Global search is feature-gated and enabled by default. When disabled by an
operator, the route returns `404`. It accepts
`q` (at least two characters), an optional IANA `timezone`, optional inclusive
`start` and `end` dates, and `limit`/`offset` pagination. The date window is
bounded to seven days and defaults to three days before through three days after
the current server date.

Results are typed `team`, `competition`, or `fixture` records with stable IDs.
Fixture results contain status and teams but never score fields. A provider
failure for one day preserves successful days and returns `state: "partial"`
with per-day states. The endpoint returns `404` while the `search` feature flag
### `GET /api/v2/teams/{canonicalId}/analysis`

Temporarily unavailable while Team Intelligence is disabled. The route returns the generic `404 not_found` envelope until the feature is re-enabled.

### `GET /api/v2/capabilities`

Returns typed `supported`, `unavailable`, or `not_supported` states for provider-gated features. Unsupported results contain a reason and never a synthetic `data` field.

## Health and build

- `GET /health/live`: process liveness.
- `GET /health/ready`: dependency wiring, exact build, and cache readiness/degradation.
- `GET /health/version`: version, full commit SHA, build timestamp, environment, and asset token.
- `GET /health/metrics`: in-process counters and timing aggregates; no raw requests or credentials.

## Page and export routes

- `/`, `/matches-today`: fixture dashboard.
- `/calendar`: bounded seven-day calendar.
- `/fixtures/{id}`: canonical dashboard deep-link redirect.
- `/fixtures/{id}.ics`: score-free RFC 5545 event.
- `/teams`, `/teams/{canonicalId}`: reserved Team Intelligence routes; currently return `404` while the feature is disabled.
- `/competitions/{canonicalId}`: stable competition page.
- `/league-tables`: consent-gated third-party table embed.
- `/privacy`, `/data-sources`, `/offline`: product information and offline shell.
- `/operations`: restricted read-only operations dashboard; live data requires
  the `X-Ops-Token` header through `/api/v2/operations` when configured.

Legacy `/api/competitions`, `/api/teams/{id}`, `/api/team/{id}`, `/api/team-analysis/{id}`, and `/api/matches-today` remain for compatibility; team-analysis routes currently return `404` while Team Intelligence is disabled. New clients should prefer `/api/v2` because legacy errors and provider-shaped response fields are not the canonical contract.
