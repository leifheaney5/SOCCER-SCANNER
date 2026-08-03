# Soccer Scanner Fixtures Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the complete spoiler-safe, crest-rich, accessible Soccer Scanner fixtures dashboard defined in `docs/superpowers/specs/2026-08-03-fixtures-dashboard-design.md`.

**Architecture:** Keep Flask/Jinja and the existing JSON contracts. A small controller coordinates URL-backed state, cancellable fixture loading, pure filtering/grouping, DOM-node rendering, responsive match context, and a lazy cached team drawer; the score preference is a shared dependency so every score-bearing renderer follows one privacy rule.

**Tech Stack:** Flask 3.1, Jinja, vanilla ES modules, CSS custom properties, Python unittest/pytest, Playwright browser tests.

## Global Constraints

- Preserve `/`, `/matches-today`, `/teams`, `/league-tables`, all current `/api/*` routes, Football-data.org/ESPN integrations, caching, and team analysis.
- Do not add React, Vue, Next.js, another frontend framework, an icon library, or an animation library.
- Default `soccer-scanner:reveal-scores` to false through one exported constant.
- While hidden, actual score values must not exist anywhere in DOM text, attributes, accessible names, titles, tooltips, or hidden regions.
- Build provider-derived UI with DOM nodes and `textContent`; do not interpolate provider data into HTML.
- Use true black `#000000`, the supplied layered surfaces, Inter, IBM Plex Mono, restricted Orbitron branding, and `#7cff00` interaction lime.
- Use 44 px mobile touch targets, visible focus, semantic controls, native dialogs, focus restoration, Escape close, reduced-motion support, and safe-area insets.
- Verify 320, 375, 430, 768, 1024, 1280, and 1440 px widths without horizontal overflow.
- Run Python tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

---

### Task 1: Add the browser-test harness and semantic dashboard shell

**Files:**
- Create: `package.json`
- Create: `playwright.config.js`
- Create: `tests/browser/fixtures-dashboard.spec.js`
- Modify: `tests/test_app.py`
- Modify: `templates/base.html`
- Replace: `templates/matches_today.html`

**Interfaces:**
- Produces shell IDs `dashboard-date`, `previous-date`, `today-date`, `next-date`, `fixture-search`, `clear-search`, `competition-filter`, `status-all`, `status-live`, `status-upcoming`, `status-finished`, `clear-filters`, `filter-toggle`, `score-toggle`, `dashboard-status`, `daily-summary`, `data-notice`, `featured-match`, `fixture-stream`, `match-context`, `match-context-dialog`, and `team-drawer`.
- Browser tests start `python app.py` on port 5100 and intercept only `/api/matches-today*` and `/api/team-analysis/*`.

- [ ] Extend `test_fixture_dashboard_is_home_page` to require the summary, score toggle, stream, context, two labelled dialogs, active Fixtures navigation, and Select XI external link while rejecting a permanent left rail.
- [ ] Add a Playwright smoke test that requires the heading, toolbar, `Reveal scores` pressed button, and six fixture-shaped skeleton rows on the first paint.
- [ ] Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_app.py -q` and `npx playwright test --grep "semantic shell"`; confirm failure because the new shell is absent.
- [ ] Add `@playwright/test` as a development dependency, configure the Flask web server, and replace the template with the semantic shell. Update the base header to load Inter, IBM Plex Mono, and Orbitron, include the compact external Select XI link, and keep the existing CSP-safe external assets.
- [ ] Run the focused Python and Playwright tests; confirm both pass.
- [ ] Commit with `git commit -m "feat: establish fixtures dashboard shell"`.

### Task 2: Implement URL-backed state and the score preference

**Files:**
- Create: `static/js/fixture-state.js`
- Create: `static/js/score-preference.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- `fixture-state.js` exports `todayLocal()`, `shiftDate(date, amount)`, `statusKind(match)`, `createState(search)`, `filterMatches(matches, state)`, `groupMatches(matches)`, `summarizeMatches(matches)`, and `selectFeatured(matches)`.
- `score-preference.js` exports `SCORE_STORAGE_KEY`, `DEFAULT_REVEAL_SCORES`, `readScorePreference(storage)`, `writeScorePreference(storage, value)`, `validScore(match)`, and `syncScoreToggle(button, revealed)`.

- [ ] Add browser assertions that `?date=2026-08-03&competition=Premier+League&status=live&q=arsenal` initializes every control; date/filter changes use `history.replaceState`; the score toggle defaults false and persists true across reload.
- [ ] Run the focused tests and confirm they fail for missing state/persistence behavior.
- [ ] Implement normalization with literal allowed status values (`all`, `live`, `upcoming`, `finished`) and encode only non-default query parameters. Treat `LIVE`, `IN_PLAY`, `PAUSED`, and `HALFTIME` as live; `FINISHED` and `AWARDED` as finished; exception states remain distinct from upcoming.
- [ ] Implement defensive localStorage access and the pressed-button label/icon contract without reading score data.
- [ ] Run focused tests, then `node --check` on both modules.
- [ ] Commit with `git commit -m "feat: add dashboard state and score preference"`.

### Task 3: Render spoiler-safe fixtures, crests, summaries, and groups

**Files:**
- Create: `static/js/crest.js`
- Create: `static/js/fixture-renderer.js`
- Modify: `static/js/fixtures.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- `crest.js` exports `createCrest(team, options)` and replaces failed images with a neutral initials fallback of the same dimensions.
- `fixture-renderer.js` exports `renderLoading`, `renderSummary`, `renderNotice`, `renderFeatured`, `renderFixtureStream`, `renderRequestError`, and `createScoreNode`.
- Renderer handlers are `{onSelect(match, trigger), onTeam(team, trigger), onClearFilters(), onRetry(), onToggleGroup(key)}`.

- [ ] Add a complete fixture fixture containing live `7–6`, finished `4–3`, upcoming, half-time, postponed, missing-score, missing-crest, long-name, competition emblem/area, partial, stale, source, venue, stage, and matchday data.
- [ ] Add tests proving score literals `7`, `6`, `4`, and `3` are absent from `document.documentElement.textContent` and every DOM attribute while hidden; `Score hidden` appears; upcoming shows kickoff; revealing shows `7–6` and `4–3`; missing score says `Score unavailable`.
- [ ] Add tests for two crest images per normal fixture, reserved dimensions, lazy/async attributes, image-error initials fallback, distinct home/away rows, competition grouping/count/emblem/area, featured-selection priority, collapsed long groups, and non-score state labels.
- [ ] Run the focused tests and confirm failure against the current renderer.
- [ ] Implement crest and renderer modules exclusively with `createElement`, trusted static SVG construction, `textContent`, and safe URL assignment. Never assign score values to attributes.
- [ ] Replace `fixtures.js` with an unminified module controller sufficient to load the fixture data, read the score preference, call the renderer, and delegate actions.
- [ ] Run the focused tests and confirm the hidden-score DOM scan passes before proceeding.
- [ ] Commit with `git commit -m "feat: render spoiler-safe fixture ledger"`.

### Task 4: Complete loading, filtering, URL, and degraded-data behavior

**Files:**
- Modify: `static/js/fixtures.js`
- Modify: `static/js/fixture-renderer.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- Controller owns one `AbortController`, one monotonically increasing request ID, one debounced search timer, and an immutable current payload reference.
- Fixture request URL is `/api/matches-today?date=<YYYY-MM-DD>&timezone=<IANA>`.

- [ ] Add tests for initial skeletons, date-change skeleton stability, previous/today/next controls, date picker, debounced search, segmented status filters, competition filter, active-filter count, clear-search, clear-filters, correct URL parameters, and Return-to-today behavior.
- [ ] Add separate fixtures/tests for no scheduled matches, no filter matches, 502 provider failure with retry, partial data, stale cached data, missing metadata, and a superseded slow date request.
- [ ] Run the focused tests and verify the expected controller/state failures.
- [ ] Implement cancellable loading and stale-response rejection; preserve the shell during date changes; render distinct empty/filter-empty/error/degraded notices; populate competitions without discarding a URL-selected value; update counts and last-updated time; expose retry without raw exceptions.
- [ ] Run the focused browser tests and full Python suite.
- [ ] Commit with `git commit -m "feat: complete fixture loading and filters"`.

### Task 5: Build responsive match context

**Files:**
- Create: `static/js/match-context.js`
- Modify: `static/js/fixtures.js`
- Modify: `static/js/fixture-renderer.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- `createMatchContext({panel, dialog, closeButton, onTeam, scoreState})` returns `open(match, trigger)`, `close()`, `rerender(revealed)`, and `selected()`.
- Desktop selection renders into the sticky panel; below 1100 px it opens the dialog sheet.

- [ ] Add tests that selecting a fixture marks exactly one card, renders competition/status/local time/venue/matchday/stage/source/crests/teams, respects score privacy, and exposes two team-intelligence buttons.
- [ ] Add mobile tests for dialog open, Escape close, backdrop close, body scroll lock, safe focus placement, and restoration to the initiating details button.
- [ ] Run the focused tests and confirm failure because context selection is currently inert.
- [ ] Implement the responsive panel/dialog adapter, focus trap, Escape/backdrop close, scroll locking, selected-card synchronization, and spoiler-safe rerendering.
- [ ] Run focused tests at desktop and mobile viewports.
- [ ] Commit with `git commit -m "feat: add accessible match context"`.

### Task 6: Complete team intelligence

**Files:**
- Create: `static/js/team-drawer.js`
- Modify: `static/js/fixtures.js`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- `createTeamDrawer({dialog, content, closeButton, getRevealed})` returns `open(team, trigger)`, `close()`, and `rerender()`.
- Successful responses are cached by team ID; in-flight requests are reused; retry starts a fresh request after failure.

- [ ] Add a complete team-analysis fixture matching the backend keys `team_info`, `squad`, `formation_data`, `recent_matches`, `upcoming_matches`, `stats`, `top_performers`, and `competition_analysis`.
- [ ] Add tests for the loading skeleton, crest/name/founded/venue/colors, played/wins/draws/losses/goals/goal difference, form text, recent and upcoming matches, squad totals/formation, provider failure/retry, partial data, one request per cached team, score privacy, focus trap, Escape close, scroll containment, and focus restoration.
- [ ] Run the focused tests and confirm the current two-line drawer fails them.
- [ ] Implement all available sections with semantic headings, text equivalents for form, safe score rendering shared with `createScoreNode`, and omission/explanation for absent provider fields.
- [ ] Run the focused tests, including the hidden-score DOM scan while the drawer is open.
- [ ] Commit with `git commit -m "feat: complete team intelligence drawer"`.

### Task 7: Apply the production visual system and responsive layout

**Files:**
- Replace: `static/css/base.css`
- Replace: `static/css/fixtures.css`
- Modify: `tests/browser/fixtures-dashboard.spec.js`

**Interfaces:**
- CSS exposes the exact supplied `--bg-*`, `--text-*`, `--accent-*`, `--success`, `--warning`, and `--danger` tokens.
- Breakpoint at 1100 px removes the desktop context column; mobile toolbar behavior begins at 768 px; fixture-card mobile layout begins at 600 px.

- [ ] Add browser checks at 320, 375, 430, 768, 1024, 1280, and 1440 px for `scrollWidth <= clientWidth`, nonzero 44 px control targets on mobile, visible details controls, stable score cell, context mode, and intentional long-name wrapping.
- [ ] Add reduced-motion assertions that computed transition/animation durations are zero when `reducedMotion: reduce` is emulated.
- [ ] Run the responsive tests and confirm they fail against the compressed legacy CSS.
- [ ] Implement readable tokenized CSS for the sticky header, daily summary, toolbar, featured match, ledger rows, competition headers, desktop context, mobile sheets, drawer, state cards, skeletons, focus, hover, live dot, and safe areas. Keep all essential actions visible without hover.
- [ ] Run all responsive/reduced-motion tests, capture 1440 px and 375 px screenshots, inspect them, and make one visual critique pass for density, typography, overflow, contrast, and unnecessary decoration.
- [ ] Commit with `git commit -m "style: finish fixtures workspace visual system"`.

### Task 8: Final compatibility and acceptance audit

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `.gitignore`
- Modify: tests only if the audit reveals an uncovered required behavior

**Interfaces:**
- Documentation describes the fixtures-first workspace, spoiler default/storage key, contextual data behavior, and test commands.

- [ ] Update docs and ignore local Playwright artifacts/screenshots without removing the captured evidence.
- [ ] Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` and record the exact count/result.
- [ ] Run `npm test` and `npm run test:browser` and record the exact count/result.
- [ ] Run `python -m compileall -q app.py wsgi.py soccer_scanner`, `node --check` for every source JS file, and `git diff --check`.
- [ ] Start the local app, verify `/`, `/matches-today`, `/teams`, `/league-tables`, `/health/live`, `/health/ready`, and representative API behavior.
- [ ] Use Playwright accessibility snapshots and screenshots at every required width; verify keyboard-only filters, fixture/context/drawer flow, Escape and focus restoration, no console errors, no horizontal overflow, and score literals absent from DOM/attributes while hidden.
- [ ] Compare the finished 1440 px composition with the captured Select XI reference and remove any decorative treatment that does not serve fixture scanning.
- [ ] Audit each design-spec acceptance criterion against a file, automated test, runtime assertion, or screenshot. Do not mark the goal complete while any item lacks direct evidence.
- [ ] Commit with `git commit -m "test: verify fixtures dashboard release"`.
