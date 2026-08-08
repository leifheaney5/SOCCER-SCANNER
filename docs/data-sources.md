# Data sources

## ESPN

ESPN's global soccer scoreboard is the default fixture source. For each UTC date needed to compose a visitor's local day, the adapter makes one bounded request and accepts up to 500 provider events. This avoids the former fixed 20-league shortlist, so every competition included in ESPN's global response is eligible for display. A two-day local-date window uses two single-day requests rather than a combined range, preserving the bounded 5 MB response-size guard.

The global scoreboard carries a provider league ID in each event UID but does not include the human-readable competition record. The adapter resolves one representative event summary per newly seen league, caches that provider-derived metadata for 24 hours (with a seven-day stale fallback), and reuses it across fixture fills. Resolution is bounded to eight concurrent calls. If a refresh fails, an unexpired stale entry preserves the fixture and marks the provider response partial; if no verified or stale metadata exists, the adapter omits only the unverified competition rather than inventing a label.

ESPN coverage is useful but not treated as a contractual guarantee; the UI surfaces partial, stale, and unavailable states. The provider's terms, rate limits, geographic coverage, and schemas can change.

## Football-Data.org

Football-Data.org is optional and disabled when `FOOTBALL_DATA_API_KEY` is absent. When configured, its adapter can enrich canonical fixture coverage and backs legacy team analysis plus declared squad and standings capabilities. Its provider IDs never become canonical route IDs.

## SofaScore

League tables use a SofaScore iframe only after explicit visitor activation. The embed is third-party presentation, not ingested data, not part of `/api/v2`, and not reported as a supported canonical standings capability.

## Provenance rules

Every canonical fixture retains provider IDs, a `sources` list, source update time, and explicit missing verified fields. Provider failures are categorized without exposing raw exception data. Unknown fields remain absent or null; Soccer Scanner does not infer events, lineups, statistics, broadcasts, or outcomes.

Provider terms, rate limits, geographic coverage, and schemas can change. Review provider agreements before expanding collection, caching, redistribution, or notification use.
