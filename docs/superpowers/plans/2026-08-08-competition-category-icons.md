# Competition Category Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render official competition emblems when available and use the supplied friendly-category mark for friendly competition group headers without emblems.

**Architecture:** Keep the existing browser-side `createCrest()` path as the single visual component. Add a small competition-icon resolver in `fixture-renderer.js` that prefers provider data and falls back only for recognized friendly category names; keep all fixture rows unchanged.

**Tech Stack:** Native browser ES modules, CSS, PNG asset, Playwright, Node test data, Markdown documentation.

## Global Constraints

- Competition IDs and provider values must come from actual provider data; do not fabricate fixture or provider values.
- Official provider emblems always take precedence over local category artwork.
- The icon applies only to competition group headers, not fixture rows.
- No dependency changes and no backend/API/iOS changes.
- Match surrounding JavaScript conventions: camelCase, native ES modules, versioned imports where already used.

---

### Task 1: Add the friendly category asset

**Files:**
- Create: `static/icons/competition-friendly.png`
- Verify: `static/icons/competition-friendly.png`

**Interfaces:**
- Produces: a transparent PNG referenced by the browser competition-icon resolver.

- [ ] **Step 1: Derive a clean project asset from the supplied image**

Use the attached image as the edit target. Preserve the ball, blue/red handshake, proportions, and colors; remove the gray background and glow; output a square transparent PNG with generous padding and no text or watermark.

- [ ] **Step 2: Inspect and validate the asset**

Confirm the file has an alpha channel, transparent corners, a readable mark at the existing 28px group-header size, and no visible gray background fringe. Keep the final file compact enough for a repeated category header asset.

### Task 2: Add failing browser coverage for competition-icon precedence

**Files:**
- Modify: `tests/browser/fixtures-dashboard.spec.js:248-286`
- Modify: `tests/browser/test-data.js` only if a reusable friendly fixture factory is needed.

**Interfaces:**
- Consumes: the existing `mockFixtures()` helper and `fixturePayload`.
- Produces: browser assertions for provider-emblem precedence and friendly fallback behavior.

- [ ] **Step 1: Add a focused test with a friendly competition lacking an emblem**

Clone one existing test match in the test payload inside the test, change only its fixture ID and competition object to `name: 'Club Friendly'`, `id: '19834'`, `code: '19834'`, and `emblem: null`, then append it to the mocked matches. Assert that the `Club Friendly` competition group contains an image whose source ends with `/static/icons/competition-friendly.png`, and assert that no fixture-row image uses the category asset.

- [ ] **Step 2: Assert official league emblem precedence in the same test**

Assert that the existing `Premier League` competition group still contains an image whose source is the provider-supplied emblem URL, proving the local friendly asset does not replace official competition artwork.

- [ ] **Step 3: Run the focused test before implementation**

Run: `npm run test:chromium -- --grep "competition headers use official emblems"`

Expected: FAIL because the friendly group currently renders the initials fallback and has no local friendly asset reference.

### Task 3: Implement the resolver and styles

**Files:**
- Modify: `static/js/fixture-renderer.js:260-267`
- Modify: `static/css/fixtures.css:810-823` only if the local mark needs category-specific object-fit treatment.

**Interfaces:**
- Consumes: `competition.name`, `competition.emblem`, and `static/icons/competition-friendly.png`.
- Produces: `createCompetitionIdentity(competition)` that passes the resolved image source to `createCrest()` while preserving existing fallback semantics.

- [ ] **Step 1: Add the smallest resolver**

Implement a local helper with this precedence:

```js
function competitionEmblem(competition) {
    if (competition?.emblem) return competition.emblem;
    if (/\bfriendly\b/i.test(competition?.name || '')) {
        return '/static/icons/competition-friendly.png';
    }
    return null;
}
```

Use the returned value as the `crest` passed to `createCrest()`. Leave the existing competition name, area, alt text, dimensions, lazy loading, and unknown-category initials fallback intact.

- [ ] **Step 2: Run the focused test**

Run: `npm run test:chromium -- --grep "competition headers use official emblems"`

Expected: PASS.

- [ ] **Step 3: Run focused accessibility and browser checks**

Run: `npm run test:chromium -- --grep "competition headers|accessibility|navigation"` and `npm run test:webkit -- --grep "competition headers|accessibility|navigation"`.

Expected: all selected tests pass with no serious accessibility violations.

### Task 4: Document and verify the release

**Files:**
- Modify: `CHANGELOG.md` under `Unreleased / Changed`.
- Verify: all files in the plan and the final Git diff.

**Interfaces:**
- Produces: documented user-facing competition icon behavior and a clean, tested change.

- [ ] **Step 1: Update the changelog**

Add a concise Changed entry stating that competition group headers now use official provider emblems, with the supplied mark as the friendly-category fallback.

- [ ] **Step 2: Run the release checks**

Run the repository matrix from `docs/testing.md`, including Python tests, compile checks, JavaScript syntax checks, Node tests, smoke invariants, npm audit, iOS asset checks with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and Chromium/WebKit browser suites. Do not install dependencies without explicit approval.

- [ ] **Step 3: Review and report**

Run `git diff --check`, inspect `git diff`, confirm only the planned files changed, and report any environment-only gate that cannot run.
