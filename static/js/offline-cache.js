import {isOfflineEligible} from './match-status.js';

const SCORE_KEYS = new Set([
    'score',
    'scores',
    'homescore',
    'awayscore',
    'displayvalue',
]);

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
    // Only statuses the canonical taxonomy marks offlineEligible are safe to
    // freeze into the snapshot. Anything still in flight — live, half time,
    // extra time, penalties, suspended, delayed, or a status the taxonomy
    // could not classify — must be excluded, or a cached in-progress score
    // is served back as if it were final.
    const matches = Array.isArray(clean.matches)
        ? clean.matches.filter(match => isOfflineEligible(match))
        : [];
    // Neither field is read by any client code, and neither can be recomputed
    // here without duplicating the server's timezone bucketing. Carrying their
    // pre-filter values into a snapshot whose match list has been filtered
    // would store something simultaneously stale and unread.
    const {matchStatistics: _statistics, featured_matches: _featured, ...rest} = clean;
    return {
        ...rest,
        matches,
        total_matches: matches.length,
        totalMatches: matches.length,
        stale: true,
        partial: true,
        offline: true,
        offlineCachedAt: cachedAt,
    };
}
