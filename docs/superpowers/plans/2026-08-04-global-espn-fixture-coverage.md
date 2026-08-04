# Global ESPN Fixture Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the narrow ESPN competition allowlist as the primary schedule source so the fixture API reports the broad ESPN global soccer scoreboard for a requested local day.

**Architecture:** The ESPN adapter makes one bounded `sports/soccer/all/scoreboard` request for each UTC day in the calculated provider date range. It extracts the ESPN league numeric ID from each event UID, resolves each newly seen league from one representative event summary, and caches that provider-derived metadata for 24 hours.

**Tech Stack:** Python 3.12, Flask, requests, existing ProviderHttpClient, existing Redis/memory cache, pytest.

## Global Constraints

- Keep every fixture and competition fact provider-derived; do not invent a league name or ID.
- Preserve bounded concurrency, request budgets, canonical identities, de-duplication, score privacy, and typed outcome semantics.
- A complete global scoreboard can confirm an empty day; an unavailable provider cannot.
- Resolve at most one summary per unknown league; cache it for 86,400 seconds.

---

### Task 1: Capture the global scoreboard contract

**Files:** Modify `soccer_scanner/providers/espn.py`, `tests/test_espn_provider.py`.

- [ ] Write a failing test with two global events carrying UIDs for different league IDs; assert exactly one `sports/soccer/all/scoreboard` request and provider-derived competition names.
- [ ] Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_espn_provider.py -q`; it must fail because the adapter currently fans out through 20 fixed slugs.
- [ ] Implement one global scoreboard request with `dates=YYYYMMDD-YYYYMMDD` and `limit=500`; extract the league ID from `s:600~l:<id>~e:<event>`.
- [ ] Run the focused tests and commit `feat: use global ESPN fixture scoreboard`.

### Task 2: Resolve and cache global league metadata

**Files:** Modify `soccer_scanner/providers/espn.py`, `soccer_scanner/__init__.py`, `soccer_scanner/config.py`, and `tests/test_espn_provider.py`.

- [ ] Write a failing test showing that repeated global requests resolve a representative event summary once per league and reuse cached metadata.
- [ ] Implement `resolve_league_metadata(league_id, event_id, budget)` through the existing shared cache backend, using `sports/soccer/all/summary?event=<event_id>` and a 24-hour fresh / 7-day stale cache policy.
- [ ] Validate malformed or unavailable metadata results in explicit partial coverage without rendering fabricated competition labels.
- [ ] Run focused provider/service tests and commit `feat: cache ESPN league metadata`.

### Task 3: Validate broad coverage and complete the release

**Files:** Modify `README.md`, `docs/data-sources.md`, `tests/test_espn_provider.py`.

- [ ] Add contract tests for global-provider failure, complete empty response, and unresolved league metadata.
- [ ] Document global ESPN scoreboard coverage, the 500-event page bound, cached metadata, and provider limitations.
- [ ] Run Python, compile, JavaScript, Chromium/WebKit, security, and live smoke verification; compare the live fixture count with the currently observed global ESPN event count.
- [ ] Commit `docs: document global ESPN fixture coverage`, push main, deploy, and prove the production API is no longer constrained to the prior 20-league allowlist.
