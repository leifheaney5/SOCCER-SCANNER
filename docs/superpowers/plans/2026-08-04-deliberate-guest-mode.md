# Deliberate guest mode implementation plan

**Goal:** Remove the unsupported account-like persistence surface and make every guest preference truthful, spoiler-safe, and web/iOS compatible.

**Decision:** Follow `docs/decisions/accounts-and-preferences.md`: no accounts in this release, no persistent favorites, URL-backed navigation state, and session-only score visibility.

## Task 1: Lock the guest contract in tests

- Replace favorite-persistence browser tests with assertions that favorite navigation, buttons, filters, and data controls are absent.
- Assert legacy `localStorage` preferences are ignored.
- Assert score visibility writes only to `sessionStorage` and remains hidden by default in a new session.
- Update server-rendered navigation/privacy assertions.

## Task 2: Remove favorite behavior from the active client

- Remove the favorites module from fixture-page startup.
- Remove favorite URL state, filtering, ranking, rendering, event handlers, and import/export behavior.
- Remove favorite navigation and controls from templates.
- Keep deterministic recommended ranking without visitor-specific inputs.

## Task 3: Make spoiler preference session-scoped

- Change score-preference defaults to `sessionStorage`.
- Use the same behavior on fixture and calendar pages.
- Do not read or migrate legacy local-storage values automatically.

## Task 4: Align privacy, architecture, and verification

- Update privacy and architecture documentation.
- Run Python, JavaScript, Chromium, WebKit, accessibility, audit, and smoke-invariant gates.
- Stage, smoke, and verify the exact commit before production promotion.
