const LIVE_STATUSES = new Set(['LIVE', 'IN_PLAY', 'IN_PROGRESS', 'PAUSED', 'HALFTIME', 'HALF_TIME', 'EXTRA_TIME', 'PENALTIES']);
const FINISHED_STATUSES = new Set(['FINISHED', 'AWARDED']);
const EXCEPTION_STATUSES = new Map([
    ['POSTPONED', 'postponed'],
    ['CANCELLED', 'cancelled'],
    ['CANCELED', 'cancelled'],
    ['SUSPENDED', 'suspended'],
]);
const FILTER_STATUSES = new Set(['all', 'live', 'upcoming', 'finished']);

export function todayLocal(now = new Date()) {
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

export function shiftDate(value, amount) {
    const date = new Date(`${value}T12:00:00`);
    if (Number.isNaN(date.getTime())) return todayLocal();
    date.setDate(date.getDate() + amount);
    return todayLocal(date);
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
    const status = match?.status;
    return String((status && typeof status === 'object' ? status.code : status) || 'scheduled').toUpperCase();
}

export function statusKind(match) {
    const status = statusValue(match);
    if (LIVE_STATUSES.has(status)) return 'live';
    if (FINISHED_STATUSES.has(status)) return 'finished';
    return EXCEPTION_STATUSES.get(status) || 'upcoming';
}

export function createState(search = '', defaultTimezone = 'UTC') {
    const params = new URLSearchParams(search);
    const rawStatus = params.get('status') || 'all';
    const rawDate = params.get('date') || todayLocal();
    const rawTimezone = params.get('timezone') || defaultTimezone;
    const state = {
        date: isValidDate(rawDate) ? rawDate : todayLocal(),
        dateError: params.has('date') && !isValidDate(rawDate),
        timezone: isValidTimezone(rawTimezone) ? rawTimezone : (isValidTimezone(defaultTimezone) ? defaultTimezone : 'UTC'),
        competition: params.get('competition') || '',
        status: FILTER_STATUSES.has(rawStatus) ? rawStatus : 'all',
        query: params.get('q') || '',
        set(patch) {
            Object.assign(this, patch);
            return this;
        },
        toSearchParams() {
            const next = new URLSearchParams();
            next.set('date', this.date);
            next.set('timezone', this.timezone);
            if (this.competition) next.set('competition', this.competition);
            if (this.status !== 'all') next.set('status', this.status);
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
        const searchable = [
            match?.homeTeam?.name,
            match?.awayTeam?.name,
            competitionName,
        ].filter(Boolean).join(' ');
        const normalizedSearchable = normalizeSearch(searchable);
        return (!state.competition || competitionName === state.competition)
            && (state.status === 'all' || statusKind(match) === state.status)
            && (!query || normalizedSearchable.includes(query));
    });
}

export function groupMatches(matches) {
    const groups = new Map();
    for (const match of Array.isArray(matches) ? matches : []) {
        const competition = match?.competition || {};
        const key = String(competition.canonicalId || competition.id || competition.name || 'other');
        if (!groups.has(key)) groups.set(key, {key, competition, matches: []});
        groups.get(key).matches.push(match);
    }
    return [...groups.values()].map(group => ({
        ...group,
        matches: group.matches.sort((left, right) => (
            String(left?.utcDate || '').localeCompare(String(right?.utcDate || ''))
        )),
    }));
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
    return list.find(match => statusKind(match) === 'live')
        || list.find(match => statusKind(match) === 'upcoming')
        || list.find(match => statusKind(match) === 'finished')
        || null;
}
