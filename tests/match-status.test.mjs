import {strict as assert} from 'node:assert';
import test from 'node:test';

import {
    MATCH_STATUSES,
    describeStatus,
    isOfflineEligible,
    isTerminalStatus,
    resolveStatus,
    shouldRefresh,
    statusGroup,
    statusLabel,
    statusShortLabel,
} from '../static/js/match-status.js';

test('every canonical status declares a complete behaviour contract', () => {
    const expected = [
        'scheduled', 'delayed', 'in_progress', 'first_half', 'second_half',
        'half_time', 'extra_time', 'penalties', 'finished_extra_time',
        'finished_penalties', 'finished', 'postponed', 'cancelled',
        'suspended', 'abandoned', 'unknown',
    ];
    assert.deepEqual(Object.keys(MATCH_STATUSES).sort(), [...expected].sort());
    for (const [key, status] of Object.entries(MATCH_STATUSES)) {
        assert.equal(typeof status.label, 'string', `${key} label`);
        assert.equal(typeof status.shortLabel, 'string', `${key} shortLabel`);
        assert.equal(typeof status.group, 'string', `${key} group`);
        assert.equal(typeof status.active, 'boolean', `${key} active`);
        assert.equal(typeof status.terminal, 'boolean', `${key} terminal`);
        assert.equal(typeof status.refresh, 'boolean', `${key} refresh`);
        assert.equal(typeof status.scoreAvailable, 'boolean', `${key} scoreAvailable`);
        assert.equal(typeof status.offlineEligible, 'boolean', `${key} offlineEligible`);
        assert.equal(typeof status.tone, 'string', `${key} tone`);
        assert.ok(status.description.length > 0, `${key} description`);
    }
});

test('provider codes normalise onto the canonical taxonomy', () => {
    assert.equal(resolveStatus({status: 'IN_PLAY'}), 'in_progress');
    assert.equal(resolveStatus({status: 'LIVE'}), 'in_progress');
    assert.equal(resolveStatus({status: 'FIRST_HALF'}), 'first_half');
    assert.equal(resolveStatus({status: 'SECOND_HALF'}), 'second_half');
    assert.equal(resolveStatus({status: {code: 'in_progress', raw: 'STATUS_FIRST_HALF'}}), 'first_half');
    assert.equal(resolveStatus({status: 'PAUSED'}), 'half_time');
    assert.equal(resolveStatus({status: 'HALFTIME'}), 'half_time');
    assert.equal(resolveStatus({status: 'HALF_TIME'}), 'half_time');
    assert.equal(resolveStatus({status: 'EXTRA_TIME'}), 'extra_time');
    assert.equal(resolveStatus({status: 'PENALTIES'}), 'penalties');
    assert.equal(resolveStatus({status: 'PENALTY_SHOOTOUT'}), 'penalties');
    assert.equal(resolveStatus({status: 'FINISHED'}), 'finished');
    assert.equal(resolveStatus({status: 'AWARDED'}), 'finished');
    assert.equal(resolveStatus({status: 'POSTPONED'}), 'postponed');
    assert.equal(resolveStatus({status: 'CANCELED'}), 'cancelled');
    assert.equal(resolveStatus({status: 'CANCELLED'}), 'cancelled');
    assert.equal(resolveStatus({status: 'SUSPENDED'}), 'suspended');
    assert.equal(resolveStatus({status: 'ABANDONED'}), 'abandoned');
    assert.equal(resolveStatus({status: 'DELAYED'}), 'delayed');
    assert.equal(resolveStatus({status: 'SCHEDULED'}), 'scheduled');
    assert.equal(resolveStatus({status: 'TIMED'}), 'scheduled');
    assert.equal(resolveStatus({status: 'FINISHED_AFTER_EXTRA_TIME'}), 'finished_extra_time');
    assert.equal(resolveStatus({status: 'FINISHED_AFTER_PENALTIES'}), 'finished_penalties');
});

test('object-shaped and missing statuses resolve safely', () => {
    assert.equal(resolveStatus({status: {code: 'HALF_TIME'}}), 'half_time');
    assert.equal(resolveStatus({}), 'scheduled');
    assert.equal(resolveStatus(null), 'scheduled');
    assert.equal(resolveStatus({status: 'SOMETHING_NEW'}), 'unknown');
});

test('half time, extra time and penalties are distinct from generic live', () => {
    assert.equal(statusShortLabel({status: 'HALF_TIME'}), 'HT');
    assert.equal(statusShortLabel({status: 'EXTRA_TIME'}), 'ET');
    assert.equal(statusShortLabel({status: 'PENALTIES'}), 'PEN');
    assert.equal(statusShortLabel({status: 'IN_PLAY'}), 'LIVE');
    assert.equal(statusShortLabel({status: 'DELAYED'}), 'DELAYED');
    assert.equal(statusShortLabel({status: 'POSTPONED'}), 'POSTPONED');
    assert.equal(statusShortLabel({status: 'ABANDONED'}), 'ABANDONED');
    assert.equal(statusShortLabel({status: 'FINISHED'}), 'FT');
});

test('abandoned is terminal and is not an upcoming fixture', () => {
    assert.equal(statusGroup({status: 'ABANDONED'}), 'exception');
    assert.notEqual(statusGroup({status: 'ABANDONED'}), 'upcoming');
    assert.equal(isTerminalStatus({status: 'ABANDONED'}), true);
    assert.equal(shouldRefresh({status: 'ABANDONED'}), false);
});

test('active fixtures drive refresh and are never cached offline', () => {
    for (const code of ['IN_PLAY', 'HALF_TIME', 'EXTRA_TIME', 'PENALTIES']) {
        assert.equal(shouldRefresh({status: code}), true, `${code} refresh`);
        assert.equal(isOfflineEligible({status: code}), false, `${code} offline`);
    }
    // Terminal outcomes are safe to keep in an offline snapshot.
    assert.equal(isOfflineEligible({status: 'FINISHED'}), true);
    assert.equal(isOfflineEligible({status: 'POSTPONED'}), true);
    assert.equal(isOfflineEligible({status: 'ABANDONED'}), true);
});

test('a suspended match is still active and still refreshes', () => {
    assert.equal(isTerminalStatus({status: 'SUSPENDED'}), false);
    assert.equal(shouldRefresh({status: 'SUSPENDED'}), true);
    assert.equal(isOfflineEligible({status: 'SUSPENDED'}), false);
});

test('scores are unavailable before a match has started', () => {
    assert.equal(MATCH_STATUSES.scheduled.scoreAvailable, false);
    assert.equal(MATCH_STATUSES.postponed.scoreAvailable, false);
    assert.equal(MATCH_STATUSES.cancelled.scoreAvailable, false);
    assert.equal(MATCH_STATUSES.in_progress.scoreAvailable, true);
    assert.equal(MATCH_STATUSES.penalties.scoreAvailable, true);
    assert.equal(MATCH_STATUSES.abandoned.scoreAvailable, true);
});

test('labels and descriptions are exposed for accessible output', () => {
    assert.equal(statusLabel({status: 'EXTRA_TIME'}), 'Extra time');
    assert.equal(statusLabel({status: 'PENALTIES'}), 'Penalty shootout');
    assert.equal(describeStatus({status: 'HALF_TIME'}), MATCH_STATUSES.half_time.description);
});
