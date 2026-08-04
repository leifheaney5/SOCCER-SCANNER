const SCORE_KEYS = new Set([
    'score',
    'scores',
    'homescore',
    'awayscore',
    'displayvalue',
]);

function statusTokens(match) {
    const status = match?.status;
    if (status && typeof status === 'object') {
        return [status.code, status.raw, status.type, status.name]
            .filter(Boolean)
            .map(value => String(value).toLocaleLowerCase());
    }
    return [String(status || '').toLocaleLowerCase()];
}

export function isLiveFixture(match) {
    return statusTokens(match).some(value => (
        value.includes('live')
        || value.includes('progress')
        || value.includes('half')
        || value.includes('paused')
    ));
}

function withoutScores(value) {
    if (Array.isArray(value)) return value.map(withoutScores);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(
        Object.entries(value)
            .filter(([key]) => !SCORE_KEYS.has(key.toLocaleLowerCase()))
            .map(([key, nested]) => [key, withoutScores(nested)]),
    );
}

export function sanitizeFixturePayload(payload, cachedAt = new Date().toISOString()) {
    const clean = withoutScores(payload || {});
    const matches = Array.isArray(clean.matches)
        ? clean.matches.filter(match => !isLiveFixture(match))
        : [];
    return {
        ...clean,
        matches,
        total_matches: matches.length,
        totalMatches: matches.length,
        stale: true,
        partial: true,
        offline: true,
        offlineCachedAt: cachedAt,
    };
}
