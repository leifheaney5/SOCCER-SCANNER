# Final completion and production-validation record

Audit date: 2026-08-08
Application merge commit: `64b6a6b625ae8ef2d9fd1606c9e54565097e2b58`
Final deployed commit: `291420334bbdc830bd82ec0cb307e154c8ebfc88`
Previous deployed baseline: `7759b5dd1ec33ef7b70ab87488593ad4b4c749ba`
Railway deployment: `935f20ff-a8fd-47a1-af32-656ab1538454` (`SUCCESS`)

This record separates evidence that is available on the Windows checkout from
evidence that requires GitHub macOS CI, Railway production, Apple hardware, or
human/portal ownership. It does not treat local checks as proof of deployment
or iOS compilation.

## Requirement matrix

| Requirement | Implemented | Unit tested | Browser tested | CI verified | Production verified | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Explicit timezone formatting and selected-fixture preservation | yes | yes | yes, Chromium/WebKit | yes | partial | Local/CI browser coverage includes cross-midnight rollover; production smoke verifies the live timezone control and exact build. |
| Canonical match-status labels and descriptions | yes | yes | yes, Chromium/WebKit | yes | partial | Cards and match context consume the shared status contract; live build identity verified. |
| Streaming service icons and safe fallbacks | yes | yes | yes, Chromium/WebKit/axe | yes | yes | Production Peacock SVG returned 200; live fixture data remained provider-owned. |
| Calendar per-day failures, retry, and score-toggle no-refetch | yes | n/a | yes, Chromium/WebKit | yes | partial | Browser/CI verified; production smoke verifies the deployed asset and dashboard shell. |
| Standings season rollover/review warnings | yes | yes | yes, existing standings coverage | yes | partial | No provider season IDs were invented; stale configuration is visibly withheld. |
| Concurrent providers under one shared deadline | yes | yes | n/a | yes | partial | Bounded executor and typed outcomes are covered locally/CI; live readiness reports ESPN ok and Football-Data disabled. |
| Guest-only docs, SEO, route boundaries, and freshness labels | yes | yes | yes, accessibility/branding | yes | yes | Production smoke checks public routes/assets; `/teams` returns 404 and Team Intelligence remains disabled. |
| iOS source/release readiness | source checks yes | yes | n/a | yes, macOS | not applicable | GitHub Actions iOS run `31289973761` generated, built, and tested the simulator target. Physical-device/TestFlight remains open. |
| Exact deployment identity and public smoke | yes | yes | yes, local smoke | yes | yes | Smoke passed against `https://soccerscanner.pro` with final deployed SHA `2914203...`: 143 fixtures, 143 unique IDs. |

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

- GitHub Actions CI passed for the final pushed SHA, including macOS iOS
  generation/build/unit/UI workflow (run `31289973761`).
- The PR was merged into `main`; Railway deployment reached terminal `SUCCESS`.
- `/health/version.commitSha` and `/health/ready.build.commitSha` equal the
  final deployed full SHA `291420334bbdc830bd82ec0cb307e154c8ebfc88`.
- `npm run smoke:production` passed against `https://soccerscanner.pro` with
  that exact SHA. Live readiness reports ESPN `ok` and Football-Data `disabled`;
  no provider failure was relabeled as successful data.
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
