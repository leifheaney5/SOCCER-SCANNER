export const SCORE_STORAGE_KEY = 'soccer-scanner:reveal-scores';
export const DEFAULT_REVEAL_SCORES = false;
const SVG_NAMESPACE = 'http://www.w3.org/2000/svg';

const SCORE_ICONS = {
    eye: [
        ['path', {d: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z'}],
        ['circle', {cx: '12', cy: '12', r: '3'}],
    ],
    'eye-off': [
        ['path', {d: 'M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 4.2A10.7 10.7 0 0 1 12 4c5.5 0 9 5.2 9 5.2a15 15 0 0 1-2.1 2.6M6.6 6.6C4.4 8 3 10 3 10s3.5 5 9 5c1.2 0 2.3-.2 3.3-.6'}],
    ],
};

function syncScoreIcon(button, revealed) {
    const icon = button.querySelector('svg');
    if (!icon) return;

    const iconName = revealed ? 'eye' : 'eye-off';
    const shapes = SCORE_ICONS[iconName].map(([tagName, attributes]) => {
        const shape = document.createElementNS(SVG_NAMESPACE, tagName);
        for (const [name, value] of Object.entries(attributes)) shape.setAttribute(name, value);
        return shape;
    });
    icon.dataset.icon = iconName;
    icon.replaceChildren(...shapes);
}

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
    syncScoreIcon(button, revealed);
    const text = button.querySelector('[data-score-toggle-label]');
    if (text) text.textContent = label;
}
