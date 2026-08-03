# Fixtures Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a fixtures-first Soccer Scanner dashboard with contextual team intelligence and standings, replacing the current three-tab utility experience.

**Architecture:** Retain Flask and the existing API payloads. Replace the fixtures template and monolithic renderer with a dashboard shell plus focused vanilla-JS modules; team analysis and standings load only from explicit contextual actions.

**Tech Stack:** Flask 3, Jinja, vanilla ES modules, CSS custom properties, Python unittest/pytest.

## Global Constraints

- Keep `/`, `/matches-today`, `/teams`, and `/league-tables` successful routes.
- Do not add a framework, animation dependency, account system, or provider.
- Use DOM APIs for all dynamic content; never interpolate provider data into HTML strings.
- Respect `prefers-reduced-motion`, keyboard operation, focus restoration, and the existing CSP.
- Run tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

---

### Task 1: Establish the fixtures-only application shell

**Files:**
- Modify: `templates/base.html`, `templates/matches_today.html`, `templates/index.html`, `templates/league_tables.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Produces stable dashboard element IDs: `dashboard-date`, `competition-filter`, `fixture-stream`, `team-drawer`, and `dashboard-status`.

- [ ] Write route-rendering assertions for the dashboard shell and compatibility-page return actions.
- [ ] Run the focused test and confirm the dashboard IDs are absent.
- [ ] Replace top-level Teams/League Tables links with one fixtures workspace link and a compact “Data views” disclosure; rebuild `matches_today.html` around dashboard landmarks, controls, spotlight, stream, and the team drawer dialog.
- [ ] Keep `/teams` and `/league-tables` templates, but give each an explicit dashboard return link.
- [ ] Run the focused route test and commit the shell change.

### Task 2: Build safe dashboard state and fixture rendering

**Files:**
- Create: `static/js/dashboard-state.js`, `static/js/fixture-stream.js`
- Modify: `static/js/fixtures.js`, `templates/matches_today.html`
- Test: `tests/test_app.py`

**Interfaces:**
- `dashboard-state.js` exports `createDashboardState(search)` with `date`, `competition`, `status`, `query`, `set()`, and `toSearchParams()`.
- `fixture-stream.js` exports `filterMatches(matches, state)`, `groupMatches(matches)`, and `renderFixtureStream(container, groups, handlers)`.

- [ ] Write tests that require module script loading and dashboard data attributes before implementation.
- [ ] Confirm the tests fail because the modules and attributes do not exist.
- [ ] Implement URL-backed state, competition/status/team filtering, competition grouping, empty state, and DOM-node match cards with semantic disclosure buttons.
- [ ] Refactor `fixtures.js` to fetch the existing endpoint, select a live-or-next spotlight, and delegate rendering to the modules.
- [ ] Verify URL filtering manually in a browser and run the full Python suite; commit the rendering work.

### Task 3: Add contextual team intelligence and standings

**Files:**
- Create: `static/js/team-drawer.js`, `static/js/standings-context.js`
- Modify: `templates/matches_today.html`, `static/js/fixtures.js`
- Test: `tests/test_app.py`

**Interfaces:**
- `team-drawer.js` exports `createTeamDrawer(dialog)` with `open(teamId, trigger)` and `close()`.
- `standings-context.js` exports `createStandingsContext(container)` with `toggle(competition)`.

- [ ] Write shell tests for the labelled dialog, close control, and lazy standings region.
- [ ] Confirm they fail before the elements exist.
- [ ] Implement a focus-restoring team drawer that fetches `/api/team-analysis/<id>` after opening and has loading, populated, and provider-error states.
- [ ] Implement a collapsed league-pulse panel that only creates the provider standings iframe after user activation.
- [ ] Verify keyboard open/Escape/close behaviour and run the full Python suite; commit the contextual tooling.

### Task 4: Apply the new visual system and motion contract

**Files:**
- Replace: `static/css/fixtures.css`
- Modify: `static/css/base.css`, `templates/base.html`

**Interfaces:**
- CSS variables define canvas, panel, text, muted, accent, warning, and danger tokens.
- Dashboard classes include `dashboard-shell`, `fixture-card`, `fixture-card--live`, `team-drawer`, and `league-pulse`.

- [ ] Add a test that still requires externally linked CSS and no inline style/script blocks.
- [ ] Confirm it passes before visual work, preserving the CSP constraint.
- [ ] Build the responsive dark analytical layout: desktop context rail, mobile stacked flow, field-green accent, tabular score/time treatment, focused interactive states, and 320 px-safe controls.
- [ ] Add only functional transitions and a global reduced-motion override.
- [ ] Run browser/manual responsive checks, `python -m compileall`, and the full suite; commit the visual system.

### Task 5: Validate compatibility and release readiness

**Files:**
- Modify: `tests/test_app.py`
- Modify: `docs/README.md`

- [ ] Extend tests for route compatibility and dashboard asset/module references.
- [ ] Run the tests once to confirm the new assertions cover the intended output.
- [ ] Document the fixtures-first information architecture and how contextual data loads.
- [ ] Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`, `python -m compileall -q app.py wsgi.py soccer_scanner`, `git diff --check`, and a live local smoke check of `/`, `/teams`, `/league-tables`, and `/health/ready`.
- [ ] Commit the verification/docs update.
