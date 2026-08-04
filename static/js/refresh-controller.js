const LIVE_CODES = new Set([
    'LIVE', 'IN_PLAY', 'IN_PROGRESS', 'PAUSED', 'HALFTIME', 'HALF_TIME',
    'EXTRA_TIME', 'PENALTIES',
]);
const FINISHED_CODES = new Set(['FINISHED', 'AWARDED', 'CANCELLED', 'CANCELED', 'POSTPONED', 'SUSPENDED']);

function statusCode(match) {
    const status = match?.status;
    return String((status && typeof status === 'object' ? status.code : status) || '').toUpperCase();
}

function localDate(now) {
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

export function computeRefreshDelay({matches = [], date, now = new Date()} = {}) {
    if (date && date < localDate(now)) return null;
    if (matches.some(match => LIVE_CODES.has(statusCode(match)))) return 30_000;

    const upcoming = matches
        .filter(match => !FINISHED_CODES.has(statusCode(match)))
        .map(match => new Date(match?.utcDate).getTime())
        .filter(value => Number.isFinite(value) && value >= now.getTime());
    if (upcoming.some(value => value - now.getTime() <= 15 * 60_000)) return 60_000;
    if (upcoming.length) return 300_000;
    return date === localDate(now) ? 900_000 : null;
}

export function createRefreshController({
    load,
    getContext,
    documentRef = document,
    setTimeoutFn = setTimeout,
    clearTimeoutFn = clearTimeout,
    now = () => new Date(),
} = {}) {
    let timer = null;
    let inFlight = null;
    let stopped = true;
    let failures = 0;

    function clear() {
        if (timer !== null) clearTimeoutFn(timer);
        timer = null;
    }

    function schedule(override = null) {
        clear();
        if (stopped || documentRef.hidden) return;
        const delay = override ?? computeRefreshDelay({...getContext(), now: now()});
        if (delay === null) return;
        timer = setTimeoutFn(() => refresh('poll'), delay);
    }

    async function refresh(reason = 'manual') {
        if (inFlight) return inFlight;
        clear();
        inFlight = Promise.resolve(load({preserve: reason !== 'initial', reason}));
        try {
            const result = await inFlight;
            if (result?.ok === false) {
                failures += 1;
                const fallback = Math.min(300_000, 5_000 * (2 ** Math.min(failures - 1, 6)));
                schedule(Number(result.retryAfterMs) || fallback);
            } else {
                failures = 0;
                schedule();
            }
            return result;
        } catch (error) {
            failures += 1;
            schedule(Number(error?.retryAfterMs) || Math.min(300_000, 5_000 * (2 ** Math.min(failures - 1, 6))));
            return {ok: false};
        } finally {
            inFlight = null;
        }
    }

    function onVisibilityChange() {
        if (documentRef.hidden) {
            clear();
        } else {
            refresh('visibility');
        }
    }

    function start({loadImmediately = false} = {}) {
        if (!stopped) return;
        stopped = false;
        documentRef.addEventListener('visibilitychange', onVisibilityChange);
        if (loadImmediately) refresh('initial');
        else schedule();
    }

    function destroy() {
        stopped = true;
        clear();
        documentRef.removeEventListener('visibilitychange', onVisibilityChange);
    }

    return {start, destroy, refresh, schedule, isRefreshing: () => Boolean(inFlight)};
}
