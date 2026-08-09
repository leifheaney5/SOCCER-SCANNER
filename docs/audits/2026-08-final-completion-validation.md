# Final completion and production-validation record

Audit date: 2026-08-08
Release candidate: `agent/final-completion-validation`
Previous deployed baseline: `7759b5dd1ec33ef7b70ab87488593ad4b4c749ba`

This record separates evidence that is available on the Windows checkout from
evidence that requires GitHub macOS CI, Railway production, Apple hardware, or
human/portal ownership. It does not treat local checks as proof of deployment
or iOS compilation.

## Requirement matrix

| Requirement | Implemented | Unit tested | Browser tested | CI verified | Production verified | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Explicit timezone formatting and selected-fixture preservation | yes | yes | yes, Chromium/WebKit | pending | pending | Includes cross-midnight date rollover, detail/source timestamps, deep links, and copied timezone state. |
| Canonical match-status labels and descriptions | yes | yes | yes, Chromium/WebKit | pending | pending | Cards and match context consume the shared status contract. |
| Streaming service icons and safe fallbacks | yes | yes | yes, Chromium/WebKit/axe | pending | pending | Registry-owned local asset metadata; verified links remain provider-owned. |
| Calendar per-day failures, retry, and score-toggle no-refetch | yes | n/a | yes, Chromium/WebKit | pending | pending | Bounded loading and stale-response protection remain in the existing calendar route. |
| Standings season rollover/review warnings | yes | yes | yes, existing standings coverage | pending | pending | No provider season IDs were invented; stale configuration is visibly withheld. |
| Concurrent providers under one shared deadline | yes | yes | n/a | pending | pending | Bounded executor, typed timeout outcomes, deterministic composition, and stale fallback. |
| Guest-only docs, SEO, route boundaries, and freshness labels | yes | yes | yes, accessibility/branding | pending | pending | No new routes or navigation; Team Intelligence remains disabled. |
| iOS source/release readiness | source checks yes | yes | n/a | pending macOS | not applicable | Windows validates assets/configuration only; Swift compile and simulator tests require macOS CI. |
| Exact deployment identity and public smoke | code ready | yes | local smoke coverage | pending | pending | Candidate must be merged, deployed, and checked against the exact full SHA. |

## Local evidence

The following checks passed against the candidate working tree:

- `python -m pytest -q` — 264 passed, 72 subtests passed.
- `python -m compileall -q app.py wsgi.py soccer_scanner` — passed.
- `npm run test:node` — passed in the full Node matrix.
- `npm run test:smoke-invariants` — 4 passed.
- `npx --no-install playwright test --project=chromium` — passed.
- `npx --no-install playwright test --project=webkit` — passed, 94 tests.
- `npm audit --audit-level=high` — 0 vulnerabilities.
- `python -m pip_audit -r requirements.txt --progress-spinner off` — no known vulnerabilities.
- JavaScript `node --check` sweep — passed.
- `python tests/test_ios_release_assets.py` — release assets validated.
- `git diff --check` — passed.

The first combined browser run exposed one stale expected label (`Live now`
versus the canonical `Live`) and then a shared-server WebKit cascade. The
expectation was corrected and the two browser projects were rerun independently;
both passed.

## Pending external evidence

- GitHub Actions must run the final pushed SHA, including the macOS iOS
  generation/build/unit/UI workflow. A Windows source check cannot prove Swift
  compilation.
- The final PR must be merged into `main` before Railway deployment is treated
  as the candidate release.
- Railway must reach terminal `SUCCESS`; `/health/version.commitSha` and
  `/health/ready.build.commitSha` must equal the merged full SHA.
- `npm run smoke:production` must pass against `https://soccerscanner.pro` with
  that exact SHA. Provider unavailability, if present, must remain reported as
  live provider state rather than being relabeled as a successful data fetch.
- Physical-device/TestFlight review, VoiceOver, Dynamic Type, safe areas,
  Universal Links, App Store Connect metadata, legal placeholders, and support
  ownership remain human/Apple gates.

## Scope controls reviewed

- No application routes or primary-navigation destinations were added.
- Team Intelligence remains disabled; dormant compatibility files were not
  expanded.
- Spoiler-safe score rendering and URL-backed guest state remain in place.
- No dependencies, secrets, provider values, fixture IDs, crest URLs, or
  standings season IDs were fabricated.
