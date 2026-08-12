const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [statusModule, timeZoneModule] = await Promise.all([
    import(versionedModule('./match-status.js')),
    import(versionedModule('./time-zone.js')),
]);
const {statusFilterKind, rawStatusCode} = statusModule;
const {calendarDateInZone, resolveTimeZone, todayInZone} = timeZoneModule;

const FILTER_STATUSES = new Set(['all', 'live', 'upcoming', 'finished']);
const SORT_VALUES = new Set(['kickoff', 'competition', 'live', 'recommended']);
const TIME_WINDOWS = new Set(['all', 'morning', 'afternoon', 'evening', 'late-night']);

/** Today in the selected zone — not the host's zone. */
export function todayLocal(now = new Date(), timezone = undefined) {
    return todayInZone(resolveTimeZone(timezone, browserFallback()), now);
}

function browserFallback() {
    try {
        return new Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
        return 'UTC';
    }
}

export function shiftDate(value, amount, timezone = undefined) {
    // Step whole days at noon UTC so a DST transition cannot skip or repeat
    // a calendar day.
    const date = new Date(`${value}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) return todayLocal(new Date(), timezone);
    date.setUTCDate(date.getUTCDate() + amount);
    return calendarDateInZone(date, 'UTC');
}

export function buildDateTabs(selectedDate) {
    const formatter = new Intl.DateTimeFormat('en-US', {weekday: 'short', month: 'short', day: 'numeric'});
    const today = todayLocal(new Date(), 'UTC');
    return [-2, -1, 0, 1, 2].map(offset => {
        const date = shiftDate(selectedDate, offset, 'UTC');
        const label = date === today ? 'Today'
            : date === shiftDate(today, -1, 'UTC') ? 'Yesterday'
                : date === shiftDate(today, 1, 'UTC') ? 'Tomorrow'
                    : formatter.format(new Date(`${date}T12:00:00Z`));
        return {date, label, shortLabel: formatter.format(new Date(`${date}T12:00:00Z`))};
    });
}

export function isValidDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ''))) return false;
    const [year, month, day] = value.split('-').map(Number);
    const candidate = new Date(Date.UTC(year, month - 1, day, 12));
    return candidate.getUTCFullYear() === year
        && candidate.getUTCMonth() === month - 1
        && candidate.getUTCDate() === day;
}

export function isValidTimezone(value) {
    try {
        new Intl.DateTimeFormat('en-US', {timeZone: value}).format();
        return Boolean(value);
    } catch {
        return false;
    }
}

export function statusValue(match) {
    return rawStatusCode(match);
}

/** Delegated to the canonical taxonomy so every module agrees. */
export function statusKind(match) {
    return statusFilterKind(match);
}

export function createState(search = '', defaultTimezone = 'UTC') {
    const params = new URLSearchParams(search);
    const rawStatus = params.get('status') || 'all';
    // The timezone must be resolved before it is used to pick "today", or
    // the default date silently falls back to the host's zone instead of
    // the selected one.
    const rawTimezone = params.get('timezone') || defaultTimezone;
    const resolvedTimezone = isValidTimezone(rawTimezone)
        ? rawTimezone
        : (isValidTimezone(defaultTimezone) ? defaultTimezone : 'UTC');
    const rawDate = params.get('date') || todayLocal(new Date(), resolvedTimezone);
    const state = {
        date: isValidDate(rawDate) ? rawDate : todayLocal(new Date(), resolvedTimezone),
        dateError: params.has('date') && !isValidDate(rawDate),
        timezone: resolvedTimezone,
        competition: params.get('competition') || '',
        country: params.get('country') || '',
        status: FILTER_STATUSES.has(rawStatus) ? rawStatus : 'all',
        sort: SORT_VALUES.has(params.get('sort')) ? params.get('sort') : 'kickoff',
        timeWindow: TIME_WINDOWS.has(params.get('time')) ? params.get('time') : 'all',
        hideFinished: params.get('hideFinished') === '1',
        fixture: (params.get('fixture') || '').slice(0, 120),
        query: params.get('q') || '',
        toSearchParams() {
            const next = new URLSearchParams();
            next.set('date', this.date);
            next.set('timezone', this.timezone);
            if (this.competition) next.set('competition', this.competition);
            if (this.country) next.set('country', this.country);
            if (this.status !== 'all') next.set('status', this.status);
            if (this.sort !== 'kickoff') next.set('sort', this.sort);
            if (this.timeWindow !== 'all') next.set('time', this.timeWindow);
            if (this.hideFinished) next.set('hideFinished', '1');
            if (this.fixture) next.set('fixture', this.fixture);
            if (this.query) next.set('q', this.query);
            return next;
        },
    };
    return state;
}

export function filterMatches(matches, state) {
    const normalizeSearch = value => String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase();
    const query = normalizeSearch(state.query.trim());
    return (Array.isArray(matches) ? matches : []).filter(match => {
        const competitionName = match?.competition?.name || '';
        const country = match?.competition?.area?.name || '';
        const searchable = [
            match?.homeTeam?.name,
            match?.awayTeam?.name,
            competitionName,
        ].filter(Boolean).join(' ');
        const normalizedSearchable = normalizeSearch(searchable);
        let hour = null;
        try {
            const parts = new Intl.DateTimeFormat('en-GB', {
                timeZone: state.timezone,
                hour: '2-digit',
                hourCycle: 'h23',
            }).formatToParts(new Date(match?.utcDate));
            hour = Number(parts.find(part => part.type === 'hour')?.value);
        } catch {
            hour = null;
        }
        const inTimeWindow = state.timeWindow === 'all'
            || (state.timeWindow === 'morning' && hour >= 6 && hour < 12)
            || (state.timeWindow === 'afternoon' && hour >= 12 && hour < 18)
            || (state.timeWindow === 'evening' && hour >= 18 && hour < 24)
            || (state.timeWindow === 'late-night' && hour >= 0 && hour < 6);
        return (!state.competition || competitionName === state.competition)
            && (!state.country || country === state.country)
            && (state.status === 'all' || statusKind(match) === state.status)
            && (!state.hideFinished || statusKind(match) !== 'finished')
            && inTimeWindow
            && (!query || normalizedSearchable.includes(query));
    });
}

export function sortMatches(matches, sort = 'kickoff') {
    const list = [...(Array.isArray(matches) ? matches : [])];
    const kickoff = match => String(match?.utcDate || '');
    const stableId = match => String(match?.canonicalFixtureId || match?.id || '');
    const rank = match => ({live: 0, upcoming: 1, finished: 2}[statusKind(match)] ?? 3);
    return list.sort((left, right) => {
        if (sort === 'competition') {
            return String(left?.competition?.name || '').localeCompare(String(right?.competition?.name || ''))
                || kickoff(left).localeCompare(kickoff(right))
                || stableId(left).localeCompare(stableId(right));
        }
        if (sort === 'live') {
            return rank(left) - rank(right)
                || kickoff(left).localeCompare(kickoff(right))
                || stableId(left).localeCompare(stableId(right));
        }
        if (sort === 'recommended') {
            return Number(right?.interestEstimate || 0) - Number(left?.interestEstimate || 0)
                || kickoff(left).localeCompare(kickoff(right))
                || stableId(left).localeCompare(stableId(right));
        }
        return kickoff(left).localeCompare(kickoff(right))
            || stableId(left).localeCompare(stableId(right));
    });
}

/**
 * Group by competition while preserving the caller's chosen ordering.
 *
 * Grouping previously re-sorted every group by kickoff, which silently
 * discarded the selected sort. Insertion order now carries the sort through,
 * and group order follows the sort too.
 */
export function groupMatches(matches, sort = 'kickoff') {
    const groups = new Map();
    for (const match of Array.isArray(matches) ? matches : []) {
        const competition = match?.competition || {};
        const key = String(competition.canonicalId || competition.id || competition.name || 'other');
        if (!groups.has(key)) groups.set(key, {key, competition, matches: []});
        groups.get(key).matches.push(match);
    }
    const ordered = [...groups.values()];
    if (sort === 'competition') {
        ordered.sort((left, right) => String(left.competition?.name || '')
            .localeCompare(String(right.competition?.name || '')));
    }
    // For every other sort the first fixture in each group already reflects
    // the chosen ordering, so ranking groups by their leader keeps the page
    // consistent with the control.
    return ordered;
}

export function summarizeMatches(matches) {
    const summary = {total: 0, live: 0, upcoming: 0, finished: 0};
    for (const match of Array.isArray(matches) ? matches : []) {
        summary.total += 1;
        const kind = statusKind(match);
        if (Object.hasOwn(summary, kind)) summary[kind] += 1;
    }
    return summary;
}

export function selectFeatured(matches) {
    const list = Array.isArray(matches) ? matches : [];
    const mostInteresting = kind => list.reduce((selected, match) => {
        if (statusKind(match) !== kind) return selected;
        const interest = Number(match?.interestEstimate ?? match?.enhanced_info?.importance_score ?? 0);
        const selectedInterest = Number(
            selected?.interestEstimate ?? selected?.enhanced_info?.importance_score ?? 0,
        );
        return !selected || interest > selectedInterest ? match : selected;
    }, null);
    return mostInteresting('live')
        || mostInteresting('upcoming')
        || mostInteresting('finished')
        || null;
}
