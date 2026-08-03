export const SCORE_STORAGE_KEY = 'soccer-scanner:reveal-scores';
export const DEFAULT_REVEAL_SCORES = false;

export function readScorePreference(storage = window.localStorage) {
    try {
        const stored = storage.getItem(SCORE_STORAGE_KEY);
        return stored === null ? DEFAULT_REVEAL_SCORES : stored === 'true';
    } catch {
        return DEFAULT_REVEAL_SCORES;
    }
}

export function writeScorePreference(storage = window.localStorage, revealed) {
    try {
        storage.setItem(SCORE_STORAGE_KEY, String(Boolean(revealed)));
    } catch {
        // The visible state still works when storage is unavailable.
    }
}

export function validScore(match) {
    const fullTime = match?.score?.fullTime;
    const home = fullTime?.home;
    const away = fullTime?.away;
    const isValue = value => (typeof value === 'number' && Number.isFinite(value))
        || (typeof value === 'string' && /^\d+$/.test(value));
    return isValue(home) && isValue(away) ? {home: String(home), away: String(away)} : null;
}

export function syncScoreToggle(button, revealed) {
    const label = revealed ? 'Hide scores' : 'Reveal scores';
    button.setAttribute('aria-pressed', String(Boolean(revealed)));
    button.setAttribute('aria-label', label);
    button.classList.toggle('is-active', Boolean(revealed));
    const text = button.querySelector('[data-score-toggle-label]');
    if (text) text.textContent = label;
}
