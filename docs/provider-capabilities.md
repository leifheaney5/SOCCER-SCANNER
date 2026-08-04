# Provider capability boundaries

Soccer Scanner treats every data surface as a declared provider capability. A feature is never populated from inference, scraped presentation markup, placeholder values, or an unrelated provider field.

The live manifest is available from `GET /api/v2/capabilities`. Each capability has one of three states:

- `supported`: a configured, legitimate provider supplies the data through an implemented adapter.
- `unavailable`: the adapter is understood, but its required provider credential is not configured in this environment.
- `not_supported`: no production adapter and legitimate source are implemented. The API returns the status and reason, never synthetic `data`.

## Current matrix

| Capability | Default production state | Legitimate prerequisite |
|---|---|---|
| Match events | `not_supported` | Contracted event feed with stable event IDs and correction semantics |
| Lineups | `not_supported` | Contracted lineup feed with confirmed/provisional state and timestamps |
| Match statistics | `not_supported` | Contracted statistics feed with metric definitions and provenance |
| Broadcasts | `not_supported` | Licensed, territory-aware broadcast listings |
| Squads | `unavailable` without key | Configured Football-Data.org credential |
| Standings | `unavailable` without key | Configured Football-Data.org credential |
| Notifications | `not_supported` | Delivery service, consent records, preferences, and verified event source |

The existing tables page gates a third-party SofaScore embed behind an explicit user action. That embed is not reported as a Soccer Scanner standings-provider capability and is not ingested into the canonical API.

## Notification architecture prerequisite

Notifications remain intentionally deferred. Enabling them requires all of the following before any push subscription is collected:

1. Explicit per-device opt-in, a documented purpose, and a reversible permission flow.
2. Server-side subscription storage with encryption, retention limits, deletion, and auditable consent timestamps.
3. Per-team and per-competition preferences plus event-type selection.
4. Quiet hours stored with an IANA timezone and deterministic daylight-saving handling.
5. A spoiler mode that suppresses score, outcome, scorer, and score-derived wording in titles, bodies, URLs, icons, and analytics properties.
6. Idempotent delivery keyed by canonical fixture and provider event IDs, with corrections and cancellations supported.
7. A legitimate, contractually permitted live-event source with freshness and outage metadata.

Until those conditions are met, `notifications` stays `not_supported`. Client favorites remain local to the browser and are not interpreted as notification consent.

## Extension rule

New capability adapters must normalize provider payloads into a typed domain contract, retain source and update timestamps, expose missing verified fields, and add contract, outage, and no-fabrication tests. A capability may move to `supported` only when its required configuration is present and the production code path is implemented.
