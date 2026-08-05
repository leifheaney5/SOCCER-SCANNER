# Phase 1: Provider Reliability and Observability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a fixture-provider outage visible and survivable — detected within 15 minutes, reported per provider, and no longer a single point of failure.

**Architecture:** A small in-process `ProviderHealthRegistry` records the outcome of each provider call. `CanonicalFixtureService` writes to it; `/health/ready` and a new `/health/providers` read from it. Provider failure surfaces as `degraded` but never adds to `blocking`, because a 503 on readiness would fail Railway's healthcheck and trigger a rollback loop over an upstream problem the deploy cannot fix. External detection comes from a scheduled GitHub Actions workflow that exercises the real fixture endpoint.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, Redis, Node 22 (`node --test`), GitHub Actions.

## Global Constraints

- Python tests run as `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`.
- Never log or expose API keys, tokens, connection strings, or score values — `soccer_scanner/observability.py` already redacts keys matching `api.?key|token|secret|score|payload|body`.
- `/health/ready` must return 200 whenever the application itself is serving, even when every upstream provider is failing.
- Readiness `blocking` may only contain conditions a redeploy can fix.
- New metric names must be added to `DEFAULT_METRICS` in `soccer_scanner/observability.py` or `increment` will reject them.
- No new runtime dependencies.
- Commit after every task; the working tree must be clean between tasks.

---

### Task 1: Provider health registry

**Files:**
- Create: `soccer_scanner/services/provider_health.py`
- Test: `tests/test_provider_health.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ProviderHealthRegistry` with `record(name: str, status: str, detail: str | None = None) -> None` and `snapshot() -> dict`. Status values are exactly `'ok'`, `'degraded'`, `'unavailable'`, `'disabled'`. `snapshot()` returns `{'status': str, 'providers': list[dict], 'lastSuccessAt': str | None, 'singleProvider': bool}` where each provider dict is `{'name', 'status', 'detail', 'lastObservedAt', 'lastSuccessAt'}` and timestamps are ISO-8601 UTC strings or `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_provider_health.py`:

```python
import unittest

from soccer_scanner.services.provider_health import ProviderHealthRegistry


class FakeClock:
    def __init__(self, value=1_770_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class ProviderHealthRegistryTest(unittest.TestCase):
    def test_reports_unknown_before_any_observation(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        snapshot = registry.snapshot()

        self.assertEqual(snapshot['status'], 'unknown')
        self.assertEqual(snapshot['providers'], [])
        self.assertIsNone(snapshot['lastSuccessAt'])

    def test_all_healthy_providers_report_ok(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'ok')

        self.assertEqual(registry.snapshot()['status'], 'ok')

    def test_one_failing_provider_degrades_rather_than_fails(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable', detail='connect timeout')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'degraded')

    def test_every_provider_failing_reports_unavailable(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'unavailable')
        registry.record('football-data', 'unavailable')

        self.assertEqual(registry.snapshot()['status'], 'unavailable')

    def test_disabled_providers_do_not_count_against_health(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        self.assertEqual(registry.snapshot()['status'], 'ok')

    def test_last_success_is_retained_after_a_later_failure(self):
        clock = FakeClock()
        registry = ProviderHealthRegistry(clock=clock)

        registry.record('espn', 'ok')
        clock.advance(120)
        registry.record('espn', 'unavailable', detail='HTTP 503')

        provider = registry.snapshot()['providers'][0]
        self.assertEqual(provider['status'], 'unavailable')
        self.assertEqual(provider['detail'], 'HTTP 503')
        # The success timestamp must survive so staleness is measurable.
        self.assertIsNotNone(provider['lastSuccessAt'])
        self.assertNotEqual(provider['lastSuccessAt'], provider['lastObservedAt'])

    def test_timestamps_are_iso8601_utc(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')

        provider = registry.snapshot()['providers'][0]
        self.assertTrue(provider['lastSuccessAt'].endswith('+00:00'))
        self.assertIn('T', provider['lastSuccessAt'])

    def test_a_lone_configured_provider_is_flagged(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        # One usable provider means no fallback exists.
        self.assertTrue(registry.snapshot()['singleProvider'])

    def test_two_usable_providers_are_not_flagged_as_single(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable')

        self.assertFalse(registry.snapshot()['singleProvider'])

    def test_providers_are_reported_in_a_stable_order(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('zebra', 'ok')
        registry.record('alpha', 'ok')

        names = [item['name'] for item in registry.snapshot()['providers']]
        self.assertEqual(names, ['alpha', 'zebra'])

    def test_unknown_status_values_are_rejected(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        with self.assertRaises(ValueError):
            registry.record('espn', 'exploded')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'soccer_scanner.services.provider_health'`

- [ ] **Step 3: Write the implementation**

Create `soccer_scanner/services/provider_health.py`:

```python
"""In-process provider health tracking.

Readiness answers "can this process serve requests", which stayed true during a
real production outage where every fixture request failed. This registry
answers the different question of whether upstream data is actually flowing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
import time

VALID_STATUSES = frozenset({'ok', 'degraded', 'unavailable', 'disabled'})

# A provider that is switched off by configuration is not a failure.
_COUNTS_AGAINST_HEALTH = frozenset({'degraded', 'unavailable'})


def _isoformat(epoch_seconds):
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


@dataclass
class _ProviderState:
    status: str
    detail: str | None
    last_observed_at: float
    last_success_at: float | None


class ProviderHealthRegistry:
    def __init__(self, *, clock=time.time):
        self.clock = clock
        self._states = {}
        self._lock = Lock()

    def record(self, name, status, detail=None):
        if status not in VALID_STATUSES:
            raise ValueError(f'unknown provider status: {status!r}')
        now = self.clock()
        with self._lock:
            previous = self._states.get(str(name))
            last_success = previous.last_success_at if previous else None
            if status == 'ok':
                last_success = now
            self._states[str(name)] = _ProviderState(
                status=status,
                detail=detail,
                last_observed_at=now,
                last_success_at=last_success,
            )

    def snapshot(self):
        with self._lock:
            states = dict(self._states)

        providers = [
            {
                'name': name,
                'status': state.status,
                'detail': state.detail,
                'lastObservedAt': _isoformat(state.last_observed_at),
                'lastSuccessAt': _isoformat(state.last_success_at),
            }
            for name, state in sorted(states.items())
        ]

        accountable = [
            state for state in states.values() if state.status != 'disabled'
        ]
        if not accountable:
            status = 'unknown' if not states else 'unavailable'
        elif all(state.status in _COUNTS_AGAINST_HEALTH for state in accountable):
            status = 'unavailable'
        elif any(state.status in _COUNTS_AGAINST_HEALTH for state in accountable):
            status = 'degraded'
        else:
            status = 'ok'
        if not states:
            status = 'unknown'

        successes = [
            state.last_success_at for state in states.values()
            if state.last_success_at is not None
        ]
        return {
            'status': status,
            'providers': providers,
            'lastSuccessAt': _isoformat(max(successes)) if successes else None,
            # One usable provider means an upstream failure has no fallback.
            'singleProvider': len(accountable) <= 1,
        }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health.py -q`
Expected: PASS — 10 passed

- [ ] **Step 5: Commit**

```bash
git add soccer_scanner/services/provider_health.py tests/test_provider_health.py
git commit -m "feat: track per-provider health and last success"
```

---

### Task 2: Surface provider health on the health endpoints

**Files:**
- Modify: `soccer_scanner/__init__.py` (register the extension near `app.extensions['rate_limiter']`)
- Modify: `soccer_scanner/routes/health.py`
- Test: `tests/test_provider_health_routes.py`

**Interfaces:**
- Consumes: `ProviderHealthRegistry` from Task 1.
- Produces: `app.extensions['provider_health']`; `/health/ready` gains a `providers` key holding `snapshot()`; new route `GET /health/providers` returning the same snapshot with HTTP 200 always.

- [ ] **Step 1: Write the failing test**

Create `tests/test_provider_health_routes.py`:

```python
import os
import unittest
from unittest.mock import Mock, patch

from soccer_scanner import create_app


class ProviderHealthRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True})
        self.client = self.app.test_client()

    def test_readiness_includes_a_provider_block(self):
        payload = self.client.get('/health/ready').json

        self.assertIn('providers', payload)
        self.assertIn('status', payload['providers'])

    def test_provider_detail_route_is_available(self):
        self.app.extensions['provider_health'].record('espn', 'ok')

        response = self.client.get('/health/providers')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'ok')
        self.assertEqual(response.json['providers'][0]['name'], 'espn')

    def test_a_total_provider_outage_never_fails_readiness(self):
        environment = {
            'APP_ENVIRONMENT': 'production',
            'GIT_COMMIT_SHA': '0123456789abcdef0123456789abcdef01234567',
        }
        with patch.dict(os.environ, environment, clear=False):
            production = create_app({'TESTING': False})
        production.extensions['fixture_identities'] = Mock(
            durable=True,
            health=Mock(return_value={
                'backend': 'database', 'reachable': True,
                'schemaVersion': '20260804_01', 'status': 'ready',
            }),
        )
        production.extensions['cache_backend'] = Mock(
            health=Mock(return_value={
                'backend': 'redis', 'shared': True, 'status': 'ready',
            }),
        )
        production.extensions['rate_limiter'] = Mock(shared=True, degraded=False)
        production.extensions['provider_health'].record('espn', 'unavailable')

        ready = production.test_client().get('/health/ready')

        # A 503 here would fail Railway's healthcheck and roll the deploy back
        # over an upstream outage that redeploying cannot fix.
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json['status'], 'ready')
        self.assertNotIn('providers_unavailable', ready.json['blocking'])
        self.assertEqual(ready.json['providers']['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health_routes.py -q`
Expected: FAIL — `KeyError: 'provider_health'` and `assertIn('providers', payload)` failing

- [ ] **Step 3: Register the extension**

In `soccer_scanner/__init__.py`, add to the imports block alongside the other service imports:

```python
from .services.provider_health import ProviderHealthRegistry
```

Immediately after the `app.extensions['feature_flags'] = ...` assignment, add:

```python
    app.extensions['provider_health'] = ProviderHealthRegistry()
```

- [ ] **Step 4: Expose it from the health routes**

In `soccer_scanner/routes/health.py`, add this helper next to `_rate_limit_health`:

```python
def _provider_health():
    registry = current_app.extensions.get('provider_health')
    if registry is None:
        return {'status': 'unknown', 'providers': [], 'lastSuccessAt': None,
                'singleProvider': False}
    return registry.snapshot()
```

In `ready()`, add before the return:

```python
    provider_health = _provider_health()
```

and add to the JSON body, after the `'rateLimit': rate_limit_health,` line:

```python
        'providers': provider_health,
```

Do **not** append anything to `blocking`.

Then add the detail route at the end of the file:

```python
@health.get('/providers')
def providers():
    # Always 200: this reports upstream state and is polled by monitoring,
    # which needs to distinguish "app is down" from "data is down".
    return jsonify(_provider_health())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health_routes.py -q`
Expected: PASS — 3 passed

- [ ] **Step 6: Run the whole Python suite for regressions**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS — all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add soccer_scanner/__init__.py soccer_scanner/routes/health.py tests/test_provider_health_routes.py
git commit -m "feat: report provider health without failing readiness"
```

---

### Task 3: Record real provider outcomes

**Files:**
- Modify: `soccer_scanner/services/fixture_service.py` (constructor and the provider loop starting near line 95)
- Modify: `soccer_scanner/observability.py` (add metric name)
- Test: `tests/test_provider_health_recording.py`

**Interfaces:**
- Consumes: `ProviderHealthRegistry.record` from Task 1.
- Produces: `CanonicalFixtureService(..., provider_health=None)` keyword argument, and the private method `_record_provider_health(outcome: ProviderOutcome) -> None`. Mapping: `ProviderStatus.SUCCESS` → `'ok'`, `PARTIAL` → `'degraded'`, `DISABLED` → `'disabled'`, everything else → `'unavailable'`.

**Context for the implementer:** `CanonicalFixtureService.fixtures_for_date` loops `for provider in self.providers:` (a two-tuple of the ESPN and Football-Data providers). Inside, the success path binds `outcome = _dict_outcome(lookup.value)` and the failure path catches `except _ProviderFailure as error:` where `error.outcome` is a `ProviderOutcome`. **Both paths must record**, or a failing provider would simply never appear. `ProviderOutcome` (see `soccer_scanner/domain/models.py:26`) carries `provider: str`, `status: ProviderStatus` and `failureCategories: tuple` — there is no `message` field.

- [ ] **Step 1: Write the failing test**

Create `tests/test_provider_health_recording.py`:

```python
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from soccer_scanner import create_app
from soccer_scanner.domain.models import ProviderOutcome, ProviderStatus
from soccer_scanner.services.cache_backend import MemoryCacheBackend
from soccer_scanner.services.fixture_service import CanonicalFixtureService
from soccer_scanner.services.provider_health import ProviderHealthRegistry


def outcome(provider, status, failure_categories=()):
    return ProviderOutcome(
        provider=provider,
        status=status,
        fixtures=(),
        requestedResources=(),
        completedResources=(),
        requestCount=1,
        timeoutCount=0,
        rateLimitCount=0,
        sourceUpdatedAt=None,
        durationMs=5,
        failureCategories=tuple(failure_categories),
    )


def stub_provider(name, result):
    provider = Mock()
    provider.provider_name = name
    provider.fetch_range = Mock(return_value=result)
    return provider


def build_service(espn_result, football_result, registry):
    return CanonicalFixtureService(
        stub_provider('espn', espn_result),
        stub_provider('football-data', football_result),
        MemoryCacheBackend(),
        provider_health=registry,
        now=lambda: datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
    )


class ProviderHealthRecordingTest(unittest.TestCase):
    def test_a_successful_fetch_marks_both_providers_healthy(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.SUCCESS),
            outcome('football-data', ProviderStatus.SUCCESS),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'ok')
        self.assertEqual({item['name'] for item in snapshot['providers']},
                         {'espn', 'football-data'})

    def test_a_failing_provider_is_recorded_with_its_failure_category(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.SUCCESS),
            outcome('football-data', ProviderStatus.UNAVAILABLE, ('timeout',)),
            registry,
        )

        try:
            service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')
        except Exception:
            pass  # A partial failure may still raise; health must be recorded.

        recorded = {
            item['name']: item for item in registry.snapshot()['providers']
        }
        self.assertEqual(recorded['football-data']['status'], 'unavailable')
        self.assertIn('timeout', recorded['football-data']['detail'])
        self.assertEqual(registry.snapshot()['status'], 'degraded')

    def test_a_disabled_provider_does_not_degrade_health(self):
        registry = ProviderHealthRegistry()
        service = build_service(
            outcome('espn', ProviderStatus.SUCCESS),
            outcome('football-data', ProviderStatus.DISABLED),
            registry,
        )

        service.fixtures_for_date(datetime(2026, 8, 5).date(), 'UTC')

        self.assertEqual(registry.snapshot()['status'], 'ok')
        self.assertTrue(registry.snapshot()['singleProvider'])

    def test_the_registry_is_wired_into_the_application_service(self):
        app = create_app({'TESTING': True})

        self.assertIs(
            app.extensions['fixture_service'].provider_health,
            app.extensions['provider_health'],
        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health_recording.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'provider_health'`

- [ ] **Step 3: Add the constructor argument and mapping**

In `soccer_scanner/services/fixture_service.py`, add `provider_health=None` to the keyword-only arguments of `CanonicalFixtureService.__init__` (after `identity_registry=None`), and store it beside the other assignments:

```python
        self.provider_health = provider_health
```

Add this module-level mapping after the imports:

```python
# Provider outcome -> the vocabulary ProviderHealthRegistry accepts.
_HEALTH_BY_STATUS = {
    ProviderStatus.SUCCESS: 'ok',
    ProviderStatus.PARTIAL: 'degraded',
    ProviderStatus.DISABLED: 'disabled',
}
```

- [ ] **Step 4: Add the recording helper**

Add this method to `CanonicalFixtureService`, next to `_provider_name`:

```python
    def _record_provider_health(self, outcome):
        if self.provider_health is None:
            return
        categories = ','.join(outcome.failureCategories)
        self.provider_health.record(
            outcome.provider,
            _HEALTH_BY_STATUS.get(outcome.status, 'unavailable'),
            detail=categories or None,
        )
```

- [ ] **Step 5: Record on both the success and failure paths**

In `fixtures_for_date`, immediately after:

```python
                outcome = _dict_outcome(lookup.value)
```

add:

```python
                self._record_provider_health(outcome)
```

And in the failure handler, immediately after:

```python
            except _ProviderFailure as error:
                failed.append(error.outcome)
```

add:

```python
                self._record_provider_health(error.outcome)
```

Recording only the success path would leave a permanently failing provider invisible, which is the exact gap this phase exists to close.

- [ ] **Step 6: Pass the registry when constructing the service**

In `soccer_scanner/__init__.py`, add to the `CanonicalFixtureService(...)` call:

```python
        provider_health=app.extensions['provider_health'],
```

Ensure `app.extensions['provider_health']` is assigned **before** this call.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_health_recording.py -q`
Expected: PASS — 2 passed

- [ ] **Step 8: Run the whole suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add soccer_scanner/services/fixture_service.py soccer_scanner/__init__.py tests/test_provider_health_recording.py
git commit -m "feat: record provider outcomes into the health registry"
```

---

### Task 4: Scheduled synthetic production monitor

**Files:**
- Create: `tests/synthetic-monitor.mjs`
- Create: `.github/workflows/synthetic-monitor.yml`
- Modify: `package.json` (add a script)
- Test: `tests/synthetic-monitor.test.mjs`

**Interfaces:**
- Consumes: the deployed `/health/live`, `/health/ready`, `/health/providers`, `/api/v2/fixtures` endpoints.
- Produces: `evaluateChecks(results) -> {ok: boolean, failures: string[]}` exported from `tests/synthetic-monitor.mjs`, and `runMonitor(baseUrl, fetchImpl) -> Promise<{ok, failures, checks}>`.

- [ ] **Step 1: Write the failing test**

Create `tests/synthetic-monitor.test.mjs`:

```javascript
import {strict as assert} from 'node:assert';
import test from 'node:test';

import {evaluateChecks, runMonitor} from './synthetic-monitor.mjs';

const jsonResponse = (body, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
});

function stubFetch(routes) {
    return async url => {
        for (const [fragment, response] of Object.entries(routes)) {
            if (url.includes(fragment)) return response;
        }
        throw new Error(`unstubbed url: ${url}`);
    };
}

const healthy = {
    '/health/live': jsonResponse({status: 'ok'}),
    '/health/ready': jsonResponse({status: 'ready', blocking: []}),
    '/health/providers': jsonResponse({status: 'ok', singleProvider: false}),
    '/api/v2/fixtures': jsonResponse({matches: [{canonicalFixtureId: 'fx_a'}]}),
};

test('a healthy deployment passes every check', async () => {
    const result = await runMonitor('https://example.test', stubFetch(healthy));
    assert.equal(result.ok, true);
    assert.deepEqual(result.failures, []);
});

test('an unavailable fixture endpoint fails the monitor', async () => {
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/api/v2/fixtures': jsonResponse(
            {error: {code: 'provider_unavailable'}}, 503,
        ),
    }));
    assert.equal(result.ok, false);
    assert.ok(result.failures.some(item => item.includes('fixtures')));
});

test('an empty fixture list fails the monitor', async () => {
    // A 200 carrying no fixtures is the silent-outage case that readiness misses.
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/api/v2/fixtures': jsonResponse({matches: []}),
    }));
    assert.equal(result.ok, false);
});

test('a not_ready readiness response fails the monitor', async () => {
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/health/ready': jsonResponse(
            {status: 'not_ready', blocking: ['database_not_ready']}, 503,
        ),
    }));
    assert.equal(result.ok, false);
    assert.ok(result.failures.some(item => item.includes('ready')));
});

test('a network error is reported rather than thrown', async () => {
    const result = await runMonitor('https://example.test', async () => {
        throw new Error('ECONNREFUSED');
    });
    assert.equal(result.ok, false);
    assert.ok(result.failures.length > 0);
});

test('evaluateChecks summarises failed checks', () => {
    const summary = evaluateChecks([
        {name: 'live', ok: true, detail: ''},
        {name: 'fixtures', ok: false, detail: 'HTTP 503'},
    ]);
    assert.equal(summary.ok, false);
    assert.deepEqual(summary.failures, ['fixtures: HTTP 503']);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/synthetic-monitor.test.mjs`
Expected: FAIL — cannot resolve `./synthetic-monitor.mjs`

- [ ] **Step 3: Write the monitor**

Create `tests/synthetic-monitor.mjs`:

```javascript
#!/usr/bin/env node
/**
 * Synthetic production monitor.
 *
 * Railway healthchecks only gate deploys, and `/health/ready` stays green when
 * the application is serving but every upstream provider is failing. This
 * exercises the surface a visitor actually uses and fails loudly when it breaks.
 */

import {pathToFileURL} from 'node:url';

const TODAY = () => new Date().toISOString().slice(0, 10);

export function evaluateChecks(checks) {
    const failures = checks
        .filter(check => !check.ok)
        .map(check => `${check.name}: ${check.detail}`);
    return {ok: failures.length === 0, failures};
}

async function probe(name, url, fetchImpl, validate) {
    try {
        const response = await fetchImpl(url);
        let body = null;
        try {
            body = await response.json();
        } catch {
            body = null;
        }
        return {name, ...validate(response, body)};
    } catch (error) {
        return {name, ok: false, detail: `request failed: ${error.message}`};
    }
}

export async function runMonitor(baseUrl, fetchImpl = fetch) {
    const base = String(baseUrl).replace(/\/$/, '');

    const checks = [
        await probe('live', `${base}/health/live`, fetchImpl, (response, body) => ({
            ok: response.status === 200 && body?.status === 'ok',
            detail: `HTTP ${response.status}`,
        })),
        await probe('ready', `${base}/health/ready`, fetchImpl, (response, body) => ({
            ok: response.status === 200 && body?.status === 'ready',
            detail: `HTTP ${response.status} blocking=${JSON.stringify(body?.blocking ?? null)}`,
        })),
        await probe('providers', `${base}/health/providers`, fetchImpl, (response, body) => ({
            // 'degraded' is tolerated: one provider down is survivable.
            ok: response.status === 200 && body?.status !== 'unavailable',
            detail: `status=${body?.status}`,
        })),
        await probe(
            'fixtures',
            `${base}/api/v2/fixtures?date=${TODAY()}&timezone=UTC`,
            fetchImpl,
            (response, body) => {
                if (response.status !== 200) {
                    return {ok: false, detail: `HTTP ${response.status} ${body?.error?.code ?? ''}`.trim()};
                }
                const matches = Array.isArray(body?.matches) ? body.matches : [];
                return {
                    ok: matches.length > 0,
                    detail: `HTTP 200 but ${matches.length} fixtures returned`,
                };
            },
        ),
    ];

    return {...evaluateChecks(checks), checks};
}

// Entry point when run directly. Compare resolved file URLs rather than
// string-matching paths, which breaks on Windows separators.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const target = process.env.MONITOR_BASE_URL || 'https://soccerscanner.pro';
    const result = await runMonitor(target);
    for (const check of result.checks) {
        console.log(`${check.ok ? 'PASS' : 'FAIL'} ${check.name} — ${check.detail}`);
    }
    if (!result.ok) {
        console.error(`\nSynthetic monitor FAILED against ${target}`);
        process.exit(1);
    }
    console.log(`\nSynthetic monitor passed against ${target}`);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/synthetic-monitor.test.mjs`
Expected: PASS — 6 passed

- [ ] **Step 5: Add the npm script**

In `package.json`, add to `scripts`:

```json
    "monitor:production": "node tests/synthetic-monitor.mjs",
```

- [ ] **Step 6: Run it against production for real**

Run: `npm run monitor:production`
Expected: four `PASS` lines. If `fixtures` fails, that is a genuine live outage — record the output before continuing.

- [ ] **Step 7: Create the scheduled workflow**

Create `.github/workflows/synthetic-monitor.yml`:

```yaml
name: Synthetic monitor

# Railway healthchecks gate deploys only. This is the continuous check: a
# failed run notifies via GitHub's normal workflow-failure notifications.
on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:
    inputs:
      target:
        description: 'Base URL to probe'
        required: false
        default: 'https://soccerscanner.pro'

concurrency:
  group: synthetic-monitor
  cancel-in-progress: true

jobs:
  probe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Probe the deployment
        run: node tests/synthetic-monitor.mjs
        env:
          MONITOR_BASE_URL: ${{ inputs.target || 'https://soccerscanner.pro' }}
```

- [ ] **Step 8: Verify the workflow parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/synthetic-monitor.yml', encoding='utf-8')); print('YAML VALID')"`
Expected: `YAML VALID`

- [ ] **Step 9: Commit**

```bash
git add tests/synthetic-monitor.mjs tests/synthetic-monitor.test.mjs .github/workflows/synthetic-monitor.yml package.json
git commit -m "feat: add a scheduled synthetic production monitor"
```

---

### Task 5: Make the missing fallback provider visible

**Files:**
- Modify: `.env.example`
- Modify: `docs/deployment.md`
- Test: `tests/test_provider_fallback.py`

**Interfaces:**
- Consumes: `snapshot()['singleProvider']` from Task 1 and the existing `FootballDataProvider(..., enabled=bool(api_key))` wiring.
- Produces: no new code paths — this task proves the existing fallback activates when a key is present, and documents that neither environment sets one.

- [ ] **Step 1: Write the failing test**

Create `tests/test_provider_fallback.py`:

```python
import unittest

from soccer_scanner import create_app


class ProviderFallbackTest(unittest.TestCase):
    def test_without_a_key_the_secondary_provider_is_disabled(self):
        app = create_app({'TESTING': True, 'FOOTBALL_DATA_API_KEY': None})

        self.assertFalse(app.extensions['football_data_provider'].enabled)

    def test_supplying_a_key_enables_the_secondary_provider(self):
        app = create_app({'TESTING': True, 'FOOTBALL_DATA_API_KEY': 'test-key'})

        self.assertTrue(app.extensions['football_data_provider'].enabled)

    def test_a_single_usable_provider_is_reported_as_a_risk(self):
        app = create_app({'TESTING': True, 'FOOTBALL_DATA_API_KEY': None})
        registry = app.extensions['provider_health']
        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        snapshot = app.test_client().get('/health/providers').json

        self.assertTrue(snapshot['singleProvider'])
        self.assertEqual(snapshot['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the test**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_provider_fallback.py -q`
Expected: PASS if the existing wiring is correct. If `test_supplying_a_key_enables_the_secondary_provider` fails, the wiring is broken — fix `soccer_scanner/__init__.py` so `FootballDataProvider` receives `enabled=bool(app.config.get('FOOTBALL_DATA_API_KEY'))` before continuing.

- [ ] **Step 3: Document the gap**

Confirm `.env.example` contains `FOOTBALL_DATA_API_KEY=` with a comment. If absent, add:

```bash
# Secondary fixture provider. Without this, ESPN is a single point of failure:
# an ESPN outage takes the whole product down. Free tier: football-data.org
FOOTBALL_DATA_API_KEY=
```

Add to `docs/deployment.md` under a new `## Provider redundancy` heading:

```markdown
## Provider redundancy

As of 2026-08-05 neither `production` nor `staging` sets `FOOTBALL_DATA_API_KEY`,
so ESPN is the only fixture source. A verified production outage on 2026-08-05
returned `provider_unavailable` from `/api/v2/fixtures` while `/health/ready`
continued reporting `ready`.

Set `FOOTBALL_DATA_API_KEY` on both Railway services to activate the fallback.
`/health/providers` reports `singleProvider: true` until a second provider is
usable.
```

- [ ] **Step 4: Run the whole suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .env.example docs/deployment.md tests/test_provider_fallback.py
git commit -m "docs: record the single-provider risk and prove the fallback wiring"
```

---

### Task 6: Diagnose staging provider connectivity

**Files:**
- Modify: `docs/audits/2026-08-04-recommendation-validation.md` (finding 4)

**Interfaces:**
- Consumes: `/health/providers` from Task 2, deployed to staging.
- Produces: evidence — either staging serving fixtures, or a documented root cause.

- [ ] **Step 1: Deploy this phase to staging**

```bash
SHA=$(git rev-parse HEAD)
railway variables --service web-staging --environment staging --set "GIT_COMMIT_SHA=$SHA" --skip-deploys
railway up --service web-staging --environment staging --detach
```

Wait for `SUCCESS`:

```bash
railway deployment list --service web-staging --environment staging --json | head -20
```

- [ ] **Step 2: Read the new provider detail**

```bash
curl -s https://web-staging-staging-eec1.up.railway.app/health/providers
```

Expected: a `detail` string naming the actual failure — timeout, HTTP status, or DNS.

- [ ] **Step 3: Compare against production**

```bash
curl -s https://soccerscanner.pro/health/providers
```

If production shows `ok` and staging shows `unavailable` with a connection-level detail, the cause is environment-level (egress IP reputation or upstream blocking), not code.

- [ ] **Step 4: Check the staging logs for the underlying error**

```bash
railway logs --service web-staging --environment staging | grep -i "provider\|espn\|timeout" | head -30
```

- [ ] **Step 5: Record the finding**

Update finding 4 in `docs/audits/2026-08-04-recommendation-validation.md` with the evidence and either mark it `fixed` with the change made, or `blocked` with the exact cause and the operator action required. Do not close it without evidence.

- [ ] **Step 6: Commit**

```bash
git add docs/audits/2026-08-04-recommendation-validation.md
git commit -m "docs: record the staging provider connectivity root cause"
```

---

### Task 7: Phase gate

- [ ] **Step 1: Run every local gate**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
node --test tests/*.test.mjs
python -m compileall -q app.py wsgi.py soccer_scanner
find static tests -type f \( -name '*.js' -o -name '*.mjs' \) -print0 | xargs -0 -n1 node --check
npm audit --audit-level=high
python -m pip_audit -r requirements.txt
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Push and confirm CI**

```bash
git push origin feat/deliberate-guest-mode
gh run list --branch feat/deliberate-guest-mode --limit 3
```

Expected: `CI` success. The `iOS` workflow will not trigger — no `clients/ios/**` paths changed.

- [ ] **Step 3: Trigger the monitor manually against production**

```bash
gh workflow run "Synthetic monitor"
sleep 60
gh run list --workflow="Synthetic monitor" --limit 1
```

Expected: `success`. A failure is a real outage — capture the run output.

- [ ] **Step 4: Verify the exit criteria**

Confirm each of these before declaring Phase 1 done:

- `/health/providers` returns per-provider status and last success on staging.
- `/health/ready` returned 200 with `providers.status: unavailable` in the Task 2 test.
- The synthetic monitor workflow exists, is scheduled every 15 minutes, and has one green manual run.
- `.env.example` and `docs/deployment.md` state the single-provider risk.
- Finding 4 in the audit has evidence.

- [ ] **Step 5: Update the roadmap**

Mark Phase 1 complete in `docs/superpowers/plans/2026-08-05-finalization-roadmap.md` and commit:

```bash
git add docs/superpowers/plans/2026-08-05-finalization-roadmap.md
git commit -m "docs: mark phase 1 complete"
git push origin feat/deliberate-guest-mode
```
