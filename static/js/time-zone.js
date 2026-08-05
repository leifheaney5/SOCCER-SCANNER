/**
 * Single source of truth for timezone-aware date and time behaviour.
 *
 * Every fixture time, calendar-day membership decision, refresh boundary and
 * share link must go through this module. Formatting with the host's implicit
 * zone (a bare `toLocaleTimeString()`) is a defect: the selected timezone has
 * to control both the displayed clock time and which calendar day a fixture
 * belongs to.
 */

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

export const DEFAULT_TIME_ZONE = 'UTC';

export function isSupportedTimeZone(timeZone) {
    if (typeof timeZone !== 'string' || timeZone.trim() === '') return false;
    try {
        new Intl.DateTimeFormat('en-US', {timeZone});
        return true;
    } catch {
        return false;
    }
}

export function browserTimeZone() {
    try {
        const resolved = new Intl.DateTimeFormat().resolvedOptions().timeZone;
        return isSupportedTimeZone(resolved) ? resolved : DEFAULT_TIME_ZONE;
    } catch {
        return DEFAULT_TIME_ZONE;
    }
}

/**
 * Pick the first usable zone from an explicit request then a fallback, so an
 * invalid or hostile URL parameter can never leave the app without a zone.
 */
export function resolveTimeZone(requested, fallback = DEFAULT_TIME_ZONE) {
    if (isSupportedTimeZone(requested)) return requested;
    if (isSupportedTimeZone(fallback)) return fallback;
    return DEFAULT_TIME_ZONE;
}

function toInstant(value) {
    if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
    if (typeof value === 'number') {
        const fromNumber = new Date(value);
        return Number.isNaN(fromNumber.getTime()) ? null : fromNumber;
    }
    if (typeof value !== 'string' || value.trim() === '') return null;
    // A bare calendar day has no instant of its own; anchor it at noon UTC so
    // it cannot drift into an adjacent day in any real-world zone.
    const raw = DATE_ONLY.test(value) ? `${value}T12:00:00Z` : value;
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function zonedParts(date, timeZone) {
    const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone,
        hour12: false,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
    const parts = {};
    for (const part of formatter.formatToParts(date)) parts[part.type] = part.value;
    return parts;
}

/** Minutes the zone is offset from UTC at this instant (DST-aware). */
export function zoneOffsetMinutes(value, timeZone) {
    const date = toInstant(value);
    const zone = resolveTimeZone(timeZone);
    if (date === null) return 0;
    const parts = zonedParts(date, zone);
    const hour = Number(parts.hour) === 24 ? 0 : Number(parts.hour);
    const asUtc = Date.UTC(
        Number(parts.year),
        Number(parts.month) - 1,
        Number(parts.day),
        hour,
        Number(parts.minute),
        Number(parts.second),
    );
    return Math.round((asUtc - date.getTime()) / 60000);
}

/**
 * The `YYYY-MM-DD` calendar day an instant falls on *in the selected zone*.
 * This is the date-membership primitive the dashboard, calendar and refresh
 * scheduler must agree on.
 */
export function calendarDateInZone(value, timeZone) {
    const date = toInstant(value);
    const zone = resolveTimeZone(timeZone);
    if (date === null) return null;
    const parts = zonedParts(date, zone);
    return `${parts.year}-${parts.month}-${parts.day}`;
}

/** Today's calendar day in the selected zone, for a supplied or current instant. */
export function todayInZone(timeZone, now = new Date()) {
    return calendarDateInZone(now, timeZone);
}

export function formatKickoff(value, timeZone, options = {}) {
    const date = toInstant(value);
    const zone = resolveTimeZone(timeZone);
    if (date === null) return 'Time TBC';
    return new Intl.DateTimeFormat('en-US', {
        timeZone: zone,
        hour: '2-digit',
        minute: '2-digit',
        ...options,
    }).format(date);
}

export function formatFixtureDate(value, timeZone, options = {}) {
    const date = toInstant(value);
    const zone = resolveTimeZone(timeZone);
    if (date === null) return 'Selected date';
    // A bare calendar day is already zone-independent once anchored at noon
    // UTC; rendering it in the selected zone would reintroduce the drift.
    const renderZone = typeof value === 'string' && DATE_ONLY.test(value) ? 'UTC' : zone;
    return new Intl.DateTimeFormat('en-US', {
        timeZone: renderZone,
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        ...options,
    }).format(date);
}

export function formatDateTime(value, timeZone, options = {}) {
    const date = toInstant(value);
    const zone = resolveTimeZone(timeZone);
    if (date === null) return 'Unavailable';
    return new Intl.DateTimeFormat('en-US', {
        timeZone: zone,
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        ...options,
    }).format(date);
}

function offsetLabel(offsetMinutes) {
    const sign = offsetMinutes < 0 ? '-' : '+';
    const total = Math.abs(offsetMinutes);
    const hours = String(Math.floor(total / 60)).padStart(2, '0');
    const minutes = String(total % 60).padStart(2, '0');
    return `UTC${sign}${hours}:${minutes}`;
}

/**
 * Descriptor used by the header control and the accessible name: the zone,
 * its current abbreviation (EDT/EST/JST/…) and its current UTC offset.
 */
export function formatTimezoneLabel(timeZone, now = new Date()) {
    const zone = resolveTimeZone(timeZone);
    const date = toInstant(now) ?? new Date();
    let abbreviation = zone;
    try {
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: zone,
            timeZoneName: 'short',
        }).formatToParts(date);
        abbreviation = parts.find(part => part.type === 'timeZoneName')?.value ?? zone;
    } catch {
        abbreviation = zone;
    }
    const offsetMinutes = zoneOffsetMinutes(date, zone);
    return {
        timeZone: zone,
        abbreviation,
        offsetMinutes,
        offsetLabel: offsetLabel(offsetMinutes),
        label: `${zone} · ${abbreviation}`,
        shortLabel: abbreviation,
        accessibleName: `Timezone ${zone}, ${abbreviation}, ${offsetLabel(offsetMinutes)}`,
    };
}

/** Selectable IANA zones, sorted, with UTC and the browser zone guaranteed present. */
export function supportedTimeZones() {
    let zones = [];
    try {
        zones = typeof Intl.supportedValuesOf === 'function'
            ? Intl.supportedValuesOf('timeZone')
            : [];
    } catch {
        zones = [];
    }
    const unique = new Set(zones.filter(isSupportedTimeZone));
    unique.add('UTC');
    unique.add(browserTimeZone());
    return [...unique].sort();
}
