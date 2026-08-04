# Architecture

## Request and data flow

```text
Browser store and views
        |
        v
Flask pages + /api/v2 contract
        |
        v
CanonicalFixtureService
   |       |        |        |
   |       |        |        +-- PostgreSQL fixture identity and alias registry
   |       |        +----------- canonical identity, field-level merge, local-date filter
   |       +-------------------- Redis or bounded memory cache with single-flight fills
   +---------------------------- ESPN and optional Football-Data.org adapters
```

The HTML shell is server rendered. Page behavior is split into cacheable JavaScript modules: URL/store coordination, fixture state and ranking, spoiler preference, rendering, adaptive refresh, match context, team drawer, favorites, calendar, dialogs, and PWA registration. Desktop and mobile use the same state; match context becomes a modal sheet below the desktop breakpoint.

## Canonical fixture contract

Provider adapters return camelCase normalized fixtures with explicit provider IDs and timestamps. The identity layer never merges conflicting event IDs from the same provider. Cross-provider records merge only when canonical competition, home team, away team, season/stage constraints, and kickoff within ten minutes agree. New public IDs are provider-qualified SHA-256 digests that exclude kickoff, and PostgreSQL retains provider aliases plus superseded public aliases so schedule corrections do not break links.

Field selection is deterministic. Team and competition identity favors the maintained provider map; source freshness selects current status and optional fields; score selection requires an actual provider value. Every merged fixture retains `sources`, `sourceUpdatedAt`, `providerIds`, and `dataQuality.missingFields`.

## Provider outcomes

The orchestrator distinguishes `success`, `empty_confirmed`, `partial`, `stale`, `rate_limited`, and `provider_unavailable`. It never converts an outage into an empty schedule. Providers have connection/read timeouts, bounded retry and response size, pooled sessions, and a shared request deadline. Source coverage and non-sensitive failure categories are returned and measured.

## Cache and concurrency

Provider-range payloads are cached before timezone-specific composition, so compatible timezone requests reuse upstream work. Fresh and stale windows are distinct. Per-key single-flight prevents request storms while unrelated keys fill concurrently.

`REDIS_URL` selects Redis for cross-worker storage and distributed locking. Redis failures fall back to bounded in-process memory for requests, but production readiness fails until shared Redis is healthy. Fixture deep links resolve durable public aliases and can refresh a bounded three-day window around the persisted kickoff after cache loss.

Every composed response passes a public-ID uniqueness invariant before fixture-lookup cache writes. A duplicate or missing ID fails the request rather than overwriting another fixture.

## Spoiler boundary

Scores default hidden and are not placed in text, attributes, or the accessibility tree until the global reveal preference is true. The rule covers cards, featured fixtures, context, calendar, and team history. `.ics` output never includes scores. The service worker sanitizes cached fixture payloads recursively and excludes live fixtures; offline snapshots are always labeled stale/partial/offline.

## Security and privacy

- The application trusts only a configured number of proxy hops and derives canonical links from `PUBLIC_BASE_URL`, not an arbitrary Host header.
- Production HTTPS responses receive HSTS. CSP denies objects and external framing except the explicitly gated SofaScore iframe.
- API responses use `Cache-Control: no-store`; static assets carry build-derived query tokens.
- Request IDs are validated or generated and safe error envelopes do not expose provider exception text.
- There is no account database. Favorites and score preference stay in local storage and can be cleared by the visitor.

## Build and operations

`soccer_scanner/version.py` owns the semantic application version. Production startup requires `GIT_COMMIT_SHA` or Railway's commit SHA. `/health/version` and `/health/ready` expose the exact build, while all first-party CSS and JavaScript entry assets use the first 12 SHA characters.

Gunicorn serves `wsgi:app`. Railway runs `alembic upgrade head` once in pre-deploy, then gates traffic on database/schema and Redis readiness. Release completion requires a terminal platform success plus exact-SHA public smoke, not just a pushed commit. See [Railway architecture](railway-architecture.md).

## Intentional boundaries

No data is fabricated for events, lineups, match statistics, broadcasts, squads, standings, or notifications. Their typed runtime states and prerequisites are documented in [provider capabilities](provider-capabilities.md). SofaScore tables remain an explicit third-party embed and are not ingested into the canonical API.
