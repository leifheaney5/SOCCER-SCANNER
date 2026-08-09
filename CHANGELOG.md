# Changelog

## Unreleased

### Added

- Native SwiftUI fixture navigation, local filtering, spoiler-safe detail/settings
  surfaces, route-driven fixture
  Universal Links, adaptive accessibility-size rows, and TestFlight release
  metadata.
- App Store submission lanes now stop before building when legal Terms
  placeholders or a verified support URL are still missing.
- Submission preflight also runs the shared repository release-asset validator,
  preventing manual lanes from bypassing metadata and CI-contract checks.
- Signed archive lanes now fail before building when Apple identifiers, App
  Store Connect credentials, or the numeric build number are missing; simulator
  tests remain explicitly signing-free.
- Mobile fixture filter sheets, safe-area handling, focus management, 200%/400%
  reflow coverage, release asset/CI validation, beta-note lane wiring, and
  stable WebKit match-sheet focus restoration.

### Changed

- ESPN team normalization now preserves official crests from both singular and
  collection-based provider logo fields, with ESPN's official default team logo
  when no crest exists. Team Intelligence is temporarily disabled across web,
  native, and API entry points.
- Competition group headers now preserve official provider emblems and use the
  friendly-category mark when a friendly competition has no supplied emblem.
- Live is now represented by the fixture status filter rather than a duplicate
  top-level navigation destination.
- Increased the bounded ESPN provider response guard to 5 MB so current global
  scoreboard payloads are accepted without removing response-size protection.
- Provider fan-out now shares one request budget, and stale ESPN metadata preserves
  usable fixtures while reporting a partial outcome.
- The privacy page now documents native iOS score-preference, request-ID, and
  analytics behavior; the native app root explicitly imports the Observation
  module required by its observable composition root.
- iOS CI now selects simulators using numeric runtime versions through a tested,
  dependency-free helper instead of lexicographic inline parsing.
- iOS CI now also runs when its shared release validator or Terms preflight input
  changes, keeping release-gate edits from bypassing macOS verification.
- Generated Xcode projects/user state are ignored, iOS workflow permissions are
  read-only, and CI jobs have explicit timeouts.
- Native fixture detail now shares score visibility with the list and exposes an
  explicit reveal/hide control without weakening the launch-hidden default.
- Native fixture detail now preserves every provider-reported broadcast entry,
  labels streaming versus broadcast listings, and shows supplied regions without
  implying availability.

## 2.0.0 - 2026-08-04

### Added

- Canonical versioned fixture API with typed provider and data-quality outcomes.
- ESPN and optional Football-Data.org adapters, shared Redis cache boundary, bounded memory fallback, rate limiting, request IDs, metrics, and immutable build identity.
- Spoiler-safe responsive fixture dashboard, adaptive live refresh, match and team context, local favorites, seven-day calendar, canonical links, and score-free calendar exports.
- Source/freshness inspector, privacy and data-source pages, secure headers, metadata, PWA installability, and spoiler-sanitized offline snapshots.
- Provider capability manifest and production-grade Python, Chromium, WebKit, axe, load, visual, audit, and live-smoke workflows.
- Durable PostgreSQL fixture identity/provider-alias registry with Alembic migration, stable kickoff-independent public IDs, alias-preserving deep links, and protected unresolved-mapping diagnostics.
- Dependency-aware production readiness and explicit Railway migration, start, health-check, restart, backup, and recovery operations.

### Changed

- Replaced provider-shaped fixture rendering and ambiguous empty/error fallbacks with canonical deterministic contracts.
- Made `main` production releases verifiable through full Git SHA and build-derived asset tokens.
- Prevented conflicting same-provider events and duplicate public fixture IDs from merging or overwriting fixture lookup entries.

### Deferred

- Events, lineups, detailed match statistics, broadcast listings, and notifications require legitimate sources and, for notifications, explicit consent and delivery infrastructure.
- Football-Data.org squad and standings capabilities remain unavailable where no API key is configured.
