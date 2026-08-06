import {expect, test} from '@playwright/test';

// Two dates, each with its own fixture(s), so a date change produces a real
// history entry whose URL genuinely differs (a different `?fixture=` and a
// different `?date=`) rather than two entries that merely look alike.
const dayOnePayload = {
    state: 'success',
    date: '2026-08-03',
    matches: [
        {
            canonicalFixtureId: 'fx-arsenal',
            utcDate: '2026-08-03T18:30:00Z',
            status: 'SCHEDULED',
            homeTeam: {name: 'Arsenal'},
            awayTeam: {name: 'River Plate'},
            competition: {name: 'Premier League', area: {name: 'England'}},
        },
        {
            canonicalFixtureId: 'fx-celtic',
            utcDate: '2026-08-03T20:00:00Z',
            status: 'SCHEDULED',
            homeTeam: {name: 'Celtic'},
            awayTeam: {name: 'Dundee'},
            competition: {name: 'Scottish Premiership', area: {name: 'Scotland'}},
        },
    ],
};

const dayTwoPayload = {
    state: 'success',
    date: '2026-08-04',
    matches: [
        {
            canonicalFixtureId: 'fx-liverpool',
            utcDate: '2026-08-04T18:30:00Z',
            status: 'SCHEDULED',
            homeTeam: {name: 'Liverpool'},
            awayTeam: {name: 'Chelsea'},
            competition: {name: 'Premier League', area: {name: 'England'}},
        },
    ],
};

test.beforeEach(async ({page}) => {
    // The match-context panel (rather than the mobile dialog) only renders
    // at >=1100px, and every assertion below reads that panel.
    await page.setViewportSize({width: 1280, height: 900});
    await page.route('**/api/v2/fixtures**', route => {
        const requestedDate = new URL(route.request().url()).searchParams.get('date');
        const body = requestedDate === '2026-08-04' ? dayTwoPayload : dayOnePayload;
        return route.fulfill({contentType: 'application/json', body: JSON.stringify(body)});
    });
    await page.goto('/?date=2026-08-03');
    // fixtures.js resolves its dynamic-import module graph (top-level await)
    // after the browser's `load` event fires, so the app's own initial
    // fetch(/api/v2/fixtures) can still be in flight when this beforeEach
    // returns. Waiting for the render signal here — rather than a fixed
    // timeout — avoids racing that lingering request against a later
    // navigation, the same hazard fixed in refresh-controller.spec.js.
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
});

test('opening a fixture pushes the URL and survives Back/Forward with its date', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');
    await expect(page.locator('#match-context')).toContainText('Arsenal');

    await page.locator('#next-date').click();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-04');
    await expect(page.locator('#match-context')).not.toContainText('Arsenal');

    // Back must restore both the date the URL names and the fixture the
    // same URL names — the defect discarded the fixture unconditionally.
    await page.goBack();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-03');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');
    await expect(page.locator('#match-context')).toContainText('Arsenal');
    await expect(page.locator('.fixture-card[data-fixture-id="fx-arsenal"]')).toHaveAttribute('aria-current', 'true');

    // Forward is symmetric: the later entry never named a fixture.
    await page.goForward();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-04');
    await expect.poll(() => page.evaluate(() => location.search)).not.toContain('fixture=');
    await expect(page.locator('#match-context')).not.toContainText('Arsenal');
});

test('changing timezone then going Back restores the previous timezone and keeps the selected fixture', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('timezone=America%2FNew_York');

    await page.locator('#timezone-filter').selectOption('Europe/London');
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('timezone=Europe%2FLondon');
    await expect(page.locator('#match-context')).not.toContainText('Arsenal');

    // The fixture itself is unchanged by a zone change, so Back should
    // restore it exactly as it restores the timezone.
    await page.goBack();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#timezone-filter')).toHaveValue('America/New_York');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');
    await expect(page.locator('#match-context')).toContainText('Arsenal');
});

test('filters and sort survive a Back navigation', async ({page}) => {
    await page.locator('#competition-filter').selectOption('Premier League');
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await page.locator('#sort-filter').selectOption('competition');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('sort=competition');

    await page.locator('#next-date').click();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-04');

    await page.goBack();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-03');
    await expect(page.locator('#competition-filter')).toHaveValue('Premier League');
    await expect(page.locator('#sort-filter')).toHaveValue('competition');
});

test('focus is not lost to <body> after a history navigation', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');

    // `#next-date` is a static control that survives every fixture-stream
    // re-render, so it is a reliable place to prove the handler does not
    // blur focus onto <body> as a side effect of restoring state. WebKit
    // does not focus a <button> on click (unlike Chromium), so focus is
    // set explicitly rather than relied upon as a click side effect.
    await page.locator('#next-date').click();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await page.locator('#next-date').focus();
    await expect(page.locator('#next-date')).toBeFocused();

    await page.goBack();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#next-date')).toBeFocused();
    const activeTag = await page.evaluate(() => document.activeElement?.tagName);
    expect(activeTag).not.toBe('BODY');
});
