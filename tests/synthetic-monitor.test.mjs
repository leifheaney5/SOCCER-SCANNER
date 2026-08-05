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

test('an empty fixture list without a confirming state fails the monitor', async () => {
    // A 200 carrying no fixtures is the silent-outage case that readiness misses.
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/api/v2/fixtures': jsonResponse({matches: []}),
    }));
    assert.equal(result.ok, false);
});

test('a genuinely empty day (state=empty_confirmed) passes the monitor', async () => {
    // Off-season and quiet days are legitimate: providers succeeded and
    // there really are no fixtures. Treating this as a failure at */15
    // produces up to 96 false alarms a day and trains the monitor to be
    // ignored.
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/api/v2/fixtures': jsonResponse({matches: [], state: 'empty_confirmed'}),
    }));
    assert.equal(result.ok, true);
    assert.deepEqual(result.failures, []);
});

test('an empty day caused by a provider failure still fails the monitor', async () => {
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/api/v2/fixtures': jsonResponse({matches: [], state: 'provider_unavailable'}),
    }));
    assert.equal(result.ok, false);
    assert.ok(result.failures.some(item => item.includes('fixtures')));
});

test('a populated day reports the fixture count, not the empty-day cosmetic bug', async () => {
    const result = await runMonitor('https://example.test', stubFetch(healthy));
    const fixturesCheck = result.checks.find(check => check.name === 'fixtures');
    assert.equal(fixturesCheck.ok, true);
    assert.match(fixturesCheck.detail, /^HTTP 200 with 1 fixtures returned$/);
});

test('providers probe: a degraded status passes', async () => {
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/health/providers': jsonResponse({status: 'degraded', singleProvider: true}),
    }));
    assert.equal(result.ok, true);
});

test('providers probe: an unavailable status fails', async () => {
    const result = await runMonitor('https://example.test', stubFetch({
        ...healthy,
        '/health/providers': jsonResponse({status: 'unavailable', singleProvider: true}),
    }));
    assert.equal(result.ok, false);
    assert.ok(result.failures.some(item => item.includes('providers')));
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
