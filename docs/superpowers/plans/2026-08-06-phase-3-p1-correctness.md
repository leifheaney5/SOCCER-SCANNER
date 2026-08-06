# Phase 3: P1 Correctness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make four surfaces tell the truth — a country filter that actually filters, browser history that restores what you were looking at, standings that name a verified current season, and an offline snapshot whose counts match its contents.

**Architecture:** The competition→country mapping follows the streaming-registry pattern established in Phase 2: a verified JSON data file resolved server-side, enriching `competition.area` which the client already reads. Standings season configuration moves out of the template into the same kind of data file, with a verification date that a test can fail on. Offline sanitisation recomputes every derived field from the filtered match list rather than carrying stale values.

**Tech Stack:** Python 3.12, Flask, vanilla ES modules, Playwright.

## Global Constraints

- Python tests run as `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`.
- Node tests: `npm run test:node`. Browser: `npx playwright test --project=chromium --project=webkit`.
- No new runtime dependencies. Pillow stays a dev/test dependency only.
- Never log or expose API keys, tokens, connection strings, or score values.
- **No invented facts.** A competition whose country cannot be verified is left unmapped rather than guessed. A season that cannot be verified is not claimed as current.
- Accessibility: every control keeps a complete accessible name, keyboard operation and a visible focus ring.
- Commit after every task; the working tree must be clean between tasks.
- Do NOT add `Co-Authored-By:` trailers to commit messages.

## Verified starting state

- `soccer_scanner/providers/espn.py` emits **no** `area` field anywhere (grep returns nothing), so `competition.area.name` is always `undefined` and `static/js/fixtures.js:121` always builds an empty country list. The control is permanently non-functional.
- `static/js/fixtures.js:366` sets `selectedFixtureId = null` unconditionally inside the `popstate` handler, discarding the fixture the URL still names.
- `templates/league_tables.html:21-26` hardcodes six SofaScore `tournament/<id>/season/<id>` URLs with literal `2025/26` labels.
- `static/js/offline-cache.js:29-40` filters matches by `isOfflineEligible` (correct) but recomputes only `total_matches`/`totalMatches`. The payload also carries `matchStatistics` (`fixture_service.py:248`) and `featured_matches` (`fixture_service.py:274`), which keep their pre-filter values.

---

### Task 1: Competition country registry

**Files:**
- Create: `soccer_scanner/data/competition-countries.json`
- Create: `soccer_scanner/services/competitions.py`
- Test: `tests/test_competition_registry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CompetitionRegistry.from_file(path)`, `country_for(canonical_id: str | None, name: str | None) -> str | None`, and `describe_area(competition: dict) -> dict | None` returning `{'name': str}` or `None` when the country is unknown.

**Only map competitions whose country you are certain of.** An unmapped competition is correct behaviour, not a gap — it simply will not appear in the filter.

- [ ] **Step 1: Create the data file**

Create `soccer_scanner/data/competition-countries.json`. Include the domestic leagues whose country is unambiguous, and deliberately omit multi-country competitions:

```json
{
  "version": 1,
  "lastVerified": "2026-08-06",
  "note": "Deliberately absent because they span more than one country and must not be forced into one: UEFA Champions League, Europa League, Copa Libertadores, World Cup qualifiers, and MLS (Toronto, Montreal and Vancouver are Canadian). Residual risk accepted: the bare aliases bundesliga, serie a and premiership are also used by Austria, Ecuador and Northern Ireland/England respectively; canonical-ID resolution takes precedence over name matching, which limits the exposure.",
  "competitions": [
    {"canonicalId": "premier-league", "aliases": ["premier league", "english premier league", "epl"], "country": "England"},
    {"canonicalId": "championship", "aliases": ["championship", "efl championship"], "country": "England"},
    {"canonicalId": "la-liga", "aliases": ["laliga", "la liga"], "country": "Spain"},
    {"canonicalId": "serie-a", "aliases": ["serie a", "italian serie a"], "country": "Italy"},
    {"canonicalId": "bundesliga", "aliases": ["bundesliga", "german bundesliga"], "country": "Germany"},
    {"canonicalId": "ligue-1", "aliases": ["ligue 1", "french ligue 1"], "country": "France"},
    {"canonicalId": "eredivisie", "aliases": ["eredivisie"], "country": "Netherlands"},
    {"canonicalId": "primeira-liga", "aliases": ["primeira liga", "liga portugal"], "country": "Portugal"},
    {"canonicalId": "liga-mx", "aliases": ["liga mx"], "country": "Mexico"},
    {"canonicalId": "brasileirao", "aliases": ["brasileirao", "brasileiro serie a", "campeonato brasileiro serie a"], "country": "Brazil"},
    {"canonicalId": "primera-division-argentina", "aliases": ["liga profesional argentina", "argentine liga profesional"], "country": "Argentina"},
    {"canonicalId": "scottish-premiership", "aliases": ["scottish premiership", "premiership"], "country": "Scotland"},
    {"canonicalId": "belgian-pro-league", "aliases": ["belgian pro league", "jupiler pro league"], "country": "Belgium"},
    {"canonicalId": "super-lig", "aliases": ["super lig", "turkish super lig"], "country": "Turkey"},
    {"canonicalId": "j1-league", "aliases": ["j1 league", "j league"], "country": "Japan"}
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_competition_registry.py`:

```python
import json
from pathlib import Path
import unittest

from soccer_scanner.services.competitions import CompetitionRegistry

REGISTRY_PATH = Path('soccer_scanner/data/competition-countries.json')


class CompetitionRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = CompetitionRegistry.from_file(REGISTRY_PATH)

    def test_resolves_by_canonical_id(self):
        self.assertEqual(self.registry.country_for('premier-league', None), 'England')

    def test_resolves_by_name_case_insensitively(self):
        for raw in ('Premier League', '  premier league  ', 'EPL'):
            with self.subTest(raw=raw):
                self.assertEqual(self.registry.country_for(None, raw), 'England')

    def test_canonical_id_wins_over_a_conflicting_name(self):
        self.assertEqual(self.registry.country_for('la-liga', 'Premier League'), 'Spain')

    def test_an_unmapped_competition_returns_none(self):
        self.assertIsNone(self.registry.country_for('uefa-champions-league', 'UEFA Champions League'))
        self.assertIsNone(self.registry.country_for(None, None))
        self.assertIsNone(self.registry.country_for(None, ''))

    def test_describe_area_shapes_the_client_contract(self):
        area = self.registry.describe_area({'canonicalId': 'serie-a', 'name': 'Serie A'})

        self.assertEqual(area, {'name': 'Italy'})

    def test_describe_area_returns_none_when_unknown(self):
        # An absent area is honest; a guessed one is not.
        self.assertIsNone(self.registry.describe_area({'name': 'UEFA Champions League'}))
        self.assertIsNone(self.registry.describe_area({}))
        self.assertIsNone(self.registry.describe_area(None))

    def test_multi_country_competitions_are_deliberately_absent(self):
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        mapped = {entry['canonicalId'] for entry in payload['competitions']}

        for forbidden in ('uefa-champions-league', 'uefa-europa-league', 'copa-libertadores'):
            self.assertNotIn(forbidden, mapped)

    def test_ids_and_aliases_are_unique(self):
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        ids = [entry['canonicalId'] for entry in payload['competitions']]
        self.assertEqual(len(ids), len(set(ids)))

        seen = set()
        for entry in payload['competitions']:
            for alias in entry['aliases']:
                normalized = alias.lower()
                self.assertNotIn(normalized, seen, f'duplicate alias: {alias}')
                seen.add(normalized)

    def test_every_entry_declares_a_non_empty_country(self):
        payload = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        for entry in payload['competitions']:
            with self.subTest(entry=entry['canonicalId']):
                self.assertTrue(entry['country'].strip())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run it, expect failure**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_competition_registry.py -q`
Expected: FAIL — `ModuleNotFoundError: soccer_scanner.services.competitions`

- [ ] **Step 4: Implement**

Create `soccer_scanner/services/competitions.py`:

```python
"""Verified competition → country registry.

ESPN emits no country for a competition, so the country filter had nothing to
populate from and was permanently empty. This resolves a country only for
competitions we can verify; anything else stays unmapped rather than guessed,
and multi-country competitions are deliberately excluded because forcing them
into one country would be wrong.
"""

import json
from pathlib import Path


class CompetitionRegistry:
    def __init__(self, competitions):
        self._by_id = {}
        self._by_alias = {}
        for entry in competitions:
            self._by_id[entry['canonicalId']] = entry['country']
            for alias in entry.get('aliases', []):
                self._by_alias[self._normalize(alias)] = entry['country']

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('competitions', []))

    @staticmethod
    def _normalize(value):
        return ' '.join(str(value or '').strip().lower().split())

    def country_for(self, canonical_id, name):
        # A canonical ID is authoritative; a display name is a fallback.
        if canonical_id and canonical_id in self._by_id:
            return self._by_id[canonical_id]
        return self._by_alias.get(self._normalize(name))

    def describe_area(self, competition):
        if not isinstance(competition, dict):
            return None
        country = self.country_for(
            competition.get('canonicalId'),
            competition.get('name'),
        )
        return {'name': country} if country else None
```

- [ ] **Step 5: Run the tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_competition_registry.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add soccer_scanner/data/competition-countries.json soccer_scanner/services/competitions.py tests/test_competition_registry.py
git commit -m "feat: add a verified competition country registry"
```

---

### Task 2: Populate the country filter, and hide it when it cannot filter

**Files:**
- Modify: `soccer_scanner/__init__.py` (register the registry, pass to the fixture service)
- Modify: `soccer_scanner/services/fixture_service.py` (enrich `competition.area`)
- Modify: `static/js/fixtures.js` (`populateCompetitions` — hide the control below two options)
- Test: `tests/test_competition_enrichment.py`, `tests/browser/country-filter.spec.js`

**Interfaces:**
- Consumes: `CompetitionRegistry.describe_area` from Task 1.
- Produces: each fixture's `competition` gains `area: {'name': str}` when the country is known; the key is absent otherwise. `CanonicalFixtureService` gains `competition_registry=None`.

**Enrich at the same composition site the streaming registry uses** (`_compose`), and copy rather than mutate — `merge_fixtures` output is shared between the `usable_current` and `stale` branches.

- [ ] **Step 1: Write the failing server test**

Create `tests/test_competition_enrichment.py`:

```python
import unittest

from soccer_scanner import create_app


class CompetitionEnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})

    def test_the_registry_is_registered(self):
        self.assertIn('competition_registry', self.app.extensions)

    def test_a_known_competition_resolves_a_country(self):
        registry = self.app.extensions['competition_registry']

        self.assertEqual(
            registry.describe_area({'canonicalId': 'premier-league', 'name': 'Premier League'}),
            {'name': 'England'},
        )

    def test_an_unmapped_competition_gets_no_area(self):
        registry = self.app.extensions['competition_registry']

        self.assertIsNone(registry.describe_area({'name': 'UEFA Champions League'}))

    def test_the_registry_is_wired_into_the_fixture_service(self):
        self.assertIs(
            self.app.extensions['fixture_service'].competition_registry,
            self.app.extensions['competition_registry'],
        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it, expect failure**

Expected: FAIL — `'competition_registry'` not in extensions.

- [ ] **Step 3: Register and enrich**

In `soccer_scanner/__init__.py`, beside the streaming registry:

```python
    app.extensions['competition_registry'] = CompetitionRegistry.from_file(
        Path(__file__).parent / 'data' / 'competition-countries.json',
    )
```

Pass `competition_registry=app.extensions['competition_registry']` into `CanonicalFixtureService`, and add the matching `competition_registry=None` keyword argument.

In `_compose`, in the same place the streaming enrichment happens, add the area when it resolves. Build a new dict; do not mutate:

```python
            if self.competition_registry is not None:
                area = self.competition_registry.describe_area(fixture.get('competition') or {})
                if area is not None:
                    competition = {**(fixture.get('competition') or {}), 'area': area}
                    fixture = {**fixture, 'competition': competition}
```

- [ ] **Step 4: Add an integration test**

Add to `tests/test_fixture_service_v2.py`, following the existing `service()`/`fixture()` helpers and the pattern used by the streaming enrichment tests: a composed fixture for a mapped competition gains `competition.area.name`, and one for an unmapped competition has no `area` key at all.

- [ ] **Step 5: Hide the control when it cannot filter**

In `static/js/fixtures.js`, `populateCompetitions` currently always renders the country `<select>`. Change it so that when fewer than two distinct countries are available the control is hidden (`hidden = true` on its wrapping `label.select-control`, not just the `<select>`), and shown otherwise. A filter offering only "All countries" is the non-functional control the audit objected to.

Reset `state.country` to `''` when the control is hidden, and keep the existing reconcile behaviour.

- [ ] **Step 6: Write the browser test**

Create `tests/browser/country-filter.spec.js`. Route the fixtures API to two payloads:
1. Fixtures across at least two mapped competitions in different countries — assert the control is visible, lists both countries, and selecting one filters the visible fixtures.
2. Fixtures whose competitions are all unmapped — assert the control is hidden and no fixtures are filtered away.

- [ ] **Step 7: Run everything**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
npx playwright test tests/browser/country-filter.spec.js --project=chromium --project=webkit
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: make the country filter functional and hide it when it is not"
```

---

### Task 3: Restore fixture context on browser history navigation

**Files:**
- Modify: `static/js/fixtures.js` (the `popstate` handler at line ~361)
- Test: `tests/browser/history-restoration.spec.js`

**Interfaces:**
- Consumes: `createState` (already parses `fixture` from the URL).
- Produces: no new exports; `popstate` restores the selected fixture rather than discarding it.

**The defect:** line 366 sets `selectedFixtureId = null` unconditionally, then `matchContext?.reset()`, so navigating Back to a URL that still carries `?fixture=fx_…` drops the fixture the URL names.

- [ ] **Step 1: Write the failing browser test**

Create `tests/browser/history-restoration.spec.js`. Route the fixtures API to a stable payload with at least two fixtures on two different dates. Then assert:

1. Opening a fixture pushes `?fixture=…` into the URL.
2. Navigating to another date, then pressing Back, restores **both** the previous date and the previously selected fixture — the detail panel shows that fixture again.
3. Forward navigation works symmetrically.
4. Changing timezone then going Back restores the previous timezone and keeps the selected fixture, since the fixture is unchanged by a zone change.
5. Filters and sort survive a Back navigation.
6. Focus is not lost to `<body>` after a history navigation.

Use a deterministic render signal before each assertion — `#dashboard-status` containing `fixtures shown` — rather than a fixed timeout. `page.goto` resolves on `load` while these modules use top-level `await`, and a naive wait produces exactly the cross-document race that had to be fixed in `refresh-controller.spec.js`.

- [ ] **Step 2: Run it, expect failure**

Run: `npx playwright test tests/browser/history-restoration.spec.js --project=chromium`
Expected: FAIL on the fixture-restoration assertions.

- [ ] **Step 3: Fix the handler**

Replace the unconditional reset. The restored state already carries the fixture ID from the URL, so use it:

```javascript
    window.addEventListener('popstate', () => {
        cancelPendingSearch();
        const previous = state;
        const restored = createState(window.location.search, detectedTimezone);
        setState(restored, {reason: 'popstate'});
        // The URL still names a fixture; discarding it here was the defect.
        selectedFixtureId = state.fixture || null;
        if (!selectedFixtureId) matchContext?.reset();
        syncControls();
        if (previous.date !== state.date || previous.timezone !== state.timezone) {
            loadFixtures();
        } else {
            reflectCurrentResults();
        }
    });
```

`reflectCurrentResults` already reopens the match context for `selectedFixtureId` when the fixture is present in the payload (see its closing block), so restoring the ID is sufficient on the same-day path. On the reload path `loadFixtures` ends in `reflectCurrentResults`, so it is covered there too.

Confirm that by reading `reflectCurrentResults` before relying on it. If it does not reopen the panel, make it do so rather than duplicating the logic in the handler.

- [ ] **Step 4: Run the tests**

```bash
npx playwright test tests/browser/history-restoration.spec.js --project=chromium --project=webkit
npx playwright test --project=chromium --project=webkit
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix: restore the selected fixture on history navigation"
```

---

### Task 4: Verified standings season configuration

**Files:**
- Create: `soccer_scanner/data/standings-seasons.json`
- Modify: `templates/league_tables.html`
- Modify: `soccer_scanner/routes/pages.py` (`league_tables` view)
- Modify: `soccer_scanner/__init__.py`
- Test: `tests/test_standings_seasons.py`

**Interfaces:**
- Produces: `app.extensions['standings_seasons']` — a list of `{'canonicalId', 'name', 'season', 'provider', 'tournamentId', 'seasonId', 'embedUrl', 'lastVerified', 'verifiedBy'}` passed to the template, plus `is_stale(today) -> bool`.

**The defect:** `templates/league_tables.html:21-26` hardcodes six SofaScore `tournament/<id>/season/<id>` URLs with literal `2025/26` labels. Nothing fails when the season rolls over, so the page silently shows a stale season.

- [ ] **Step 1: Extract the configuration**

Create `soccer_scanner/data/standings-seasons.json`. Copy the six tournament and season IDs **verbatim from the existing template** — do not invent new ones, and do not guess a newer season:

```json
{
  "version": 1,
  "lastVerified": "2026-08-06",
  "verifiedBy": "engineering",
  "staleAfterDays": 350,
  "competitions": [
    {"canonicalId": "premier-league", "name": "Premier League", "season": "2025/26", "provider": "sofascore", "tournamentId": 1, "seasonId": 76986},
    {"canonicalId": "la-liga", "name": "LaLiga", "season": "2025/26", "provider": "sofascore", "tournamentId": 36, "seasonId": 77559},
    {"canonicalId": "bundesliga", "name": "Bundesliga", "season": "2025/26", "provider": "sofascore", "tournamentId": 42, "seasonId": 77333},
    {"canonicalId": "serie-a", "name": "Serie A", "season": "2025/26", "provider": "sofascore", "tournamentId": 33, "seasonId": 76457},
    {"canonicalId": "ligue-1", "name": "Ligue 1", "season": "2025/26", "provider": "sofascore", "tournamentId": 4, "seasonId": 77356},
    {"canonicalId": "primeira-liga", "name": "Liga Portugal", "season": "2025/26", "provider": "sofascore", "tournamentId": 52, "seasonId": 77806}
  ]
}
```

Cross-check each `tournamentId`/`seasonId` pair against the current template before committing. A transcription error here silently shows the wrong league's table.

- [ ] **Step 2: Write the failing test**

Create `tests/test_standings_seasons.py`:

```python
from datetime import date, timedelta
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse

from soccer_scanner import create_app
from soccer_scanner.services.standings import StandingsSeasons

CONFIG_PATH = Path('soccer_scanner/data/standings-seasons.json')


class StandingsSeasonsTest(unittest.TestCase):
    def setUp(self):
        self.seasons = StandingsSeasons.from_file(CONFIG_PATH)

    def test_every_competition_declares_a_verified_season(self):
        for entry in self.seasons.competitions:
            with self.subTest(entry=entry['canonicalId']):
                self.assertTrue(entry['season'].strip())
                self.assertTrue(entry['tournamentId'])
                self.assertTrue(entry['seasonId'])

    def test_embed_urls_are_https_and_on_the_declared_provider(self):
        for entry in self.seasons.competitions:
            with self.subTest(entry=entry['canonicalId']):
                parsed = urlparse(entry['embedUrl'])
                self.assertEqual(parsed.scheme, 'https')
                self.assertTrue(parsed.netloc.endswith('sofascore.com'))

    def test_configuration_is_not_stale_today(self):
        # This is the point of the task: it must FAIL once the recorded
        # verification ages out, rather than silently serving a dead season.
        self.assertFalse(
            self.seasons.is_stale(date.today()),
            'standings season configuration is stale — re-verify the season IDs '
            'and update lastVerified in soccer_scanner/data/standings-seasons.json',
        )

    def test_staleness_triggers_after_the_configured_window(self):
        payload = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        verified = date.fromisoformat(payload['lastVerified'])
        window = int(payload['staleAfterDays'])

        self.assertFalse(self.seasons.is_stale(verified + timedelta(days=window - 1)))
        self.assertTrue(self.seasons.is_stale(verified + timedelta(days=window + 1)))

    def test_the_page_renders_from_configuration_not_hardcoded_markup(self):
        app = create_app({'TESTING': True})

        html = app.test_client().get('/league-tables').get_data(as_text=True)

        for entry in self.seasons.competitions:
            self.assertIn(entry['name'], html)
        # The season label must come from configuration, so changing it there
        # changes the page.
        self.assertIn(self.seasons.competitions[0]['season'], html)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run it, expect failure**

Expected: FAIL — `ModuleNotFoundError: soccer_scanner.services.standings`.

- [ ] **Step 4: Implement**

Create `soccer_scanner/services/standings.py`:

```python
"""Standings season configuration.

The season and provider identifiers used to be hardcoded in the template, so a
season rollover silently served a dead table with no signal. They now live in
configuration carrying a verification date, and `is_stale` gives a test
something to fail on.
"""

from datetime import date, timedelta
import json
from pathlib import Path
from urllib.parse import quote


class StandingsSeasons:
    def __init__(self, payload):
        self.last_verified = date.fromisoformat(payload['lastVerified'])
        self.verified_by = payload.get('verifiedBy', 'unknown')
        self.stale_after_days = int(payload.get('staleAfterDays', 400))
        self.competitions = [
            {**entry, 'embedUrl': self._embed_url(entry)}
            for entry in payload.get('competitions', [])
        ]

    @classmethod
    def from_file(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

    @staticmethod
    def _embed_url(entry):
        title = f"{entry['name']} {entry['season']}"
        # safe='' is required: quote() defaults to safe='/', which would leave
        # the slash in "2025/26" unescaped and split the title across two path
        # segments. The original hardcoded URLs escaped it as %2F.
        encoded = quote(title, safe='')
        return (
            'https://widgets.sofascore.com/embed/tournament/'
            f"{entry['tournamentId']}/season/{entry['seasonId']}/standings/"
            f'{encoded}?widgetTitle={encoded}&showCompetitionLogo=true'
        )

    def is_stale(self, today=None):
        today = today or date.today()
        return today > self.last_verified + timedelta(days=self.stale_after_days)
```

- [ ] **Step 5: Wire it into the page**

Register in `soccer_scanner/__init__.py`:

```python
    app.extensions['standings_seasons'] = StandingsSeasons.from_file(
        Path(__file__).parent / 'data' / 'standings-seasons.json',
    )
```

Change `league_tables` in `soccer_scanner/routes/pages.py` to pass the configuration:

```python
@pages.get('/league-tables')
def league_tables():
    seasons = current_app.extensions['standings_seasons']
    return render_template(
        'league_tables.html',
        competitions=seasons.competitions,
        seasons_stale=seasons.is_stale(),
    )
```

Replace the six hardcoded `<option>` elements in `templates/league_tables.html` with a loop over `competitions`, using `entry.embedUrl` as the value and `{{ entry.name }} {{ entry.season }}` as the label. When `seasons_stale` is true, render a visible notice telling the visitor the standings configuration has not been re-verified recently — do not hide the tables, and do not claim the data is wrong when you only know the configuration is old.

- [ ] **Step 6: Run the tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
npx playwright test --project=chromium --project=webkit
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: move standings seasons into verified configuration"
```

---

### Task 5: Recompute derived fields in the offline snapshot

**Files:**
- Modify: `static/js/offline-cache.js`
- Test: `tests/offline-cache.test.mjs`

**Interfaces:**
- Consumes: `isOfflineEligible` (already imported).
- Produces: `sanitizeFixturePayload` additionally recomputes `matchStatistics` and `featured_matches` from the filtered list, and drops any provider-derived count that no longer matches.

**The defect:** `sanitizeFixturePayload` filters `matches` by `isOfflineEligible` and updates `total_matches`/`totalMatches`, but the payload also carries `matchStatistics` (`fixture_service.py:248`) and `featured_matches` (`fixture_service.py:274`), which keep their pre-filter values. Offline, the page can show "12 matches" in a summary while listing four, and feature a match that was filtered out.

- [ ] **Step 1: Write the failing test**

Add to `tests/offline-cache.test.mjs`:

```javascript
test('derived fields are recomputed from the filtered match list', () => {
    const payload = {
        matches: [
            {canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'}},
            {canonicalFixtureId: 'fx_b', status: {code: 'IN_PLAY'}},
            {canonicalFixtureId: 'fx_c', status: {code: 'PENALTIES'}},
            {canonicalFixtureId: 'fx_d', status: {code: 'POSTPONED'}},
        ],
        // Pre-filter values that must not survive.
        matchStatistics: {total: 4, live: 2, finished: 1},
        featured_matches: [{canonicalFixtureId: 'fx_b', status: {code: 'IN_PLAY'}}],
        total_matches: 4,
    };

    const clean = sanitizeFixturePayload(payload, '2026-08-06T00:00:00Z');

    // Only FINISHED and POSTPONED are offline-eligible.
    assert.deepEqual(clean.matches.map(m => m.canonicalFixtureId), ['fx_a', 'fx_d']);
    assert.equal(clean.total_matches, 2);
    assert.equal(clean.totalMatches, 2);
    assert.equal(clean.matchStatistics.total, 2);
    // A live match must not remain featured in a snapshot that excludes it.
    assert.deepEqual(clean.featured_matches.map(m => m.canonicalFixtureId), []);
});

test('a featured match that survives filtering is kept', () => {
    const payload = {
        matches: [{canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'}}],
        featured_matches: [{canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'}}],
    };

    const clean = sanitizeFixturePayload(payload, '2026-08-06T00:00:00Z');

    assert.deepEqual(clean.featured_matches.map(m => m.canonicalFixtureId), ['fx_a']);
});

test('statistics are absent rather than wrong when the payload had none', () => {
    const clean = sanitizeFixturePayload({
        matches: [{canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'}}],
    }, '2026-08-06T00:00:00Z');

    assert.equal(clean.matchStatistics, undefined);
});
```

If `tests/offline-cache.test.mjs` does not already import `sanitizeFixturePayload`, add the import at the top following the existing test files' style.

- [ ] **Step 2: Run it, expect failure**

Run: `node --test tests/offline-cache.test.mjs`
Expected: FAIL — `matchStatistics.total` is 4 and `featured_matches` still contains the live fixture.

- [ ] **Step 3: Implement**

In `static/js/offline-cache.js`, after filtering `matches`, recompute the derived fields. Keep a field absent when the source payload did not carry it — inventing statistics is worse than omitting them:

```javascript
    const survivingIds = new Set(
        matches.map(match => String(match?.canonicalFixtureId ?? match?.id ?? '')),
    );
    // Any fixture filtered out of the snapshot must also disappear from the
    // fields derived from it, or the page reports counts and features
    // matches it is not showing.
    const featured = Array.isArray(clean.featured_matches)
        ? clean.featured_matches.filter(match => survivingIds.has(
            String(match?.canonicalFixtureId ?? match?.id ?? ''),
        ))
        : undefined;
    const statistics = clean.matchStatistics
        ? {...clean.matchStatistics, total: matches.length}
        : undefined;
```

Then include them in the returned object only when defined, and recompute any other count you find on the payload that is derived from the match list. Read the actual payload shape in `fixture_service.py` before deciding which fields qualify — do not guess.

- [ ] **Step 4: Run the tests**

```bash
node --test tests/offline-cache.test.mjs
npm run test:node
npx playwright test --project=chromium --project=webkit
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix: recompute offline snapshot fields from the filtered matches"
```

---

### Task 6: Phase gate

- [ ] **Step 1: Run every local gate**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
npm run test:node
python -m compileall -q app.py wsgi.py soccer_scanner
find static tests -type f \( -name '*.js' -o -name '*.mjs' \) -print0 | xargs -0 -n1 node --check
npx playwright test --project=chromium --project=webkit
npm audit --audit-level=high
python -m pip_audit -r requirements.txt
git diff --check
```

- [ ] **Step 2: Update the audit**

In `docs/audits/2026-08-04-recommendation-validation.md`, section F: the country filter, `popstate` restoration, standings season and PWA recomputation rows move to `implemented`, each naming its covering test. Do not mark a row implemented without a passing test named in the evidence column.

- [ ] **Step 3: Push and confirm CI**

- [ ] **Step 4: Deploy staging and verify**

Confirm `/health/version` reports the branch head, `/league-tables` renders from configuration, and the country filter appears only when at least two countries resolve.

- [ ] **Step 5: Update the roadmap and commit**
