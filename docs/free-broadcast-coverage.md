# Free broadcast coverage

Soccer Scanner uses only free, lawful, and verifiable broadcast information.
The application does not host streams, bypass regional restrictions, or infer a
broadcaster from a competition-wide rights deal.

## Current automatic source

| Source | Coverage | Link type | Status |
| --- | --- | --- | --- |
| ESPN fixture broadcasts | Only when ESPN reports a streaming entry for the fixture | Verified service homepage from the streaming registry | Active |
| Official competition listings | Inventory for future fixture-level adapters | Source-specific, after verification | Inventory |
| UEFA match calendar and where-to-watch listings | Competition-level inventory for future fixture-level adapters | Source-specific, after verification | Inventory |
| FIFA+ live football | Competition-level inventory; availability may vary by territory | Source-specific, after verification | Inventory |
| Concacaf where-to-watch listings | Competition-level inventory for future fixture-level adapters | Source-specific, after verification | Inventory |

ESPN data is the baseline. Missing broadcast data is rendered as missing data;
it is never replaced with a guessed service or URL.

The application registry lives in
[`soccer_scanner/data/broadcast-sources.json`](../soccer_scanner/data/broadcast-sources.json).
An entry marked `inventory` is not used to enrich fixtures; it records a source
that still needs a real adapter and matching evidence.

The current UEFA and Concacaf pages expose competition or tournament-level
territory guidance rather than a stable fixture-by-fixture listing feed. That
is useful discovery data, but it does not satisfy the admission contract by
itself and remains inventory-only until an official fixture listing or
machine-readable feed becomes available.

## Source admission contract

Each additional free source must provide, or allow us to verify, all of the
following:

- a stable official source URL;
- fixture identity using competition, teams, date, and kickoff;
- broadcaster or platform name;
- territory or an explicit unknown value;
- an official destination URL, or a verified registry mapping;
- an observation timestamp;
- a lawful access path that does not require bypassing a paywall or access control.

Competition-wide mappings are not sufficient on their own. A source must be
able to establish that the broadcaster applies to the individual fixture.

The reusable `OfficialBroadcastAdapter` now enforces this contract for fetched
official listings: exactly one canonical fixture must match, the source must
be configured, and any linked destination must be HTTPS on a source-declared
domain. Missing links remain display-only; multiple matches are marked
`ambiguous` and never become public links.

Its observation mode returns the normalized records and the required coverage
metrics (`observed`, `matched`, `verifiedLinks`, `regionKnown`, `stale`,
`unmatched`, and `ambiguous`) so a source can be monitored before promotion.
`BroadcastCoverageService` applies only `verified` records to fixture streaming
metadata and leaves the input fixtures unchanged; all other observations remain
available as diagnostics.

## Rollout order

1. Inventory official league, federation, club, university, conference, and
   broadcaster pages with publicly visible fixture-level listings.
2. Prioritize sources by fixture volume, geographic coverage, stability, and
   clarity of match identity.
3. Add one adapter at a time with fixture matching, link validation, region,
   logo, freshness, malformed-data, and no-fabrication tests.
4. Run each adapter in observation mode before allowing it to enrich the public
   fixture response.
5. Promote an adapter only when its match-linking and freshness metrics remain
   within the documented threshold for a full observation period.

## Required normalized record

```json
{
  "fixtureKey": "provider-qualified fixture identity",
  "displayName": "Official broadcaster name",
  "region": "US",
  "regionKnown": true,
  "officialUrl": "https://official.example/",
  "logoPath": "/static/icons/streaming/example.svg",
  "source": "official-source-id",
  "observedAt": "2026-08-12T00:00:00Z",
  "status": "verified"
}
```

`officialUrl` must be HTTPS and belong to the verified service registry. A
source may produce a display-only entry when the broadcaster is known but its
official destination cannot be verified; that entry must not become a link.

## Coverage metrics

Every adapter must report:

- fixtures observed;
- fixtures matched to canonical IDs;
- verified links produced;
- region-known percentage;
- stale or expired records;
- unmatched and ambiguous records.

An adapter is not considered a coverage improvement if it increases listing
count by lowering match confidence or link safety.
