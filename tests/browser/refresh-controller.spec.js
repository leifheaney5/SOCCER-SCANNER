import {expect, test} from '@playwright/test';

test.beforeEach(async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({state: 'empty_confirmed', date: '2026-08-03', matches: []}),
    }));
    await page.goto('/?date=2026-08-03');
    // fixtures.js resolves its dynamic-import module graph (top-level await)
    // after the browser's `load` event fires, so the app's own initial
    // fetch(/api/v2/fixtures) can still be in flight when this beforeEach
    // returns. Tests that navigate again (e.g. to install a different route
    // mock) would otherwise race that lingering request against their own
    // page's initial load, letting the stale request steal a response meant
    // for the fresh page. Wait for the initial render to actually finish so
    // no request from this page is left in flight.
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
});

test('refresh cadence follows fixture urgency and avoids polling historical dates', async ({page}) => {
    const delays = await page.evaluate(async () => {
        const {computeRefreshDelay} = await import('/static/js/refresh-controller.js');
        const now = new Date('2026-08-03T12:00:00Z');
        return {
            live: computeRefreshDelay({date: '2026-08-03', now, matches: [{status: {code: 'in_progress'}}]}),
            preKickoff: computeRefreshDelay({date: '2026-08-03', now, matches: [{status: 'SCHEDULED', utcDate: '2026-08-03T12:10:00Z'}]}),
            upcoming: computeRefreshDelay({date: '2026-08-03', now, matches: [{status: 'SCHEDULED', utcDate: '2026-08-03T18:00:00Z'}]}),
            quietToday: computeRefreshDelay({date: '2026-08-03', now, matches: []}),
            historical: computeRefreshDelay({date: '2026-08-02', now, matches: [{status: 'FINISHED'}]}),
        };
    });

    expect(delays).toEqual({live: 30_000, preKickoff: 60_000, upcoming: 300_000, quietToday: 900_000, historical: null});
});

test('controller pauses while hidden, prevents overlap, and honors retry delay', async ({page}) => {
    const result = await page.evaluate(async () => {
        const {createRefreshController} = await import('/static/js/refresh-controller.js');
        const scheduled = [];
        const cleared = [];
        const listeners = {};
        const documentRef = {
            hidden: false,
            addEventListener: (name, callback) => { listeners[name] = callback; },
            removeEventListener: name => { delete listeners[name]; },
        };
        let resolveLoad;
        let calls = 0;
        const controller = createRefreshController({
            load: () => {
                calls += 1;
                return new Promise(resolve => { resolveLoad = resolve; });
            },
            getContext: () => ({date: '2026-08-03', matches: [{status: 'LIVE'}]}),
            documentRef,
            setTimeoutFn: (callback, delay) => {
                scheduled.push({callback, delay});
                return scheduled.length;
            },
            clearTimeoutFn: timer => cleared.push(timer),
            now: () => new Date('2026-08-03T12:00:00Z'),
        });
        controller.start();
        const firstDelay = scheduled.at(-1).delay;
        const first = controller.refresh('manual');
        const overlap = controller.refresh('manual');
        resolveLoad({ok: false, retryAfterMs: 42_000});
        await Promise.all([first, overlap]);
        const retryDelay = scheduled.at(-1).delay;
        documentRef.hidden = true;
        listeners.visibilitychange();
        const countWhenHidden = scheduled.length;
        documentRef.hidden = false;
        listeners.visibilitychange();
        resolveLoad({ok: true});
        await Promise.resolve();
        controller.destroy();
        return {firstDelay, retryDelay, calls, countWhenHidden, finalCount: scheduled.length, cleared: cleared.length};
    });

    expect(result.firstDelay).toBe(30_000);
    expect(result.retryDelay).toBe(42_000);
    expect(result.calls).toBe(2);
    expect(result.finalCount).toBeGreaterThan(result.countWhenHidden);
    expect(result.cleared).toBeGreaterThan(0);
});

test('manual refresh preserves loaded fixtures and classifies a rate limit', async ({page}) => {
    await page.unroute('**/api/v2/fixtures**');
    let attempts = 0;
    await page.route('**/api/v2/fixtures**', route => {
        attempts += 1;
        if (attempts === 1) {
            return route.fulfill({
                contentType: 'application/json',
                body: JSON.stringify({
                    state: 'success',
                    date: '2026-08-03',
                    matches: [{
                        canonicalFixtureId: 'preserved-fixture',
                        utcDate: '2026-08-03T18:00:00Z',
                        status: 'SCHEDULED',
                        homeTeam: {name: 'Preserved United'},
                        awayTeam: {name: 'Steady City'},
                        competition: {name: 'Test League'},
                    }],
                }),
            });
        }
        return route.fulfill({
            status: 429,
            headers: {'Retry-After': '42'},
            contentType: 'application/json',
            body: JSON.stringify({error: {code: 'rate_limited', retryAfterSeconds: 42}}),
        });
    });

    await page.goto('/?date=2026-08-03');
    await expect(page.getByText('Preserved United').first()).toBeVisible();
    await page.locator('#refresh-fixtures').click();

    await expect(page.getByText('Preserved United').first()).toBeVisible();
    await expect(page.locator('#data-notice')).toContainText('Live update delayed');
    await expect(page.locator('#dashboard-status')).toContainText('showing previous fixtures');
    expect(attempts).toBe(2);
});
