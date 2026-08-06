# Phase 2: Remaining P0 User-Facing Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last three P0 commitments — a header timezone control, branded and truthful streaming discovery, and a complete icon suite — and fix the per-worker provider registry carried over from Phase 1.

**Architecture:** The streaming registry lives server-side in Python and enriches the fixture payload, so web and the native client consume one verified source rather than each inventing its own mapping. The header timezone control and the existing filter `<select>` write to the same single state value — two controls, one timezone. Icons are generated from the existing brand geometry by extending `clients/ios/Tools/generate_app_icon.py`, so web and native icons cannot drift.

**Tech Stack:** Python 3.12, Flask, Redis, vanilla ES modules, Playwright, Pillow.

## Global Constraints

- Python tests run as `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`.
- Node tests run as `npm run test:node`. Browser tests: `npx playwright test --project=chromium --project=webkit`.
- No new runtime dependencies. Pillow is already available for the icon generator and is a build-time tool only — it must not become an application import.
- Never log or expose API keys, tokens, connection strings, or score values.
- Every streaming link must be `https://`, point at an official domain in the registry, and carry `rel="noopener noreferrer"`. Never link to an unofficial stream.
- No invented facts: a service whose region the provider did not supply is labelled "Region unknown", never guessed.
- Accessibility is not optional: every new control needs a complete accessible name, keyboard operation, and a visible focus indicator.
- Commit after every task; the working tree must be clean between tasks.
- Do NOT add `Co-Authored-By:` trailers to commit messages.

---

### Task 1: Redis-backed provider health registry

Carried over from Phase 1. `ProviderHealthRegistry` is in-process, so with `WEB_CONCURRENCY=2` each gunicorn worker holds its own copy. Verified in production: eight sequential `/health/providers` requests returned four `ok` and four `unknown`.

**Files:**
- Modify: `soccer_scanner/services/provider_health.py`
- Modify: `soccer_scanner/__init__.py` (construction site, currently `ProviderHealthRegistry()`)
- Test: `tests/test_provider_health.py`

**Interfaces:**
- Consumes: the existing `record(name, status, detail=None)` / `snapshot()` contract — it must not change.
- Produces: `RedisProviderHealthRegistry(client, *, namespace, ttl_seconds=900, fallback=None, clock=time.time)` with the identical interface, plus `build_provider_health(config)` returning the Redis-backed registry when `REDIS_URL` is set and the in-memory one otherwise.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_provider_health.py`:

```python
class FakeRedisHash:
    """Minimal hash + expiry stand-in shared by several 'workers'."""

    def __init__(self):
        self.hashes = {}
        self.expiries = {}

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def expire(self, key, seconds):
        self.expiries[key] = seconds
        return True


class RedisProviderHealthRegistryTest(unittest.TestCase):
    def registry(self, client, **kwargs):
        from soccer_scanner.services.provider_health import RedisProviderHealthRegistry
        return RedisProviderHealthRegistry(client, namespace='test', **kwargs)

    def test_state_written_by_one_worker_is_visible_to_another(self):
        client = FakeRedisHash()
        worker_one = self.registry(client)
        worker_two = self.registry(client)

        worker_one.record('espn', 'ok')

        # This is the whole point: a second gunicorn worker must not report
        # 'unknown' just because it did not personally serve the request.
        snapshot = worker_two.snapshot()
        self.assertEqual(snapshot['status'], 'ok')
        self.assertEqual([item['name'] for item in snapshot['providers']], ['espn'])

    def test_aggregate_rules_match_the_in_memory_registry(self):
        client = FakeRedisHash()
        registry = self.registry(client)

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable', detail='timeout')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'degraded')
        self.assertFalse(snapshot['singleProvider'])
        recorded = {item['name']: item for item in snapshot['providers']}
        self.assertEqual(recorded['football-data']['detail'], 'timeout')

    def test_last_success_survives_a_later_failure_across_workers(self):
        client = FakeRedisHash()
        clock = FakeClock()
        writer = self.registry(client, clock=clock)

        writer.record('espn', 'ok')
        clock.advance(120)
        writer.record('espn', 'unavailable', detail='HTTP 503')

        provider = self.registry(client).snapshot()['providers'][0]
        self.assertEqual(provider['status'], 'unavailable')
        self.assertIsNotNone(provider['lastSuccessAt'])
        self.assertNotEqual(provider['lastSuccessAt'], provider['lastObservedAt'])

    def test_an_entry_is_given_a_bounded_lifetime(self):
        client = FakeRedisHash()
        self.registry(client, ttl_seconds=900).record('espn', 'ok')

        # Without an expiry a dead provider's last state would persist forever.
        self.assertTrue(any(value == 900 for value in client.expiries.values()))

    def test_redis_failure_degrades_to_the_in_memory_registry(self):
        class BrokenRedis:
            def hset(self, *args, **kwargs):
                raise RuntimeError('redis down')

            def hgetall(self, *args, **kwargs):
                raise RuntimeError('redis down')

            def expire(self, *args, **kwargs):
                raise RuntimeError('redis down')

        registry = self.registry(BrokenRedis())

        registry.record('espn', 'ok')

        # Availability is preserved and the degradation is observable.
        self.assertEqual(registry.snapshot()['status'], 'ok')
        self.assertTrue(registry.degraded)

    def test_a_corrupt_entry_is_ignored_rather_than_raising(self):
        client = FakeRedisHash()
        client.hset('test:provider-health', 'espn', 'not-json')
        registry = self.registry(client)

        # A malformed entry must not take down the health endpoint.
        self.assertEqual(registry.snapshot()['status'], 'unknown')
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health.py -q`
Expected: FAIL — `ImportError: cannot import name 'RedisProviderHealthRegistry'`

- [ ] **Step 3: Implement the Redis-backed registry**

Add to `soccer_scanner/services/provider_health.py`. Keep `ProviderHealthRegistry` exactly as it is — it remains the fallback and the development default.

```python
import json


class RedisProviderHealthRegistry:
    """Provider health shared across gunicorn workers.

    The in-process registry gives each worker its own view, so /health/providers
    answered `ok` or `unknown` depending on which worker happened to serve the
    request. One hash keyed by provider name fixes that.

    Ageing-out is enforced in `_read` against each entry's `lastObservedAt`,
    NOT by the Redis key TTL. `expire` applies to the whole hash, so an
    actively-served provider would refresh the TTL for every other provider
    and a decommissioned one would never age out. The key TTL is kept only to
    bound total growth. Writes go through a single atomic Lua script, as
    `rate_limit.py` does, so concurrent workers cannot clobber `lastSuccessAt`.
    """

    def __init__(
        self,
        client,
        *,
        namespace='soccer-scanner',
        ttl_seconds=900,
        fallback=None,
        clock=time.time,
        metrics=None,
    ):
        self.client = client
        self.namespace = ''.join(
            character if character.isalnum() or character in '-_.' else '-'
            for character in str(namespace)
        )[:64]
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.clock = clock
        self.metrics = metrics
        self.shared = True
        self.degraded = False
        self._fallback = fallback or ProviderHealthRegistry(clock=clock)

    @property
    def _key(self):
        return f'{self.namespace}:provider-health'

    def record(self, name, status, detail=None):
        if status not in VALID_STATUSES:
            raise ValueError(f'unknown provider status: {status!r}')
        # Mirror into the fallback so a later Redis outage still has context.
        self._fallback.record(name, status, detail)
        now = self.clock()
        try:
            existing = self._read()
            previous = existing.get(str(name)) or {}
            last_success = previous.get('lastSuccessAt')
            payload = {
                'status': status,
                'detail': detail,
                'lastObservedAt': now,
                'lastSuccessAt': now if status == 'ok' else last_success,
            }
            self.client.hset(self._key, str(name), json.dumps(payload))
            self.client.expire(self._key, self.ttl_seconds)
            self.degraded = False
        except Exception:
            self.degraded = True
            if self.metrics is not None:
                self.metrics.increment('api.provider_health_degraded')

    def _read(self):
        raw = self.client.hgetall(self._key) or {}
        entries = {}
        for name, value in raw.items():
            key = name.decode() if isinstance(name, bytes) else str(name)
            text = value.decode() if isinstance(value, bytes) else str(value)
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                # A corrupt entry must never take down the health endpoint.
                continue
            if isinstance(parsed, dict) and parsed.get('status') in VALID_STATUSES:
                entries[key] = parsed
        return entries

    def snapshot(self):
        try:
            entries = self._read()
            self.degraded = False
        except Exception:
            self.degraded = True
            return self._fallback.snapshot()

        providers = [
            {
                'name': name,
                'status': entry['status'],
                'detail': entry.get('detail'),
                'lastObservedAt': _isoformat(entry.get('lastObservedAt')),
                'lastSuccessAt': _isoformat(entry.get('lastSuccessAt')),
            }
            for name, entry in sorted(entries.items())
        ]
        return _aggregate(providers)


def _aggregate(providers):
    """Shared status rollup so the two registries cannot drift apart.

    Takes the already-rendered provider dicts, not internal state, so both the
    dataclass-backed in-memory registry and the JSON-backed Redis one can share
    it without a type mismatch.
    """
    accountable = [item for item in providers if item['status'] != 'disabled']
    if not providers:
        status = 'unknown'
    elif not accountable:
        status = 'unavailable'
    elif all(item['status'] in _COUNTS_AGAINST_HEALTH for item in accountable):
        status = 'unavailable'
    elif any(item['status'] in _COUNTS_AGAINST_HEALTH for item in accountable):
        status = 'degraded'
    else:
        status = 'ok'
    successes = [
        item['lastSuccessAt'] for item in providers if item['lastSuccessAt']
    ]
    return {
        'status': status,
        'providers': providers,
        'lastSuccessAt': max(successes) if successes else None,
        'singleProvider': len(accountable) <= 1,
    }


def build_provider_health(config, *, metrics=None):
    """Shared registry when Redis is configured, in-process otherwise."""
    fallback = ProviderHealthRegistry()
    redis_url = config.get('REDIS_URL')
    if not redis_url:
        return fallback

    import redis

    client = redis.Redis.from_url(
        redis_url,
        socket_connect_timeout=config['REDIS_CONNECT_TIMEOUT'],
        socket_timeout=config['REDIS_READ_TIMEOUT'],
        health_check_interval=30,
    )
    return RedisProviderHealthRegistry(
        client,
        namespace=config.get('CACHE_NAMESPACE', 'soccer-scanner'),
        fallback=fallback,
        metrics=metrics,
    )
```

Add `'api.provider_health_degraded'` to `DEFAULT_METRICS` in `soccer_scanner/observability.py`, or `increment` will reject it.

Refactor `ProviderHealthRegistry.snapshot` to call the shared `_aggregate` helper so the two implementations cannot diverge. Its existing tests must keep passing unchanged — if any assertion has to be edited, stop and report, because that means behaviour changed.

- [ ] **Step 4: Wire it up**

In `soccer_scanner/__init__.py`, replace `app.extensions['provider_health'] = ProviderHealthRegistry()` with:

```python
    app.extensions['provider_health'] = build_provider_health(
        app.config,
        metrics=app.extensions['metrics'],
    )
```

and update the import accordingly.

- [ ] **Step 5: Run the tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS, with the pre-existing `ProviderHealthRegistry` tests unchanged.

- [ ] **Step 6: Commit**

```bash
git add soccer_scanner/services/provider_health.py soccer_scanner/observability.py soccer_scanner/__init__.py tests/test_provider_health.py
git commit -m "fix: share provider health across workers"
```

---

### Task 2: Verified streaming-service registry

**Files:**
- Create: `soccer_scanner/data/streaming-services.json`
- Create: `soccer_scanner/services/streaming.py`
- Test: `tests/test_streaming_registry.py`

**Interfaces:**
- Consumes: the raw `broadcasts` entries the ESPN provider already emits — `{'type': 'STREAMING', 'name': str, 'region': str | None}`.
- Produces: `StreamingRegistry.from_file(path)`, `resolve(name) -> dict | None` returning `{'id', 'displayName', 'officialUrl', 'domains', 'requiresAttribution'}`, and `describe(broadcast) -> dict` returning `{'id', 'displayName', 'region', 'regionKnown', 'officialUrl', 'source'}`.

**Only include services you can verify.** Do not invent official URLs. Every `officialUrl` must be the service's own root domain over HTTPS.

- [ ] **Step 1: Create the registry data**

Create `soccer_scanner/data/streaming-services.json`:

```json
{
  "version": 1,
  "lastVerified": "2026-08-05",
  "services": [
    {
      "id": "peacock",
      "displayName": "Peacock",
      "aliases": ["peacock", "peacock premium", "peacock tv"],
      "domains": ["peacocktv.com"],
      "officialUrl": "https://www.peacocktv.com/",
      "requiresAttribution": false
    },
    {
      "id": "espn-plus",
      "displayName": "ESPN+",
      "aliases": ["espn+", "espn plus", "espnplus"],
      "domains": ["plus.espn.com", "espn.com"],
      "officialUrl": "https://plus.espn.com/",
      "requiresAttribution": false
    },
    {
      "id": "paramount-plus",
      "displayName": "Paramount+",
      "aliases": ["paramount+", "paramount plus"],
      "domains": ["paramountplus.com"],
      "officialUrl": "https://www.paramountplus.com/",
      "requiresAttribution": false
    },
    {
      "id": "apple-tv",
      "displayName": "Apple TV",
      "aliases": ["apple tv", "apple tv+", "apple tv plus"],
      "domains": ["tv.apple.com"],
      "officialUrl": "https://tv.apple.com/",
      "requiresAttribution": false
    },
    {
      "id": "amazon-prime-video",
      "displayName": "Prime Video",
      "aliases": ["prime video", "amazon prime video", "amazon"],
      "domains": ["primevideo.com", "amazon.com"],
      "officialUrl": "https://www.primevideo.com/",
      "requiresAttribution": false
    },
    {
      "id": "dazn",
      "displayName": "DAZN",
      "aliases": ["dazn"],
      "domains": ["dazn.com"],
      "officialUrl": "https://www.dazn.com/",
      "requiresAttribution": false
    },
    {
      "id": "fubo",
      "displayName": "Fubo",
      "aliases": ["fubo", "fubotv", "fubo tv"],
      "domains": ["fubo.tv"],
      "officialUrl": "https://www.fubo.tv/",
      "requiresAttribution": false
    },
    {
      "id": "max",
      "displayName": "Max",
      "aliases": ["max", "hbo max"],
      "domains": ["max.com"],
      "officialUrl": "https://www.max.com/",
      "requiresAttribution": false
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_streaming_registry.py`:

```python
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse

from soccer_scanner.services.streaming import StreamingRegistry

REGISTRY_PATH = Path('soccer_scanner/data/streaming-services.json')


class StreamingRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = StreamingRegistry.from_file(REGISTRY_PATH)

    def test_resolves_a_known_service_by_exact_name(self):
        service = self.registry.resolve('Peacock')

        self.assertEqual(service['id'], 'peacock')
        self.assertEqual(service['displayName'], 'Peacock')

    def test_resolution_is_case_and_whitespace_insensitive(self):
        for raw in ('peacock', '  PEACOCK  ', 'Peacock Premium'):
            with self.subTest(raw=raw):
                self.assertEqual(self.registry.resolve(raw)['id'], 'peacock')

    def test_an_unknown_service_resolves_to_none(self):
        self.assertIsNone(self.registry.resolve('Some Unlicensed Stream'))
        self.assertIsNone(self.registry.resolve(''))
        self.assertIsNone(self.registry.resolve(None))

    def test_describe_preserves_a_supplied_region(self):
        described = self.registry.describe({
            'type': 'STREAMING', 'name': 'Peacock', 'region': 'US',
        })

        self.assertEqual(described['region'], 'US')
        self.assertTrue(described['regionKnown'])

    def test_describe_labels_an_absent_region_honestly(self):
        described = self.registry.describe({'type': 'STREAMING', 'name': 'DAZN'})

        # Never guess a region — say it is unknown.
        self.assertFalse(described['regionKnown'])
        self.assertEqual(described['region'], 'Region unknown')

    def test_an_unknown_service_still_describes_with_its_raw_name(self):
        described = self.registry.describe({
            'type': 'STREAMING', 'name': 'Local Broadcaster', 'region': 'BR',
        })

        self.assertIsNone(described['id'])
        self.assertEqual(described['displayName'], 'Local Broadcaster')
        self.assertIsNone(described['officialUrl'])
        self.assertEqual(described['region'], 'BR')

    def test_non_streaming_broadcasts_are_not_described(self):
        self.assertIsNone(self.registry.describe({'type': 'TV', 'name': 'Peacock'}))

    def test_every_official_url_is_https_and_matches_a_declared_domain(self):
        for service in json.loads(REGISTRY_PATH.read_text())['services']:
            with self.subTest(service=service['id']):
                parsed = urlparse(service['officialUrl'])
                self.assertEqual(parsed.scheme, 'https')
                host = parsed.netloc.removeprefix('www.')
                self.assertTrue(
                    any(host == domain or host.endswith('.' + domain)
                        for domain in service['domains']),
                    f"{service['officialUrl']} is not on a declared domain",
                )

    def test_service_ids_and_aliases_are_unique(self):
        services = json.loads(REGISTRY_PATH.read_text())['services']
        ids = [service['id'] for service in services]
        self.assertEqual(len(ids), len(set(ids)))

        seen = set()
        for service in services:
            for alias in service['aliases']:
                normalized = alias.lower()
                # An alias claimed twice would resolve unpredictably.
                self.assertNotIn(normalized, seen, f'duplicate alias: {alias}')
                seen.add(normalized)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run it to verify failure**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_streaming_registry.py -q`
Expected: FAIL — `ModuleNotFoundError: soccer_scanner.services.streaming`

- [ ] **Step 4: Implement the registry**

Create `soccer_scanner/services/streaming.py`:

```python
"""Verified streaming-service registry.

Providers report free-text service names. This maps them onto a small set of
verified services with official URLs, so the UI can link somewhere real instead
of rendering an unlinked string — and so an unrecognised name degrades to plain
text rather than a guessed link.
"""

import json
from pathlib import Path

REGION_UNKNOWN = 'Region unknown'


class StreamingRegistry:
    def __init__(self, services):
        self._services = {}
        self._by_alias = {}
        for service in services:
            self._services[service['id']] = service
            for alias in [service['displayName'], *service.get('aliases', [])]:
                self._by_alias[self._normalize(alias)] = service['id']

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('services', []))

    @staticmethod
    def _normalize(value):
        return ' '.join(str(value or '').strip().lower().split())

    def resolve(self, name):
        service_id = self._by_alias.get(self._normalize(name))
        if service_id is None:
            return None
        service = self._services[service_id]
        return {
            'id': service['id'],
            'displayName': service['displayName'],
            'officialUrl': service['officialUrl'],
            'domains': list(service['domains']),
            'requiresAttribution': bool(service.get('requiresAttribution')),
        }

    def describe(self, broadcast):
        """Render-ready description, or None if this is not a streaming entry."""
        if not isinstance(broadcast, dict):
            return None
        if str(broadcast.get('type') or '').upper() != 'STREAMING':
            return None
        raw_name = str(broadcast.get('name') or '').strip()
        if not raw_name:
            return None

        service = self.resolve(raw_name)
        region = str(broadcast.get('region') or '').strip()
        return {
            'id': service['id'] if service else None,
            'displayName': service['displayName'] if service else raw_name,
            'officialUrl': service['officialUrl'] if service else None,
            'region': region or REGION_UNKNOWN,
            'regionKnown': bool(region),
            'source': 'espn',
        }
```

- [ ] **Step 5: Run the tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_streaming_registry.py -q`
Expected: PASS — 9 passed

- [ ] **Step 6: Commit**

```bash
git add soccer_scanner/data/streaming-services.json soccer_scanner/services/streaming.py tests/test_streaming_registry.py
git commit -m "feat: add a verified streaming-service registry"
```

---

### Task 3: Enrich the fixture payload and render streaming honestly

**Files:**
- Modify: `soccer_scanner/__init__.py` (register the registry)
- Modify: `soccer_scanner/services/fixture_service.py` (enrich each fixture)
- Modify: `static/js/fixture-renderer.js` (`streamingServiceNames`, `createFixtureCard`)
- Modify: `static/js/match-context.js` (detail panel)
- Modify: `README.md`
- Test: `tests/test_streaming_enrichment.py`, `tests/browser/streaming.spec.js`

**Interfaces:**
- Consumes: `StreamingRegistry.describe` from Task 2.
- Produces: each fixture gains `streaming: [{id, displayName, region, regionKnown, officialUrl, source}]`. The raw `broadcasts` array stays for compatibility.

- [ ] **Step 1: Write the failing server test**

Create `tests/test_streaming_enrichment.py`:

```python
import unittest

from soccer_scanner import create_app


class StreamingEnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})

    def test_the_registry_is_registered(self):
        self.assertIn('streaming_registry', self.app.extensions)

    def test_a_known_service_is_enriched_with_an_official_url(self):
        registry = self.app.extensions['streaming_registry']

        described = registry.describe({
            'type': 'STREAMING', 'name': 'Peacock', 'region': 'US',
        })

        self.assertEqual(described['displayName'], 'Peacock')
        self.assertTrue(described['officialUrl'].startswith('https://'))
        self.assertEqual(described['region'], 'US')

    def test_an_unknown_service_is_never_given_a_link(self):
        registry = self.app.extensions['streaming_registry']

        described = registry.describe({
            'type': 'STREAMING', 'name': 'Unverified Stream', 'region': None,
        })

        # Linking an unrecognised name could send a visitor anywhere.
        self.assertIsNone(described['officialUrl'])
        self.assertEqual(described['region'], 'Region unknown')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it, expect failure**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_streaming_enrichment.py -q`
Expected: FAIL — `'streaming_registry'` not in extensions

- [ ] **Step 3: Register the registry and enrich fixtures**

In `soccer_scanner/__init__.py`, alongside the other `Path(__file__).parent / 'data'` construction (`team_identities` uses the same pattern):

```python
    app.extensions['streaming_registry'] = StreamingRegistry.from_file(
        Path(__file__).parent / 'data' / 'streaming-services.json',
    )
```

Pass it into `CanonicalFixtureService` as a `streaming_registry=None` keyword argument, stored on the instance.

In `fixture_service.py`, where each fixture dict is composed for the response, add:

```python
            if self.streaming_registry is not None:
                described = [
                    self.streaming_registry.describe(item)
                    for item in (fixture.get('broadcasts') or [])
                ]
                fixture['streaming'] = [item for item in described if item]
```

Find the actual composition site by reading `_compose`; do not guess where fixtures are built.

- [ ] **Step 4: Render it on the card**

In `static/js/fixture-renderer.js`, replace `streamingServiceNames` with a function reading the enriched `match.streaming` array, falling back to `match.broadcasts` names when `streaming` is absent (older cached payloads). On the card show `displayName · region` for the first service and a `+N` affordance beyond that. Give the container `aria-label` describing where to watch.

- [ ] **Step 5: Render the detail panel**

In `static/js/match-context.js`, render each service with its display name, region, and — only when `officialUrl` is present — an anchor with `target="_blank"` and `rel="noopener noreferrer"`. Append the disclaimer: `Availability varies by region and subscription. Listings may be incomplete or out of date.`

Never render an anchor when `officialUrl` is null.

- [ ] **Step 6: Write the browser test**

Create `tests/browser/streaming.spec.js`, routing `**/api/v2/fixtures**` to a payload containing one known service with a region, one known service without a region, and one unknown service. Assert:
- the known service shows its display name and region;
- the region-less service shows `Region unknown`;
- the unknown service renders as text with **no** anchor;
- every rendered streaming anchor has `rel` containing `noopener` and `noreferrer` and an `href` starting `https://`.

- [ ] **Step 7: Correct the README**

`README.md` currently states broadcast listings are unavailable while the UI displays them. Replace that with an accurate description: streaming services are shown when a provider reports them, regions are shown when known and labelled unknown otherwise, links point only at official service homepages, and no match streams are hosted or provided.

- [ ] **Step 8: Run everything**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
npx playwright test tests/browser/streaming.spec.js --project=chromium --project=webkit
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: show branded, regional, linkable streaming services"
```

---

### Task 4: Header timezone control

**Files:**
- Modify: `templates/matches_today.html` (the `header_actions` block)
- Create: `static/js/timezone-control.js`
- Modify: `static/js/fixtures.js` (wire it to the same state)
- Modify: `static/css/fixtures.css`
- Test: `tests/browser/timezone-control.spec.js`

**Interfaces:**
- Consumes: `formatTimezoneLabel`, `supportedTimeZones`, `browserTimeZone`, `resolveTimeZone` from `static/js/time-zone.js`.
- Produces: `createTimezoneControl({root, getTimeZone, onChange})` returning `{sync()}`. It must not own the timezone — `fixtures.js` state remains the single source of truth, and the existing `#timezone-filter` select must stay in sync with it.

**There must be exactly one timezone value.** The header control and the filter select are two views of `state.timezone`.

- [ ] **Step 1: Add the markup**

In `templates/matches_today.html`, inside `{% block header_actions %}`, **before** the existing score toggle:

```html
<div id="timezone-control" class="timezone-control" data-open="false">
    <button id="timezone-trigger" class="timezone-trigger" type="button"
            aria-haspopup="listbox" aria-expanded="false"
            aria-controls="timezone-listbox">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 7v5l3 2"/>
        </svg>
        <span data-timezone-label>UTC</span>
    </button>
    <div id="timezone-listbox" class="timezone-popover" role="dialog"
         aria-label="Select timezone" hidden>
        <label class="sr-only" for="timezone-search">Search timezones</label>
        <input id="timezone-search" class="timezone-search" type="search"
               autocomplete="off" placeholder="Search timezones"
               aria-controls="timezone-options">
        <ul id="timezone-options" class="timezone-options" role="listbox"
            aria-label="Timezones"></ul>
    </div>
</div>
```

- [ ] **Step 2: Write the browser test first**

Create `tests/browser/timezone-control.spec.js`. Route `**/api/v2/fixtures**` to a fixed payload with one fixture at `2026-08-05T00:30:00Z`, then assert:

1. The trigger sits in the header and shows the current zone's abbreviation.
2. Its accessible name includes the IANA zone identifier.
3. Clicking opens the popover, `aria-expanded` becomes `true`, and focus moves into the search field.
4. Typing `Tokyo` filters the list to matching zones.
5. Selecting `Asia/Tokyo` updates the trigger label, closes the popover, restores focus to the trigger, and puts `timezone=Asia%2FTokyo` in the URL.
6. **The `#timezone-filter` select in the filter panel now also reads `Asia/Tokyo`** — one value, two controls.
7. Pressing `Escape` closes the popover and restores focus to the trigger.
8. The rendered kickoff time changes when the zone changes.
9. The control is reachable and operable by keyboard alone.

- [ ] **Step 3: Run it, expect failure**

Run: `npx playwright test tests/browser/timezone-control.spec.js --project=chromium`
Expected: FAIL — no such element

- [ ] **Step 4: Implement the control**

Create `static/js/timezone-control.js` exporting `createTimezoneControl`. Requirements:

- Build options from `supportedTimeZones()`, with `UTC` and the browser zone pinned to the top under a "Suggested" group.
- Each option shows the zone identifier and its current abbreviation and offset via `formatTimezoneLabel`.
- Render at most 50 filtered options at a time; searching narrows by case-insensitive substring on the identifier.
- `role="option"` with `aria-selected` on the current zone; arrow keys move, Enter selects, Escape closes.
- On open, remember the trigger and restore focus to it on close.
- Close on outside click and on `Escape`.
- Call `onChange(zone)` — never mutate state directly.
- `sync()` re-renders the trigger label from `getTimeZone()`.

- [ ] **Step 5: Wire it in `fixtures.js`**

Import and construct it in `init()`, passing `getTimeZone: () => state.timezone` and an `onChange` that performs exactly what the existing `#timezone-filter` change handler does — `setState({timezone, fixture: ''}, {reason: 'timezone'})`, reset selection, `syncControls()`, `syncUrl('push')`, `loadFixtures()`. Extract that shared body into one function used by both handlers so they cannot drift. Call `control.sync()` from `syncControls()`.

- [ ] **Step 6: Style it**

Add styles to `static/css/fixtures.css`: the trigger must meet a 44px minimum touch target, show a visible focus ring, and collapse to the abbreviation only below 480px. The popover must not overflow the viewport at 320px.

- [ ] **Step 7: Run the tests**

```bash
npx playwright test tests/browser/timezone-control.spec.js --project=chromium --project=webkit
npx playwright test --project=chromium --project=webkit
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add a searchable header timezone control"
```

---

### Task 5: Brand mark in the header and the full icon suite

**Files:**
- Modify: `clients/ios/Tools/generate_app_icon.py` → also emit web icons
- Create: `static/icons/*` (generated)
- Modify: `templates/base.html`, `static/manifest.webmanifest`, `static/sw.js`
- Test: `tests/test_brand_assets.py`, `tests/browser/branding.spec.js`

**Interfaces:**
- Consumes: the existing `scanner_s()` and `corner_brackets()` geometry.
- Produces: `render(size)` reused for every output; a `--web` flag writing `static/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png` (180), `favicon-32.png`, and `static/social-card.png` (1200×630).

- [ ] **Step 1: Write the failing asset test**

Create `tests/test_brand_assets.py`:

```python
from pathlib import Path
import unittest

REQUIRED = {
    'static/icons/icon-192.png': (192, 192),
    'static/icons/icon-512.png': (512, 512),
    'static/icons/icon-maskable-512.png': (512, 512),
    'static/icons/apple-touch-icon.png': (180, 180),
    'static/icons/favicon-32.png': (32, 32),
    'static/social-card.png': (1200, 630),
}


class BrandAssetTest(unittest.TestCase):
    def test_every_required_icon_exists_at_the_right_size(self):
        from PIL import Image

        for path, expected in REQUIRED.items():
            with self.subTest(path=path):
                asset = Path(path)
                self.assertTrue(asset.exists(), f'{path} is missing')
                with Image.open(asset) as image:
                    self.assertEqual(image.size, expected)

    def test_icons_are_opaque(self):
        from PIL import Image

        # An alpha channel on an iOS/PWA icon renders as a black box.
        for path in ('static/icons/icon-512.png', 'static/icons/apple-touch-icon.png'):
            with self.subTest(path=path), Image.open(path) as image:
                self.assertEqual(image.mode, 'RGB')

    def test_the_manifest_declares_the_png_icons(self):
        import json

        manifest = json.loads(Path('static/manifest.webmanifest').read_text())
        sources = {icon['src'] for icon in manifest['icons']}

        self.assertIn('/static/icons/icon-192.png', sources)
        self.assertIn('/static/icons/icon-512.png', sources)
        maskable = [i for i in manifest['icons'] if 'maskable' in i.get('purpose', '')]
        self.assertTrue(maskable, 'a maskable icon is required for Android')
        # An SVG must not be the maskable icon — Android will not mask it.
        for icon in maskable:
            self.assertTrue(icon['src'].endswith('.png'))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it, expect failure**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_brand_assets.py -q`
Expected: FAIL — assets missing

- [ ] **Step 3: Extend the generator**

Modify `clients/ios/Tools/generate_app_icon.py`:
- Keep the existing iOS output as the default.
- Add `--web`, writing every asset in `REQUIRED` above into the repository root's `static/`.
- The maskable variant must inset the mark to roughly 80% of the canvas so Android's safe zone does not crop the scanner brackets.
- The social card is 1200×630 with the mark centred on the brand black; do not render text into it.

Run it and inspect at least one output visually before committing — a generator that emits a blank square passes a size assertion.

- [ ] **Step 4: Wire the assets up**

`templates/base.html`: add `apple-touch-icon`, a 32px PNG `icon` alongside the existing SVG, and switch the Open Graph and Twitter image to `/static/social-card.png` (raster — several platforms will not render SVG cards).

`static/manifest.webmanifest`: declare `icon-192`, `icon-512` with `"purpose": "any"`, and `icon-maskable-512` with `"purpose": "maskable"`.

`static/sw.js`: add the new icon paths to the precache list if it maintains one; bump its cache version constant so returning visitors fetch the new assets.

- [ ] **Step 5: Put the mark in the header**

In `templates/base.html`, inside the existing `a.app-title`, add an inline SVG of the mark (the same geometry as `static/favicon.svg`) before the wordmark, `aria-hidden="true"` since the anchor already has `aria-label="Soccer Scanner home"`. Below 480px show the mark alone and hide the wordmark with CSS, not by removing it from the DOM.

- [ ] **Step 6: Write the browser test**

Create `tests/browser/branding.spec.js`: the header link exposes its accessible name and contains an `svg`; every declared icon URL returns HTTP 200 with an image content type; the manifest parses and its icon URLs all resolve.

- [ ] **Step 7: Run everything**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
npx playwright test tests/browser/branding.spec.js --project=chromium --project=webkit
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add the brand mark and a complete icon suite"
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

- [ ] **Step 2: Verify the audit rows**

Update `docs/audits/2026-08-04-recommendation-validation.md`: section C rows 2 (header timezone control), 5 (streaming region) and 10 (icon suite) move to `implemented` with evidence. Do not mark a row implemented without a passing test named in the evidence column.

- [ ] **Step 3: Push and confirm CI**

```bash
git push origin <branch>
gh run list --limit 3
```

- [ ] **Step 4: Deploy staging and verify**

```bash
SHA=$(git rev-parse HEAD)
railway variables --service web-staging --environment staging --set "GIT_COMMIT_SHA=$SHA" --skip-deploys
railway up --service web-staging --environment staging --detach
```

Then confirm `/health/version` reports that SHA, `/health/providers` is consistent across repeated requests (Task 1's fix — sample it at least eight times), and the new icons return 200.

- [ ] **Step 5: Update the roadmap**

Mark Phase 2 complete in `docs/superpowers/plans/2026-08-05-finalization-roadmap.md`, and commit.
