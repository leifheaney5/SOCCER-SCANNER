export const FAVORITES_KEY = 'soccer-scanner:favorites';
const VERSION = 1;
const KINDS = ['teams', 'competitions', 'fixtures'];
const MAX_ENTRIES = 500;
const MAX_ID_LENGTH = 120;
const MAX_IMPORT_BYTES = 100_000;

function emptyState() {
    return {version: VERSION, teams: [], competitions: [], fixtures: []};
}

function sanitize(value) {
    if (!value || value.version !== VERSION || typeof value !== 'object') return emptyState();
    const result = emptyState();
    for (const kind of KINDS) {
        if (!Array.isArray(value[kind])) continue;
        result[kind] = [...new Set(value[kind]
            .filter(item => typeof item === 'string')
            .map(item => item.trim())
            .filter(item => item && item.length <= MAX_ID_LENGTH))]
            .slice(0, MAX_ENTRIES);
    }
    return result;
}

export function createFavoritesRepository(storage) {
    function read() {
        try {
            return sanitize(JSON.parse(storage.getItem(FAVORITES_KEY) || 'null'));
        } catch {
            return emptyState();
        }
    }

    let state = read();

    function persist() {
        storage.setItem(FAVORITES_KEY, JSON.stringify(state));
        return snapshot();
    }

    function snapshot() {
        return structuredClone(state);
    }

    function toggle(kind, id) {
        if (!KINDS.includes(kind)) throw new TypeError('Unknown favorite type');
        const normalized = String(id || '').trim();
        if (!normalized || normalized.length > MAX_ID_LENGTH) return snapshot();
        const values = new Set(state[kind]);
        values.has(normalized) ? values.delete(normalized) : values.add(normalized);
        state = {...state, [kind]: [...values].slice(0, MAX_ENTRIES)};
        return persist();
    }

    function has(kind, id) {
        return KINDS.includes(kind) && state[kind].includes(String(id));
    }

    function exportText() {
        return JSON.stringify(state, null, 2);
    }

    function importText(text) {
        const source = String(text || '');
        if (new TextEncoder().encode(source).length > MAX_IMPORT_BYTES) {
            throw new RangeError('Favorites import is too large');
        }
        state = sanitize(JSON.parse(source));
        return persist();
    }

    function clear() {
        state = emptyState();
        storage.removeItem(FAVORITES_KEY);
        return snapshot();
    }

    return {snapshot, toggle, has, exportText, importText, clear};
}

export function fixtureIsFavorite(repository, match) {
    const fixtureId = String(match?.canonicalFixtureId || match?.id || '');
    const competitionId = String(match?.competition?.canonicalId || match?.competition?.id || '');
    const teamIds = [match?.homeTeam, match?.awayTeam]
        .map(team => String(team?.canonicalId || ''))
        .filter(Boolean);
    return repository.has('fixtures', fixtureId)
        || (competitionId && repository.has('competitions', competitionId))
        || teamIds.some(id => repository.has('teams', id));
}
