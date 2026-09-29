# Soccer Radar Rebrand and Canonical Domain Migration

**Status:** Approved by owner on 2026-09-28

**Scope update (2026-09-29):** Add a per-fixture “Where to watch” listing for
provider-reported TV and streaming options, including verified service links.

## Goal

Carry the approved initial-fixture-load fix into one coherent Soccer Radar release, with `https://soccer-radar.com` as the canonical public website.

## Current state

- The fixture-load fix is commit `1fa66f5` on `fix/initial-fixture-load-retry`; hosted CI passed for that commit.
- Production Railway project `soccer-scanner`, service `web`, currently has the active custom domain `soccerscanner.pro` on port `8080` and deploys from `main`.
- `soccer-radar.com` resolved in public DNS on 2026-09-28, but it is not currently attached as a Railway domain. DNS resolution alone does not confirm that its records point to the Railway target.
- The current brand appears in web templates, metadata, PWA and favicon labels, iOS display and store metadata, website links, Universal Link configuration, monitoring defaults, tests, and operational documentation.

## Proposed scope

1. Use **Soccer Radar** for customer-facing web and native iOS names, web page titles and descriptions, structured metadata, PWA labels, accessibility labels, and current store metadata.
2. Use `https://soccer-radar.com` as the web canonical origin in `PUBLIC_BASE_URL`, canonical and social URLs, sitemap/robots output, fixture calendar URLs, native production API/site links, and synthetic-monitor defaults.
3. Add the new host to iOS Universal Link configuration and AASA responses while retaining `soccerscanner.pro` support for links already shared and for installed app versions.
4. Keep `soccerscanner.pro` active and redirect public content requests to the matching path and query on `soccer-radar.com`. Serve `/.well-known/apple-app-site-association` directly from both hosts because Apple requires an unredirected AASA response. This preserves existing links and consolidates search indexing. Remove the old host only in a later, separately reviewed retirement.
5. Keep repository, package, bundle, database, cache, service, and persisted browser-storage identifiers stable. The rebrand requires no data migration. The API may gain a backward-compatible `whereToWatch` field to expose provider-reported TV and streaming options while preserving the existing `streaming` field and its meaning.
6. Preserve the existing visual system and app icon geometry. Replace textual brand references; do not introduce a new logo or visual redesign without approved assets.
7. Update current operating and release documentation. Leave historical audits, release evidence, and dated plans as historical records.
8. Include fixture-load retry and unavailable-state behavior in this same release. Do not submit an iOS App Store/TestFlight build as part of the web deployment.

## Rollout design

1. Confirm the Railway-provided DNS record for the new hostname and verify that the owner-controlled DNS points to it.
2. Attach `soccer-radar.com` to the existing production `web` service and verify TLS while `soccerscanner.pro` remains active.
3. Update application canonical-origin configuration and host-based redirect behavior, then update web and iOS source, metadata, monitoring, tests, and current documentation.
4. Verify both hosts: the new host serves canonical content; the old host preserves routes and query strings while redirecting content to the new host; both hosts serve AASA directly; fixture deep links still open in existing and updated iOS configurations.
5. Run the repository release matrix and the macOS iOS workflow for the candidate commit. The iOS workflow proves compilation and tests; store submission remains a separate human-controlled release.
6. Merge the coherent branch, wait for the exact Railway production deployment to reach `SUCCESS`, then verify its full commit SHA, readiness, canonical site metadata, redirects, and production smoke.

## Acceptance criteria

- Customer-facing product name is Soccer Radar across the web and native app source and metadata.
- `soccer-radar.com` is the canonical origin in HTML metadata, JSON-LD, sitemap, robots output, fixture calendar links, monitoring, and native production links.
- AASA and the native deep-link parser accept both owned domains; both AASA endpoints return directly without redirect, and existing `soccerscanner.pro` fixture links continue working.
- Every fixture presents a “Where to watch” state. Provider-reported TV and streaming options remain distinct, show provider names and region only when supplied, use official links only from the verified service registry, and expose a truthful no-listing state when the source omits broadcast data. Existing streaming-only clients and filters remain compatible.
- Content requests to `soccerscanner.pro` preserve route and query while redirecting to the corresponding `soccer-radar.com` URL.
- Repository, package, bundle, API, database, cache, and storage identifiers remain unchanged.
- Release checks pass, including hosted browser CI and the macOS iOS workflow for the candidate SHA.
- Railway reports `SUCCESS` for the exact merged SHA; public production health and smoke checks report that same SHA and production environment.

## Risks and boundaries

- The new domain currently resolves, but its live DNS target and ownership must be checked against Railway's required record before production cutover.
- Canonical-origin changes and custom-domain attachment affect production traffic and search indexing; keep the old host active throughout verification.
- iOS associated-domain changes require an app rebuild for the new association to reach installed clients. Existing versions remain supported through the old host.
- Provider schedules may omit broadcast data. Show a clear “listing not provided” state rather than inferring availability; link only registry-verified official service URLs. Keep unrecognized names visible without links.
- Changing the canonical domain does not migrate browser-local/session storage between hosts; the app has no server-side user profile to migrate.
- Do not change Railway infrastructure, DNS, App Store Connect metadata, signing, or publish an iOS build until that specific release step is authorized and its prerequisites are verified.

## Review questions

- Confirm the proposed all-platform scope: web and iOS user-facing names, metadata, and links.
- Confirm keeping `soccerscanner.pro` as a route-preserving redirect and as a supported Universal Link host.
- Confirm the new domain is intended to become production canonical once Railway supplies and verifies its DNS target.
