/**
 * Canonical match-status taxonomy.
 *
 * Previously each module kept its own ad-hoc `LIVE_STATUSES` set, which made
 * half time, extra time and penalties render as generic "LIVE", treated an
 * abandoned match as upcoming, kept polling terminal fixtures, and cached
 * in-flight matches into the offline snapshot. Every consumer — renderer,
 * state, refresh controller and offline cache — now resolves behaviour here.
 */

const status = (key, label, shortLabel, group, flags) => ({
    key,
    label,
    shortLabel,
    group,
    ...flags,
});

export const MATCH_STATUSES = {
    scheduled: status('scheduled', 'Scheduled', 'SCHEDULED', 'upcoming', {
        active: false,
        terminal: false,
        refresh: false,
        scoreAvailable: false,
        offlineEligible: true,
        tone: 'neutral',
        description: 'Kick-off has not started yet.',
    }),
    delayed: status('delayed', 'Delayed', 'DELAYED', 'upcoming', {
        active: false,
        terminal: false,
        refresh: true,
        scoreAvailable: false,
        offlineEligible: false,
        tone: 'warning',
        description: 'Kick-off is delayed and the start time may change.',
    }),
    in_progress: status('in_progress', 'Live', 'LIVE', 'active', {
        active: true,
        terminal: false,
        refresh: true,
        scoreAvailable: true,
        offlineEligible: false,
        tone: 'live',
        description: 'The match is being played right now.',
    }),
    first_half: status('first_half', 'First half', '1H', 'active', {
        active: true, terminal: false, refresh: true, scoreAvailable: true,
        offlineEligible: false, tone: 'live', description: 'The first half is in progress.',
    }),
    second_half: status('second_half', 'Second half', '2H', 'active', {
        active: true, terminal: false, refresh: true, scoreAvailable: true,
        offlineEligible: false, tone: 'live', description: 'The second half is in progress.',
    }),
    half_time: status('half_time', 'Half time', 'HT', 'active', {
        active: true,
        terminal: false,
        refresh: true,
        scoreAvailable: true,
        offlineEligible: false,
        tone: 'live',
        description: 'The match is paused at half time.',
    }),
    extra_time: status('extra_time', 'Extra time', 'ET', 'active', {
        active: true,
        terminal: false,
        refresh: true,
        scoreAvailable: true,
        offlineEligible: false,
        tone: 'live',
        description: 'The match is in extra time.',
    }),
    penalties: status('penalties', 'Penalty shootout', 'PEN', 'active', {
        active: true,
        terminal: false,
        refresh: true,
        scoreAvailable: true,
        offlineEligible: false,
        tone: 'live',
        description: 'The match is being decided by a penalty shootout.',
    }),
    finished_extra_time: status('finished_extra_time', 'Full time after extra time', 'AET', 'finished', {
        active: false, terminal: true, refresh: false, scoreAvailable: true,
        offlineEligible: true, tone: 'settled', description: 'The match finished after extra time.',
    }),
    finished_penalties: status('finished_penalties', 'Full time after penalties', 'PEN FT', 'finished', {
        active: false, terminal: true, refresh: false, scoreAvailable: true,
        offlineEligible: true, tone: 'settled', description: 'The match finished after a penalty shootout.',
    }),
    finished: status('finished', 'Full time', 'FT', 'finished', {
        active: false,
        terminal: true,
        refresh: false,
        scoreAvailable: true,
        offlineEligible: true,
        tone: 'settled',
        description: 'The match has finished.',
    }),
    postponed: status('postponed', 'Postponed', 'POSTPONED', 'exception', {
        active: false,
        terminal: true,
        refresh: false,
        scoreAvailable: false,
        offlineEligible: true,
        tone: 'warning',
        description: 'The match was postponed and will be rescheduled.',
    }),
    cancelled: status('cancelled', 'Cancelled', 'CANCELLED', 'exception', {
        active: false,
        terminal: true,
        refresh: false,
        scoreAvailable: false,
        offlineEligible: true,
        tone: 'warning',
        description: 'The match was cancelled and will not be played.',
    }),
    suspended: status('suspended', 'Suspended', 'SUSPENDED', 'exception', {
        // Suspended play can resume, so it stays active for refresh purposes
        // and must never be frozen into an offline snapshot.
        active: true,
        terminal: false,
        refresh: true,
        scoreAvailable: true,
        offlineEligible: false,
        tone: 'warning',
        description: 'The match is suspended and may resume.',
    }),
    abandoned: status('abandoned', 'Abandoned', 'ABANDONED', 'exception', {
        active: false,
        terminal: true,
        refresh: false,
        scoreAvailable: true,
        offlineEligible: true,
        tone: 'warning',
        description: 'The match was abandoned before completion.',
    }),
    unknown: status('unknown', 'Status unavailable', 'UNKNOWN', 'unknown', {
        active: false,
        terminal: false,
        refresh: true,
        scoreAvailable: false,
        offlineEligible: false,
        tone: 'neutral',
        description: 'The provider did not report a usable status.',
    }),
};

/** Provider vocabulary → canonical key. Unmapped codes become `unknown`. */
const PROVIDER_CODES = new Map(Object.entries({
    SCHEDULED: 'scheduled',
    TIMED: 'scheduled',
    NOT_STARTED: 'scheduled',
    PRE: 'scheduled',
    UPCOMING: 'scheduled',
    DELAYED: 'delayed',
    LIVE: 'in_progress',
    IN_PLAY: 'in_progress',
    IN_PROGRESS: 'in_progress',
    FIRST_HALF: 'first_half',
    SECOND_HALF: 'second_half',
    PAUSED: 'half_time',
    HALFTIME: 'half_time',
    HALF_TIME: 'half_time',
    HT: 'half_time',
    EXTRA_TIME: 'extra_time',
    EXTRATIME: 'extra_time',
    ET: 'extra_time',
    PENALTIES: 'penalties',
    PENALTY_SHOOTOUT: 'penalties',
    PEN: 'penalties',
    FINISHED_AFTER_EXTRA_TIME: 'finished_extra_time',
    FINISHED_EXTRA_TIME: 'finished_extra_time',
    AET: 'finished_extra_time',
    FINISHED_AFTER_PENALTIES: 'finished_penalties',
    FINISHED_PENALTIES: 'finished_penalties',
    PENALTY_FINISHED: 'finished_penalties',
    FINISHED: 'finished',
    FULL_TIME: 'finished',
    AWARDED: 'finished',
    POST: 'finished',
    POSTPONED: 'postponed',
    CANCELLED: 'cancelled',
    CANCELED: 'cancelled',
    SUSPENDED: 'suspended',
    ABANDONED: 'abandoned',
}));

export function rawStatusCode(match) {
    const value = match?.status;
    const code = value && typeof value === 'object' ? value.code : value;
    if (code === undefined || code === null || String(code).trim() === '') return 'SCHEDULED';
    const normalizedCode = String(code).trim().toUpperCase().replace(/[\s-]+/g, '_');
    const raw = value && typeof value === 'object' ? value.raw : null;
    const normalizedRaw = String(raw || '').trim().toUpperCase().replace(/[\s-]+/g, '_');
    if (normalizedCode === 'IN_PROGRESS' && normalizedRaw.startsWith('STATUS_')) {
        const rawCode = normalizedRaw.slice('STATUS_'.length);
        if (PROVIDER_CODES.has(rawCode)) return rawCode;
    }
    return normalizedCode;
}

export function resolveStatus(match) {
    return PROVIDER_CODES.get(rawStatusCode(match)) ?? 'unknown';
}

export function statusDefinition(match) {
    return MATCH_STATUSES[resolveStatus(match)];
}

export function statusLabel(match) {
    return statusDefinition(match).label;
}

export function statusShortLabel(match) {
    return statusDefinition(match).shortLabel;
}

export function statusGroup(match) {
    return statusDefinition(match).group;
}

export function describeStatus(match) {
    return statusDefinition(match).description;
}

export function isActiveStatus(match) {
    return statusDefinition(match).active;
}

export function isTerminalStatus(match) {
    return statusDefinition(match).terminal;
}

export function shouldRefresh(match) {
    return statusDefinition(match).refresh;
}

export function hasScore(match) {
    return statusDefinition(match).scoreAvailable;
}

/**
 * Offline snapshots must exclude anything that can still change, otherwise a
 * cached extra-time or penalty score is served as if it were final.
 */
export function isOfflineEligible(match) {
    return statusDefinition(match).offlineEligible;
}

/** Coarse bucket used by the status filter control. */
export function statusFilterKind(match) {
    const definition = statusDefinition(match);
    if (definition.active) return 'live';
    if (definition.group === 'finished') return 'finished';
    if (definition.group === 'exception') return definition.key;
    return 'upcoming';
}
