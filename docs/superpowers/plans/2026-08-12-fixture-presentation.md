Exit code: 0
Wall time: 0.5 seconds
Output:
# Fixture Presentation Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Soccer Scanner fixtures faster to scan and more visually competitive while preserving the existing spoiler-safe, guest-only, provider-truthful product boundaries.

**Architecture:** Keep the existing Flask/Jinja/vanilla ES-module architecture. Concentrate presentation logic in the existing fixture renderer, fixture state, templates, and fixture CSS; add only the smallest state helpers needed for date tabs and an optional verified broadcast view. Preserve the current match-context detail surface rather than duplicating all metadata into every row.

**Tech Stack:** Flask/Jinja templates, native ES modules, CSS, Node test runner, Playwright Chromium/WebKit, axe-core.

## Global Constraints

- Scope is fixture presentation only: hierarchy, grouping, density, date browsing, status visibility, venue/broadcast presentation, and fixture-row states.
- Do not add news, predictions, odds, transfers, player ratings, notifications, social features, accounts, or persistent favourites.
- Scores must remain absent from text, attributes, and the accessibility tree until the existing explicit reveal preference is true.
- Never fabricate venue, broadcast, competition, aggregate, or provider status data; omit unavailable fields.
- Do not add dependencies or modify protected CI/CD, deployment, migration, or lock files.
- Preserve the current URL-backed date, timezone, filter, and selected-fixture state.
- Every changed behavior needs focused tests plus the relevant browser assertions.

---

## File Map

- Modify `templates/matches_today.html`: add the compact date-strip presentation and the fixture-view controls without changing the existing filter dialog contract.
- Modify `static/js/fixtures.js`: synchronize date-strip selection and any new fixture-view state with the existing URL-backed state and render cycle.
- Modify `static/js/fixture-state.js`: expose deterministic helpers for date-tab labels/counts and the verified broadcast-only selection.
- Modify `static/js/fixture-renderer.js`: render denser rows, clearer status/competition hierarchy, inline optional venue and broadcast metadata, and special match-state annotations.
- Modify `static/css/fixtures.css`: implement the desktop/mobile grid, date strip, stronger live/state treatments, competition headers, and compact metadata layout.
- Modify `static/js/calendar.js` only if the shared renderer or date-state helper requires the calendar view to remain behaviorally consistent.
- Modify existing fixture Node tests under `tests/` and browser specs under `tests/browser/`; create no new test framework or fixture data source.
- Update `CHANGELOG.md` only after implementation, under the next unreleased/working version section already used by the repository.

### Task 1: Establish presentation contracts with tests

**Files:**
- Modify: `tests/*.test.mjs` (the existing fixture renderer/state test files discovered before implementation)
- Modify: `tests/browser/*.spec.js` (the existing fixture dashboard spec)

**Interfaces:**
- Consumes: current fixture payload shape, current fixture URL state, and current renderer exports.
- Produces: failing tests that define row density structure, date-strip behavior, optional metadata omission, live/special-state presentation, and spoiler safety.

- [ ] **Step 1: Locate the existing focused tests before editing implementation.**

  Run:

  ```powershell
  rg -n "fixture-renderer|fixtures|score|calendar|broadcast|venue|status" tests
  ```

  Expected: identify the existing Node and browser tests to extend rather than create duplicate harnesses.

- [ ] **Step 2: Add failing Node assertions for pure presentation helpers.**

  Cover these exact contracts:

  ```javascript
  assert.deepEqual(buildDateTabs('2026-08-12', matchesByDate), [
      {date: '2026-08-11', label: 'Yesterday'},
      {date: '2026-08-12', label: 'Today'},
      {date: '2026-08-13', label: 'Tomorrow'},
  ]);
  assert.equal(matchesForBroadcastView(match), true);
  assert.equal(matchesForBroadcastView({...match, streaming: []}), false);
  ```

  Also assert that missing venue, missing broadcast, missing aggregate metadata, and unknown special statuses produce no empty placeholder text.

- [ ] **Step 3: Add failing browser assertions for the visible dashboard.**

  Assert that the fixture page has a date strip, compact fixture rows with stable kickoff/team/result regions, visible competition headings, a clearly distinguishable live row, and no score text in the default hidden-score state.

- [ ] **Step 4: Run the focused tests and record the expected failures.**

  ```powershell
  npm run test:smoke-invariants
  npx playwright test tests/browser --project=chromium
  ```

  Expected: new assertions fail because the contracts do not yet exist; existing tests must remain green unless they assert the old presentation structure directly.

### Task 2: Add compact date navigation

**Files:**
- Modify: `templates/matches_today.html`
- Modify: `static/js/fixtures.js`
- Modify: `static/js/fixture-state.js`
- Modify: `static/css/fixtures.css`
- Test: existing Node and browser tests from Task 1

**Interfaces:**
- Consumes: current selected date and URL synchronization functions.
- Produces: `buildDateTabs(selectedDate, availableDates)` and a date-strip control whose buttons select a date through the existing request path.

- [ ] **Step 1: Implement `buildDateTabs(selectedDate, availableDates)` in `static/js/fixture-state.js`.**

  Return a stable ordered array for the selected date plus adjacent dates available in the current seven-day browsing window. Each item must contain `date`, `label`, `shortLabel`, and `matchCount`; use `Today`, `Tomorrow`, and `Yesterday` only when those relative dates apply, otherwise use a localized short weekday/date label.

- [ ] **Step 2: Add the date-strip markup in `templates/matches_today.html`.**

  Use a `nav` with one button per tab, `aria-current="date"` for the selected tab, and an accessible label such as `Browse fixture dates`. Keep the existing date input and previous/next buttons as fallback controls.

- [ ] **Step 3: Wire date-strip clicks through the existing date selection path.**

  Do not introduce a second fetch implementation. Update the URL-backed date, refresh the fixture request, and preserve timezone/filter state exactly as the existing date controls do.

- [ ] **Step 4: Style the strip for horizontal scanning and mobile overflow.**

  Use a compact horizontal row with an obvious selected state, match counts, keyboard focus, and touch targets of at least 44px. On narrow screens allow horizontal scrolling without wrapping the dashboard.

- [ ] **Step 5: Run focused tests.**

  ```powershell
  npm run test:smoke-invariants
  npx playwright test tests/browser --project=chromium --project=webkit
  ```

  Expected: date tab helper, URL state, keyboard access, and mobile overflow assertions pass.

### Task 3: Redesign fixture rows for scan density and status hierarchy

**Files:**
- Modify: `static/js/fixture-renderer.js`
- Modify: `static/css/fixtures.css`
- Test: Node renderer tests and browser fixture dashboard tests

**Interfaces:**
- Consumes: existing canonical fixture fields and `statusKind`/`statusLabel` helpers.
- Produces: a stable fixture row structure with status/kickoff, aligned teams, score-or-kickoff, optional metadata, and details action.

- [ ] **Step 1: Change the row markup to explicit presentation regions.**

  Render one card with these regions in this order: `fixture-status`, `fixture-teams`, `fixture-result`, `fixture-meta`, and `fixture-action`. Keep team crests and names, but use the result region as the fixed visual anchor for kickoff, hidden score, live score, or final score.

- [ ] **Step 2: Make live, upcoming, finished, and exceptional states visually distinct.**

  Add state classes and accessible labels without placing hidden scores into attributes. Live rows must expose current status/minute only when provider data supplies it; postponed/canceled/delayed/abandoned rows must display their canonical status rather than pretending to be upcoming or finished.

- [ ] **Step 3: Preserve spoiler safety while improving revealed-score emphasis.**

  Continue using `createScoreNode(match, revealed)`. Improve only the visible revealed state and layout; the hidden branch must remain a non-score label with no score-bearing DOM content.

- [ ] **Step 4: Add optional special-match annotations.**

  Render provider-supplied leg/aggregate context only when present, using compact secondary text. Do not calculate aggregate scores in the browser and do not show empty labels.

- [ ] **Step 5: Update CSS for dense desktop rows and readable mobile rows.**

  Use a consistent grid for status, teams, result, metadata, and action. Reduce unnecessary card height, retain 44px action targets, prevent long team names from shifting the result column, and keep mobile rows stacked in a predictable order.

- [ ] **Step 6: Run renderer and browser tests.**

  ```powershell
  npm run test:smoke-invariants
  npx playwright test tests/browser --project=chromium --project=webkit
  ```

  Expected: fixture ordering, hidden-score assertions, live/special status assertions, and responsive layout checks pass.

### Task 4: Strengthen competition grouping and optional inline context

**Files:**
- Modify: `static/js/fixture-renderer.js`
- Modify: `static/css/fixtures.css`
- Test: Node renderer tests and browser fixture dashboard tests

**Interfaces:**
- Consumes: existing competition identity, area, venue, and verified streaming fields.
- Produces: stronger competition headers and compact optional venue/broadcast metadata.

- [ ] **Step 1: Improve competition header hierarchy.**

  Keep the existing competition emblem fallback and name. Add a visually stronger header boundary, area/country context when supplied, match count, and the existing expand/collapse control. Do not add invented flags or competition logos.

- [ ] **Step 2: Render optional venue/location metadata in the row.**

  Show a concise location only when the provider supplies it. Truncate visually, preserve the full value in an accessible label, and omit the element entirely when absent.

- [ ] **Step 3: Add an `On TV` presentation filter using verified broadcasts only.**

  Reuse the existing streaming registry data. The filter must include a match only when at least one verified streaming service exists; legacy unverified names may remain visible in their current fallback presentation but must not qualify a match for the new filter.

- [ ] **Step 4: Add compact broadcast badges without guessed links or regions.**

  Preserve the existing official URL and region rules. Use one concise service summary in the row and expose the complete verified service list through the existing detail/context surface.

- [ ] **Step 5: Test omission and filter behavior.**

  Assert that missing venue/broadcast produces no placeholder, verified broadcasts qualify for `On TV`, unverified legacy names do not, and score hiding remains intact in both normal and filtered views.

### Task 5: Verify visual quality, accessibility, and documentation

**Files:**
- Modify: `tests/browser/*.spec.js` if final responsive/accessibility coverage needs refinement
- Modify: `CHANGELOG.md`
- Review: `docs/testing.md`

**Interfaces:**
- Consumes: completed date strip, row renderer, grouping, metadata, and filters.
- Produces: verified fixture-presentation release candidate with documented behavior.

- [ ] **Step 1: Run the full local release matrix.**

  ```powershell
  $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
  python -m pytest -q
  python -m compileall -q app.py wsgi.py soccer_scanner
  Get-ChildItem static,tests -Recurse -File -Include *.js,*.mjs | ForEach-Object { node --check $_.FullName }
  npm run test:smoke-invariants
  npm audit --audit-level=high
  pip-audit -r requirements.txt
  npx playwright test --project=chromium --project=webkit
  git diff --check
  ```

- [ ] **Step 2: Review browser states at desktop and mobile widths.**

  Verify at minimum: many competitions, long team names, live match, finished match with scores hidden/revealed, postponed match, missing venue, verified broadcast, no broadcast, empty date, filtered empty state, and narrow viewport date-strip overflow.

- [ ] **Step 3: Run accessibility checks.**

  Confirm focus order, button names, selected date semantics, status announcements, no horizontal page overflow, and no serious/critical axe violations.

- [ ] **Step 4: Review the diff and update the changelog.**

  Ensure only fixture-presentation files changed, no dependency or protected-file changes were introduced, and document the user-visible presentation improvements without claiming deployment.

- [ ] **Step 5: Stop at a clean implementation handoff.**

  Report exact test commands/results and leave commit, push, merge, and deployment decisions to the user’s explicit instruction.

## Self-Review Checklist

- The plan covers all agreed priorities: density, live hierarchy, date browsing, competition hierarchy, venue, broadcast view, and special states.
- It preserves the explicit exclusions: news, odds, predictions, transfers, notifications, accounts, and persistent favourites.
- It keeps spoiler safety and provider truthfulness as non-negotiable constraints.
- It reuses existing architecture and tests instead of adding dependencies or creating a new rendering system.
- It does not authorize deployment, publishing, or production verification.


