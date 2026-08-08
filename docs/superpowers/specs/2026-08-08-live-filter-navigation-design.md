# Live Filter Navigation Design

## Goal

Make Live a fixture status filter rather than a second top-level navigation destination.

## Context

The web application currently exposes both a top-level `Live` navigation link and an in-page `All / Live / Upcoming / Finished` status group. Both surfaces represent the same URL-backed `status=live` state. The duplicate navigation entry makes a filter look like a separate product workspace.

## Design

The primary web navigation will contain `Fixtures` and the existing external `Select XI` link, with no top-level `Live` link. The Fixtures link remains the active navigation item for every fixture view, including `/?status=live`.

The existing `status-live` button remains the single Live control. It continues to use the canonical fixture status taxonomy, writes `status=live` through the existing URL synchronization, exposes `aria-pressed`, and shares the same All/Upcoming/Finished group. The `/?status=live` URL remains valid and shareable.

This is a web information-architecture change only. The native iOS status picker and its All/Live/Upcoming/Finished behavior remain unchanged. No backend, API, dependency, or data-model changes are required.

## Accessibility and responsive behavior

Removing the duplicate link reduces navigation choices without removing access to Live. The status group remains keyboard accessible, visibly selected, and available in the responsive filter layout. The primary navigation tests will verify that Live is absent while the fixture filter tests continue to verify URL state and `aria-pressed` behavior.

## Testing

- Update browser navigation assertions to require Fixtures as the active page for both `/` and `/?status=live`.
- Add a browser assertion that the primary navigation contains no Live link.
- Preserve and run the existing URL-backed status-filter, accessibility, Chromium, and WebKit coverage.
- Run the repository release matrix and `git diff --check` before handoff.

## Scope boundaries

Do not rename the `status=live` query parameter, change filter semantics, alter refresh behavior, change native iOS UI, or add a new header toggle.
