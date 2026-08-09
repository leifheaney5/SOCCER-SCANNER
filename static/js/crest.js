const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'data:']);

function initials(name) {
    const words = String(name || '?').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    const letters = words.length === 1
        ? [...words[0]].slice(0, 2)
        : [[...words[0]][0], [...words.at(-1)][0]];
    return letters.join('').toLocaleUpperCase();
}

function safeImageUrl(value, {allowLocal = false} = {}) {
    if (!value) return null;
    try {
        const rawValue = String(value).trim();
        const url = new URL(rawValue, window.location.origin);
        if (!SAFE_PROTOCOLS.has(url.protocol)) return null;
        if (
            url.origin === window.location.origin
            && url.protocol !== 'data:'
            && (!allowLocal || !url.pathname.startsWith('/static/'))
        ) return null;
        return url.href;
    } catch {
        return null;
    }
}

export function createCrest(team, {
    size = 32,
    lazy = true,
    className = '',
    allowLocal = false,
} = {}) {
    const wrapper = document.createElement('span');
    wrapper.className = ['team-crest', className].filter(Boolean).join(' ');
    wrapper.setAttribute('aria-hidden', 'true');

    const renderFallback = () => {
        const fallback = document.createElement('span');
        fallback.className = 'crest-fallback';
        fallback.textContent = initials(team?.name);
        wrapper.replaceChildren(fallback);
    };

    const src = safeImageUrl(team?.crest, {allowLocal});
    if (!src) {
        renderFallback();
        return wrapper;
    }

    const image = document.createElement('img');
    image.className = 'team-crest-image';
    image.src = src;
    image.alt = '';
    image.width = size;
    image.height = size;
    image.decoding = 'async';
    if (lazy) image.loading = 'lazy';
    image.addEventListener('error', renderFallback, {once: true});
    wrapper.append(image);
    return wrapper;
}
