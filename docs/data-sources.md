# Data sources

## ESPN

ESPN's scoreboard endpoints are the default fixture source. The adapter uses a fixed allowlist of competition slugs, bounded concurrent requests, response-size limits, retries, and a shared deadline. It normalizes provider-specific states, identities, kickoff, scores, venue, season, and source update time. ESPN coverage is useful but not treated as a contractual guarantee; the UI surfaces partial, stale, and unavailable states.

## Football-Data.org

Football-Data.org is optional and disabled when `FOOTBALL_DATA_API_KEY` is absent. When configured, its adapter can enrich canonical fixture coverage and backs legacy team analysis plus declared squad and standings capabilities. Its provider IDs never become canonical route IDs.

## SofaScore

League tables use a SofaScore iframe only after explicit visitor activation. The embed is third-party presentation, not ingested data, not part of `/api/v2`, and not reported as a supported canonical standings capability.

## Provenance rules

Every canonical fixture retains provider IDs, a `sources` list, source update time, and explicit missing verified fields. Provider failures are categorized without exposing raw exception data. Unknown fields remain absent or null; Soccer Scanner does not infer events, lineups, statistics, broadcasts, or outcomes.

Provider terms, rate limits, geographic coverage, and schemas can change. Review provider agreements before expanding collection, caching, redistribution, or notification use.
