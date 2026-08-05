import {strict as assert} from 'node:assert';
import test from 'node:test';

import {
    calendarDateInZone,
    formatFixtureDate,
    formatKickoff,
    formatTimezoneLabel,
    isSupportedTimeZone,
    resolveTimeZone,
    todayInZone,
} from '../static/js/time-zone.js';

// 2026-08-05T00:30:00Z is still 2026-08-04 in the Americas and already
// 2026-08-05 in Europe/Asia. Every date-membership rule depends on this.
const MIDNIGHT_CROSSOVER = '2026-08-05T00:30:00Z';

test('calendarDateInZone resolves the local day across the UTC midnight boundary', () => {
    assert.equal(calendarDateInZone(MIDNIGHT_CROSSOVER, 'America/New_York'), '2026-08-04');
    assert.equal(calendarDateInZone(MIDNIGHT_CROSSOVER, 'America/Los_Angeles'), '2026-08-04');
    assert.equal(calendarDateInZone(MIDNIGHT_CROSSOVER, 'Europe/London'), '2026-08-05');
    assert.equal(calendarDateInZone(MIDNIGHT_CROSSOVER, 'Asia/Tokyo'), '2026-08-05');
    assert.equal(calendarDateInZone(MIDNIGHT_CROSSOVER, 'Australia/Sydney'), '2026-08-05');
    assert.equal(calendarDateInZone(MIDNIGHT_CROSSOVER, 'UTC'), '2026-08-05');
});

test('formatKickoff renders the selected zone, not the host zone', () => {
    assert.equal(formatKickoff(MIDNIGHT_CROSSOVER, 'America/New_York'), '08:30 PM');
    assert.equal(formatKickoff(MIDNIGHT_CROSSOVER, 'Europe/London'), '01:30 AM');
    assert.equal(formatKickoff(MIDNIGHT_CROSSOVER, 'UTC'), '12:30 AM');
});

test('formatKickoff degrades to a stable placeholder for unusable input', () => {
    assert.equal(formatKickoff(null, 'UTC'), 'Time TBC');
    assert.equal(formatKickoff('not-a-date', 'UTC'), 'Time TBC');
});

test('formatFixtureDate renders a calendar day label in the selected zone', () => {
    assert.equal(
        formatFixtureDate('2026-08-04', 'America/New_York'),
        'Tuesday, August 4, 2026',
    );
    // A bare calendar day must not drift a day when read in a zone behind UTC.
    assert.equal(
        formatFixtureDate('2026-08-04', 'Australia/Sydney'),
        'Tuesday, August 4, 2026',
    );
});

test('todayInZone derives the current day from the supplied instant', () => {
    assert.equal(todayInZone('America/New_York', MIDNIGHT_CROSSOVER), '2026-08-04');
    assert.equal(todayInZone('Asia/Tokyo', MIDNIGHT_CROSSOVER), '2026-08-05');
});

test('formatTimezoneLabel exposes zone, abbreviation and offset', () => {
    const summer = formatTimezoneLabel('America/New_York', '2026-08-04T12:00:00Z');
    assert.equal(summer.timeZone, 'America/New_York');
    assert.equal(summer.abbreviation, 'EDT');
    assert.equal(summer.offsetMinutes, -240);
    assert.equal(summer.offsetLabel, 'UTC-04:00');
    assert.equal(summer.label, 'America/New_York · EDT');

    // Same zone, other side of the DST transition.
    const winter = formatTimezoneLabel('America/New_York', '2026-01-15T12:00:00Z');
    assert.equal(winter.abbreviation, 'EST');
    assert.equal(winter.offsetMinutes, -300);
    assert.equal(winter.offsetLabel, 'UTC-05:00');
});

test('DST transition changes the rendered kickoff for a fixed instant', () => {
    // 2026-03-08 is the US spring-forward date.
    const before = formatKickoff('2026-03-08T06:30:00Z', 'America/New_York');
    const after = formatKickoff('2026-03-08T07:30:00Z', 'America/New_York');
    assert.equal(before, '01:30 AM');
    assert.equal(after, '03:30 AM');
});

test('isSupportedTimeZone accepts IANA zones and rejects junk', () => {
    assert.equal(isSupportedTimeZone('Europe/London'), true);
    assert.equal(isSupportedTimeZone('UTC'), true);
    assert.equal(isSupportedTimeZone('Mars/Olympus'), false);
    assert.equal(isSupportedTimeZone(''), false);
    assert.equal(isSupportedTimeZone(null), false);
});

test('resolveTimeZone prefers an explicit valid zone over the fallback', () => {
    assert.equal(resolveTimeZone('Asia/Tokyo', 'UTC'), 'Asia/Tokyo');
    assert.equal(resolveTimeZone('Mars/Olympus', 'Europe/London'), 'Europe/London');
    assert.equal(resolveTimeZone(null, 'Europe/London'), 'Europe/London');
    // An unusable fallback must still yield a usable zone.
    assert.equal(resolveTimeZone(null, 'Mars/Olympus'), 'UTC');
});
