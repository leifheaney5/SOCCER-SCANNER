import {strict as assert} from 'node:assert';
import test from 'node:test';

import {sanitizeFixturePayload} from '../static/js/offline-cache.js';

const match = (id, code) => ({
    canonicalFixtureId: id,
    status: {code},
    score: {fullTime: {home: 1, away: 0}},
    homeTeam: {name: 'Home'},
    awayTeam: {name: 'Away'},
});

test('offline snapshot excludes extra-time fixtures', () => {
    const payload = {matches: [match('fx_1', 'EXTRA_TIME')]};

    const sanitized = sanitizeFixturePayload(payload);

    assert.deepEqual(sanitized.matches, []);
    assert.equal(sanitized.total_matches, 0);
});

test('offline snapshot excludes penalty-shootout fixtures', () => {
    const payload = {matches: [match('fx_2', 'PENALTIES')]};

    const sanitized = sanitizeFixturePayload(payload);

    assert.deepEqual(sanitized.matches, []);
    assert.equal(sanitized.total_matches, 0);
});

test('offline snapshot excludes live, half-time, suspended, delayed and unknown fixtures', () => {
    const payload = {
        matches: [
            match('fx_3', 'IN_PLAY'),
            match('fx_4', 'HALFTIME'),
            match('fx_5', 'SUSPENDED'),
            match('fx_6', 'DELAYED'),
            match('fx_7', 'SOME_UNMAPPED_CODE'),
        ],
    };

    const sanitized = sanitizeFixturePayload(payload);

    assert.deepEqual(sanitized.matches, []);
});

test('offline snapshot keeps settled fixtures: finished, postponed, cancelled, abandoned, scheduled', () => {
    const payload = {
        matches: [
            match('fx_8', 'FINISHED'),
            match('fx_9', 'POSTPONED'),
            match('fx_10', 'CANCELLED'),
            match('fx_11', 'ABANDONED'),
            match('fx_12', 'SCHEDULED'),
        ],
    };

    const sanitized = sanitizeFixturePayload(payload);

    assert.equal(sanitized.matches.length, 5);
    assert.deepEqual(
        sanitized.matches.map(item => item.canonicalFixtureId).sort(),
        ['fx_10', 'fx_11', 'fx_12', 'fx_8', 'fx_9'],
    );
});

test('offline snapshot strips score fields even from retained matches', () => {
    const payload = {matches: [match('fx_13', 'FINISHED')]};

    const sanitized = sanitizeFixturePayload(payload);

    assert.equal(sanitized.matches[0].score, undefined);
});
