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

test('derived fields that cannot be recomputed offline are dropped, not carried stale', () => {
    const payload = {
        matches: [
            {canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'}},
            {canonicalFixtureId: 'fx_b', status: {code: 'IN_PLAY'}},
            {canonicalFixtureId: 'fx_c', status: {code: 'PENALTIES'}},
            {canonicalFixtureId: 'fx_d', status: {code: 'POSTPONED'}},
        ],
        // Pre-filter values. Nothing reads these, and neither can be recomputed
        // client-side without duplicating server logic, so they must not be
        // frozen into the snapshot at their stale values.
        matchStatistics: {total: 4, byTimeSlot: {morning: 1, afternoon: 1, evening: 2, lateNight: 0}},
        featured_matches: [{canonicalFixtureId: 'fx_b', status: {code: 'IN_PLAY'}}],
        total_matches: 4,
    };

    const clean = sanitizeFixturePayload(payload, '2026-08-06T00:00:00Z');

    // Only FINISHED and POSTPONED are offline-eligible.
    assert.deepEqual(clean.matches.map(m => m.canonicalFixtureId), ['fx_a', 'fx_d']);
    assert.equal(clean.total_matches, 2);
    assert.equal(clean.totalMatches, 2);
    assert.equal(clean.matchStatistics, undefined);
    assert.equal(clean.featured_matches, undefined);
});

test('a payload without those fields is unaffected', () => {
    const clean = sanitizeFixturePayload({
        matches: [{canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'}}],
    }, '2026-08-06T00:00:00Z');

    assert.equal(clean.total_matches, 1);
    assert.equal(clean.matchStatistics, undefined);
    assert.equal(clean.featured_matches, undefined);
});

test('fields the client does read are preserved', () => {
    const clean = sanitizeFixturePayload({
        date: '2026-08-06',
        timezone: 'UTC',
        matches: [{canonicalFixtureId: 'fx_a', status: {code: 'FINISHED'},
                   competition: {name: 'Premier League', area: {name: 'England'}}}],
    }, '2026-08-06T00:00:00Z');

    assert.equal(clean.date, '2026-08-06');
    assert.equal(clean.timezone, 'UTC');
    assert.equal(clean.matches[0].competition.area.name, 'England');
});
