import assert from 'node:assert/strict';
import test from 'node:test';

import {
    assertProductionDependenciesReady,
    assertUniqueFixtureIds,
} from './production-smoke-invariants.mjs';


test('accepts a fixture payload with unique canonical IDs', () => {
    const matches = [
        {canonicalFixtureId: 'fx_111111111111111111111111'},
        {canonicalFixtureId: 'fx_222222222222222222222222'},
    ];

    assert.doesNotThrow(() => assertUniqueFixtureIds(matches));
});


test('rejects a controlled duplicate canonical fixture ID', () => {
    const matches = [
        {canonicalFixtureId: 'fx_111111111111111111111111'},
        {canonicalFixtureId: 'fx_111111111111111111111111'},
    ];

    assert.throws(
        () => assertUniqueFixtureIds(matches),
        /Duplicate canonicalFixtureId/,
    );
});


test('rejects missing or malformed canonical fixture IDs', () => {
    assert.throws(
        () => assertUniqueFixtureIds([{}]),
        /missing or malformed/,
    );
    assert.throws(
        () => assertUniqueFixtureIds([{canonicalFixtureId: 'provider-cache-key'}]),
        /missing or malformed/,
    );
});


test('requires durable schema-current PostgreSQL and shared Redis readiness', () => {
    const ready = {
        blocking: [],
        database: {
            durable: true,
            reachable: true,
            schemaVersion: '20260804_01',
            status: 'ready',
        },
        cache: {backend: 'redis', shared: true, status: 'ready'},
    };

    assert.doesNotThrow(() => assertProductionDependenciesReady(ready));
    assert.throws(
        () => assertProductionDependenciesReady({
            ...ready,
            database: {...ready.database, durable: false},
        }),
        /durable database/,
    );
    assert.throws(
        () => assertProductionDependenciesReady({
            ...ready,
            cache: {backend: 'memory', shared: false, status: 'degraded'},
        }),
        /shared Redis/,
    );
});
