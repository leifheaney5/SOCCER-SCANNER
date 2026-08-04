# Changelog

## 2.0.0 - 2026-08-04

### Added

- Canonical versioned fixture API with typed provider and data-quality outcomes.
- ESPN and optional Football-Data.org adapters, shared Redis cache boundary, bounded memory fallback, rate limiting, request IDs, metrics, and immutable build identity.
- Spoiler-safe responsive fixture dashboard, adaptive live refresh, match and team context, local favorites, seven-day calendar, canonical links, and score-free calendar exports.
- Source/freshness inspector, privacy and data-source pages, secure headers, metadata, PWA installability, and spoiler-sanitized offline snapshots.
- Provider capability manifest and production-grade Python, Chromium, WebKit, axe, load, visual, audit, and live-smoke workflows.

### Changed

- Replaced provider-shaped fixture rendering and ambiguous empty/error fallbacks with canonical deterministic contracts.
- Made `main` production releases verifiable through full Git SHA and build-derived asset tokens.

### Deferred

- Events, lineups, detailed match statistics, broadcast listings, and notifications require legitimate sources and, for notifications, explicit consent and delivery infrastructure.
- Football-Data.org squad and standings capabilities remain unavailable where no API key is configured.
