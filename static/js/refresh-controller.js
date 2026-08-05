const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [statusModule, timeZoneModule] = await Promise.all([
    import(versionedModule('./match-status.js')),
    import(versionedModule('./time-zone.js')),
]);
const {isActiveStatus, isTerminalStatus} = statusModule;
const {todayInZone} = timeZoneModule;

/**
 * Refresh cadence for the current view.
 *
 * "Today" is resolved in the selected timezone so a viewer east or west of the
 * host does not stop refreshing the day they are actually looking at. Terminal
 * statuses stop polling; suspended matches keep polling because play can
 * resume.
 */
export function computeRefreshDelay({matches = [], date, now = new Date(), timezone = 'UTC'} = {}) {
    const today = todayInZone(timezone, now);
    if (date && date < today) return null;
    if (matches.some(isActiveStatus)) return 30_000;

    const upcoming = matches
        .filter(match => !isTerminalStatus(match))
        .map(match => new Date(match?.utcDate).getTime())
        .filter(value => Number.isFinite(value) && value >= now.getTime());
    if (upcoming.some(value => value - now.getTime() <= 15 * 60_000)) return 60_000;
    if (upcoming.length) return 300_000;
    return date === today ? 900_000 : null;
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
