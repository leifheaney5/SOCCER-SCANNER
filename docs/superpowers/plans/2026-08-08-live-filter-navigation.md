# Live Filter Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the duplicate top-level Live navigation item while preserving the existing URL-backed Live fixture filter.

**Architecture:** Keep `status=live` as browser-owned fixture state and make the existing status button the only Live entry point. Update the shared navigation template and browser contract tests; do not change the API, native iOS status picker, or filter implementation.

**Tech Stack:** Flask/Jinja templates, native browser ES modules, Playwright, Python template tests.

## Global Constraints

- Preserve the `status=live` query parameter and the existing `aria-pressed` status-filter contract.
- Keep Fixtures active for all fixture routes, including `/?status=live`.
- Do not modify backend APIs, dependencies, or native iOS source.
- Match the repository's existing 4-space Python / single-quote JavaScript style; no formatter is configured.
- Run focused checks, the release matrix, and `git diff --check` before handoff.

---

### Task 1: Lock the navigation contract with failing tests

**Files:**
- Modify: `tests/test_app.py` near `test_fixture_dashboard_is_home_page`
- Modify: `tests/browser/fixtures-dashboard.spec.js` near `URL state initializes controls and filter changes replace the URL`

**Interfaces:**
- Consumes: Existing Flask test client and Playwright fixture payload helpers.
- Produces: Assertions proving the top navigation has no Live link and the Fixtures link remains active for `status=live`.

- [ ] **Step 1: Write the failing Python template assertion**

Extend the existing home-page HTML test to assert that the rendered primary navigation contains the Fixtures link as the current page and does not contain a navigation link whose text is `Live`.

- [ ] **Step 2: Write the failing browser assertion**

In the URL-state browser test, after loading `/?date=2026-08-03&...&status=live`, assert:

```js
await expect(page.locator('#primary-navigation a', {hasText: 'Fixtures'}))
    .toHaveAttribute('aria-current', 'page');
await expect(page.locator('#primary-navigation a', {hasText: 'Live'})).toHaveCount(0);
```

- [ ] **Step 3: Run the focused tests and verify the expected failure**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_app.py -q
npm run test:chromium -- --grep "URL state initializes controls"
```

Expected: the new navigation assertions fail because the current template still renders the top-level Live link and marks Fixtures inactive for `status=live`.

### Task 2: Remove duplicate Live navigation

**Files:**
- Modify: `templates/base.html:46-48`
- Modify: `CHANGELOG.md` under `Unreleased` / `Changed`
- Modify: `docs/superpowers/specs/2026-08-08-live-filter-navigation-design.md` only if implementation wording needs correction

**Interfaces:**
- Consumes: The failing navigation contract from Task 1.
- Produces: A primary navigation containing Fixtures and Select XI, with Fixtures active for both All and Live filter URLs.

- [ ] **Step 1: Make the minimal template change**

Change the fixture-page navigation logic so the Fixtures link is active whenever `fixture_page` is true, then remove the separate `Live` anchor. Leave the Select XI external link unchanged.

- [ ] **Step 2: Add the changelog entry**

Under `## Unreleased` and `### Changed`, add one bullet stating that Live is now a fixture status filter rather than a separate top-level navigation destination.

- [ ] **Step 3: Run focused tests and verify green**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_app.py -q
npm run test:chromium -- --grep "URL state initializes controls"
```

Expected: both commands pass, including the original URL-backed Live filter assertions.

### Task 3: Verify the affected release surfaces

**Files:**
- No additional files expected.

**Interfaces:**
- Consumes: The completed template and test changes.
- Produces: Evidence that navigation, filters, accessibility, browser behavior, and repository checks remain valid.

- [ ] **Step 1: Run focused browser navigation and accessibility coverage**

Run:

```powershell
npm run test:chromium -- --grep "navigation|URL state|accessibility"
npm run test:webkit -- --grep "navigation|URL state|accessibility"
```

- [ ] **Step 2: Run the repository release matrix**

Run the commands documented in `docs/testing.md`: Python tests, compileall, JavaScript syntax checks, Node tests, smoke invariants, npm audit, available Python audit, Chromium, WebKit, and `git diff --check`.

- [ ] **Step 3: Review the final diff**

Confirm only the navigation template, targeted tests, changelog, and approved design/plan artifacts changed; confirm no iOS, API, dependency, or infrastructure files changed.
