# Soccer Scanner Finalization Roadmap

**Goal:** Take Soccer Scanner from its current state (P0 partially closed, branch staged, production on an older revision) to a finished, deployed, truthfully-documented product with a clean repository.

**Status at authoring:** branch `feat/deliberate-guest-mode` at `a0b8ce2`, 16 commits, CI and iOS green, staging verified at exact SHA. Production remains on `d665414`.

## Why this is a roadmap and not one plan

This covers seven independent subsystems. A single plan spanning all of them would be impossible to review and stale before it was half-executed. Each phase below produces working, shippable software on its own, has its own exit criteria, and gets its own detailed task-level plan written **immediately before execution** so it reflects reality rather than assumptions made weeks earlier.

Phase 1 is fully detailed in `2026-08-05-phase-1-provider-reliability.md`. Later phase plans are written as each phase begins.

## Sequencing rationale

Phases are ordered by *risk retired per unit of effort*, not by the original audit's numbering:

1. **Reliability first.** Production went down during verification and nothing would have alerted anyone. Shipping more features onto an unmonitored, single-provider system increases exposure.
2. **Then user-visible P0 gaps**, because they are the remaining commitments from the original brief.
3. **Then correctness, then data hardening**, which are lower-visibility but affect trust in what is shown.
4. **New surfaces after correctness**, so search and the ops dashboard are built on behaviour that is already right.
5. **Contracts and docs late**, so they describe what actually shipped.
6. **Prune and deploy last.**

---

## Phase 1 — Provider reliability and observability

**Why first:** during verification, `/api/v2/fixtures` returned `provider_unavailable` on production while `/health/ready` continued reporting `ready`. A total outage of the core product surface is currently invisible. Staging cannot serve fixtures at all.

**Scope**
- Track per-provider health and last-success time; expose it on `/health/ready` and a detailed `/health/providers`.
- Readiness reports `degraded` **without** returning 503 — a provider outage must not fail the Railway healthcheck and trigger a rollback loop.
- Scheduled synthetic monitor (GitHub Actions cron) that exercises the real fixture endpoint and fails loudly when the product is down.
- Wire and document a second provider so ESPN is not a single point of failure.
- Diagnose and fix staging's provider connectivity.

**Exit criteria**
- A production fixture outage produces a failed workflow run within 15 minutes.
- `/health/providers` shows per-provider status and last success.
- `/health/ready` never 503s solely because an upstream provider is down.
- Staging returns fixtures, or the cause is documented with evidence.

**Detailed plan:** `2026-08-05-phase-1-provider-reliability.md`

**Status (2026-08-05): tasks 1-7 implemented, one residual defect open.** All seven tasks are
committed and reviewed; CI is green; the branch is deployed to staging and the synthetic
monitor passes 4/4 there. The final whole-branch review produced 8 Important findings, all
fixed; the scoped re-review confirmed all 9 addressed but found that the fix wave itself
introduced a load-bearing regression: the new generic exception arm in
`fixture_service.py` records provider health but does not append to `failed`, so a
half-outage (one provider dead, the other legitimately empty) yields `empty_confirmed`
and the monitor reports fully green. Phase 1's exit criteria are NOT met until that is
closed and the branch is deployed to production.

---

## Phase 2 — Remaining P0 user-facing gaps

**Scope**
- **Header timezone control.** Compact control beside the score toggle: `[America/New_York · EDT] [Reveal scores]` on desktop, `[EDT] [eye]` on mobile. Searchable IANA selector, browser-zone and UTC options, offset and abbreviation shown, keyboard navigation, Escape-to-close, focus restoration, complete accessible name. Shares state with the existing filter control — one timezone value, not two.
- **Streaming discovery.** A verified registry (canonical ID, display name, aliases, official domains, official HTTPS URL, region support, attribution). Card shows `[icon] Peacock · US`; detail shows service, region, official link with safe external attributes, provider source, last-verified time, and an availability disclaimer. Unknown region labelled honestly. Generic fallback icon, no broken images. README corrected — it currently claims broadcast listings are unavailable while the UI shows them.
- **Brand and icons.** Logo mark in the header with accessible name and compact mobile treatment. Full icon suite: SVG favicon, PNG fallback, `apple-touch-icon`, PWA 192/512, maskable, raster Open Graph image. `templates/base.html`, `static/manifest.webmanifest`, `static/sw.js` updated. Reuse `clients/ios/Tools/generate_app_icon.py` so web and native icons come from one source of truth.

**Exit criteria:** audit section C rows 2, 5 and 10 move to `implemented`, with Playwright coverage for the timezone control, streaming region rendering, and icon asset availability.

---

## Phase 3 — P1 correctness

**Scope**
- **Country filter.** Add verified `competition.area` metadata or a competition registry; remove the control if neither can be sourced. An empty non-functional filter is not acceptable.
- **Browser history.** `popstate` restores selected fixture, date, timezone, search, filters, sort, mobile sheet vs desktop panel, and focus. Stop resetting `selectedFixtureId` unconditionally.
- **Standings season.** Remove hardcoded 2025/26 labels and SofaScore season IDs from `templates/league_tables.html`. External config carrying competition, active season, provider identifier, last-verified date, verification owner and fallback behaviour, plus a test that fails after an unreviewed season rollover.
- **PWA and offline.** Exclude extra-time and penalty fixtures from snapshots. Recompute state, counts, statistics, featured fixtures and snapshot timestamp after sanitization. Bound cache size and document retention.

**Exit criteria:** audit section F rows closed; offline snapshot provably excludes every active fixture.

---

## Phase 4 — Provider and data hardening

**Scope**
- **ESPN truncation.** Replace the blind `limit=500` with provider-total detection, continuation where supported, explicit suspected-truncation detection, and a typed `partial` response when complete coverage cannot be verified. Busy-date payload test.
- **One orchestration deadline.** A single request-scoped budget across the ESPN global request, ESPN metadata calls, Football-Data, retries and body streaming — not a fresh deadline per provider. Independent providers run concurrently.
- **League metadata.** Shared long-lived cache plus limited fallback metadata so a metadata failure stops discarding otherwise-usable fixtures. Cold and warm caches must return equivalent fixture sets for unchanged upstream events.
- **Team intelligence.** Typed partial states instead of empty lists, server-side analysis cache, concurrent independent requests, explicitly sorted recent and upcoming lists, `Unavailable` for missing data, estimated formation labelled as estimated, one coherent statistical sample, no Retry offered for permanently missing mappings. Expand verified mappings using the unresolved-identity report; leave ambiguous aliases unresolved.
- **Calendar.** Bounded range endpoint or optimised batched retrieval, per-day loading and error states, successful days preserved when one fails, score reveal via local rerender with zero refetches, competition and status shown, mobile-first agenda view.

**Exit criteria:** one failed day out of seven retains six; score reveal triggers zero network requests; truncation detected on a busy date.

---

## Phase 5 — New surfaces

**Scope**
- **Global search.** Dedicated API across teams, competitions, and upcoming/recent fixtures with stable IDs and aliases. Bounded date range, pagination, debouncing, typed partial states, hidden-score safety, full-screen mobile search, keyboard navigation, no provider call per keystroke. Recent searches only insofar as the guest-mode decision allows — which currently means not persisted.
- **Operations dashboard.** Protected by `OPS_ADMIN_TOKEN`. Shows provider health and latency, truncation, cache status, Redis, PostgreSQL, schema version, worker and cron state where applicable, duplicate-ID incidents, unresolved mappings, streaming-registry gaps, standings-season staleness, deployed SHA and backup age. No secrets, no complete device or user identifiers.
- **Mobile-first pass.** Design and verify from 320px through 430px plus tablet and desktop. Priority order: date, timezone, score visibility, search, fixtures, filters. Thumb-friendly navigation, safe-area support, large touch targets, no hover-only or drag-only actions, no nested scroll traps, no 10px essential metadata. Dynamic Type, Reduced Motion, Increased Contrast, screen-reader support, 200% and 400% zoom, axe scans.

**Exit criteria:** search returns results across all three entity types; ops dashboard renders live values; Playwright covers 320–430px and axe passes.

---

## Phase 6 — Contracts, documentation and marketing

**Scope**
- **`openapi/soccer-scanner-v2.yaml`** covering every endpoint that actually exists, with stable IDs, UTC timestamps, explicit timezone parameters, typed status and error codes, pagination, partial outcomes, freshness, rate-limit headers, request IDs and version compatibility. Endpoints not yet built are omitted, not speculated.
- **`docs/reliability-and-slos.md`** — measurable availability, fixture API p50/p95/p99, search and calendar latency, cache-hit rate, provider failure rate, Core Web Vitals, native launch and render targets.
- **`docs/analytics.md`** — privacy-safe approach; never record score values, tokens, full private URLs, complete device tokens, personal search text, or precise location. Consent and retention documented.
- **`docs/decisions/notifications.md`** — decide whether notifications are in scope at all. This ADR gates whether APNs is ever implemented; currently `not_applicable` because the decision does not exist.
- **`docs/seo.md`** plus canonical URLs, breadcrumbs, Open Graph, Twitter metadata, correct 404 behaviour, Search Console and Bing checklists, and structured data (`SportsEvent`, `SportsTeam`, `BreadcrumbList`, `WebSite`) that never leaks hidden scores.
- **Release governance** — `docs/versioning-and-release-management.md`, `docs/release-checklist.md`, restructured `CHANGELOG.md` with Unreleased/Added/Changed/Deprecated/Removed/Fixed/Security, semantic versioning, API/web/iOS/schema/service-worker versions, tags, branch strategy, hotfixes, migration compatibility, rollback, minimum supported native client, deprecation windows.
- **`marketing/`** workspace as specified in the brief. No unsupported claims about complete coverage, guaranteed streaming, perfect accuracy, official partnerships, real-time behaviour, or global rights.

**Exit criteria:** every documented capability is one of implemented-with-evidence, explicitly blocked with operator steps, or an accepted ADR deferral.

---

## Phase 7 — Prune, merge, deploy, verify

**Scope**
- **Dead code.** Delete `static/js/favorites.js` — verified unreferenced except for prose in `templates/terms.html`. Sweep for other orphans.
- **Working-tree artifacts.** Remove the 12 root-level screenshot PNGs and 5 accessibility markdown files. They are already git-ignored (`.gitignore:74-78`) but clutter the tree; move future evidence under `artifacts/release-evidence/<sha>/`.
- **Large binaries.** `docs/SOCCER-SCANNER-DIAGRAMS.pptx` (1.2 MB) and `.pdf` (0.7 MB) are ~33% of the 5.8 MB repository. Decide: keep, move to release assets, or Git LFS.
- **Ignore hygiene.** Confirm `test-results/`, `.playwright-mcp/`, `.pytest_cache/`, `__pycache__/`, `.worktrees/`, `clients/ios/build/` and generated `.xcodeproj` are all ignored and none are tracked.
- **Railway cleanup.** Remove orphaned staging `Postgres-IZlv` and `Redis-ZvsD` after re-verifying they are unreferenced. **Requires explicit confirmation — irreversible.**
- **Full gate run** — pytest, node module tests, `node --check`, compileall, smoke invariants, `npm audit`, `pip-audit`, Playwright Chromium and WebKit, iOS on `macos-latest`.
- **Merge to `main`**, deploy production, run exact-SHA production smoke, capture evidence under `artifacts/release-evidence/<full-sha>/`.
- **Final audit update** so `docs/audits/2026-08-04-recommendation-validation.md` matches reality.

**Exit criteria:** clean working tree, production serving the merged SHA, exact-SHA smoke green, audit matrix with no stale rows.

---

## Blocked — cannot be completed by development work

These stay `blocked` until a human acts. None are on the critical path for the phases above, but the product is not "finalized" while they are open.

| Item | Blocked on | Unblock step |
| --- | --- | --- |
| Railway backups, retention, restore rehearsal, RPO/RTO | Dashboard-only; no CLI, API or MCP surface exposes backup config | `docs/backup-and-recovery.md` — enable Daily+Weekly+Monthly on production `Postgres`, then run `scripts/verify_restore.py` against a scratch restore |
| App Store submission | Apple Developer Program enrolment and API key | `clients/ios/README.md` steps 1–5, then Actions → iOS → `beta` |
| Universal links live | `APPLE_TEAM_ID` / `APPLE_BUNDLE_ID` on the Railway `web` service | AASA route returns 404 by design until set |
| Terms of Service legal validity | Legal review of `[TO BE COMPLETED BY LEGAL OWNER]` placeholders | Complete entity, jurisdiction, liability cap, effective date |
| Second provider API key | `FOOTBALL_DATA_API_KEY` not set in either environment | Free tier at football-data.org; Phase 1 wires it, the key is yours to supply |

---

## Definition of done

- Every audit row is `implemented`, `blocked` with operator steps, or an accepted ADR deferral — none `partial` or `not_implemented`.
- Production serves the merged SHA and exact-SHA smoke passes.
- A production outage triggers an alert.
- Backend, browser, native, audit and smoke gates all green.
- Working tree clean; no dead code; no untracked clutter.
- Documentation describes only what exists.
