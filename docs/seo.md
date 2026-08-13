# SEO and structured data

Soccer Scanner publishes crawl-safe discovery metadata without exposing
spoiler-sensitive fixture results.

## Current implementation

- Public HTML pages have canonical URLs, Open Graph metadata, Twitter card
  metadata, and a production-only sitemap/robots policy.
- The shared layout emits `WebSite` and `BreadcrumbList` JSON-LD.
- Fixture data is loaded client-side, so scores and live match state are not
  included in crawlable metadata.
- Operations, offline, APIs, health endpoints, and other non-discovery
  surfaces remain excluded from indexing.

## Guardrails

- Do not add `SportsEvent` JSON-LD until a server-rendered fixture payload can
  be emitted without violating the spoiler contract.
- Never put scores, hidden-score state, personal search text, tokens, or
  private fixture URLs in metadata.
- Keep staging and non-production deployments disallowed in `robots.txt`.

## Verification

The application tests assert canonical/Open Graph/Twitter metadata and verify
that the shared discovery block does not contain score data. Sitemap and
robots behavior are covered by the public-route tests and production smoke
checks.
