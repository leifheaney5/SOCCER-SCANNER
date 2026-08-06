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

test('selecting a second fixture then pressing Back restores the first, not the second', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');
    await expect(page.locator('#match-context')).toContainText('Arsenal');

    await page.locator('.fixture-card[data-fixture-id="fx-celtic"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-celtic');
    await expect(page.locator('#match-context')).toContainText('Celtic');
    await expect(page.locator('#match-context')).not.toContainText('Arsenal');

    // Both selections are on the same date and timezone, so this Back
    // exercises the handler's direct reflectCurrentResults() branch rather
    // than the loadFixtures() branch that every other test above exercises.
    // The reopen guard in reflectCurrentResults only fires when nothing is
    // currently displayed, so the panel must be reconciled here even though
    // the restored id is non-empty — asserting the panel content (not just
    // the URL) is what catches a guard that skips reconciliation.
    await page.goBack();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');
    await expect(page.locator('#match-context')).toContainText('Arsenal');
    await expect(page.locator('#match-context')).not.toContainText('Celtic');
    await expect(page.locator('.fixture-card[data-fixture-id="fx-arsenal"]')).toHaveAttribute('aria-current', 'true');
});

test('an unrelated filter change then Back does not tear the match panel down to its placeholder', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect(page.locator('#match-context')).toContainText('Arsenal');

    // Filtering to the fixture's own competition leaves it selected and
    // visible — the same fixture stays open across this step, so the Back
    // below restores a selection that is already unchanged.
    await page.locator('#competition-filter').selectOption('Premier League');
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#match-context')).toContainText('Arsenal');

    // A focus assertion is not usable here: reflectCurrentResults() already
    // rebuilds #match-context-content on every filter change regardless of
    // this fix (matchContext.rerender() runs unconditionally whenever a
    // fixture is selected, independent of whether the selection itself
    // changed), so anything focused inside the panel is already lost to
    // <body> by the filter click above, before Back is even pressed. That
    // is pre-existing behavior this task does not touch. What this fix
    // controls is narrower: whether the popstate handler additionally tears
    // the panel down to its "Select a fixture" placeholder and rebuilds it
    // a second time, purely because a fixture id was restored, even though
    // it is the same one already displayed. A MutationObserver on
    // #match-context-content, installed after the filter-change re-render
    // above has settled, isolates exactly that: it records each childList
    // mutation's added content during the Back navigation, so the
    // placeholder text appearing at all — even fleetingly, with no paint in
    // between — is directly observable, unlike polling the DOM afterward.
    await page.evaluate(() => {
        window.__historyRestorationMutations = [];
        const target = document.getElementById('match-context-content');
        const observer = new MutationObserver(records => {
            for (const record of records) {
                window.__historyRestorationMutations.push(
                    [...record.addedNodes].map(node => node.textContent).join('|'),
                );
            }
        });
        observer.observe(target, {childList: true});
        window.__historyRestorationObserver = observer;
    });

    await page.goBack();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#match-context')).toContainText('Arsenal');

    const mutations = await page.evaluate(() => {
        window.__historyRestorationObserver.disconnect();
        return window.__historyRestorationMutations;
    });
    expect(mutations.some(text => text.includes('Select a fixture'))).toBe(false);
});

test('a failed refetch after jumping dates does not leave a stale fixture panel open', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');

    await page.locator('#next-date').click();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await page.locator('.fixture-card[data-fixture-id="fx-liverpool"] .details-button').click();
    await expect(page.locator('#match-context')).toContainText('Liverpool');

    // The history stack is now: (1) 2026-08-03, (2) 2026-08-03&fixture=
    // fx-arsenal, (3) 2026-08-04, (4) 2026-08-04&fixture=fx-liverpool — here.
    // `history.go(-2)` jumps straight from (4) to (2) the way a browser's
    // back-button history menu would, firing exactly one popstate for the
    // landing entry with no popstate for entry (3) in between. Two
    // sequential goBack() calls would fire popstate for (3) first, which
    // already has no fixture and would reset the panel before the date
    // boundary is even crossed — that would not reproduce a fixture from
    // one date still being open when the refetch for a different date
    // fails, which is what this test exists to cover.
    await page.unroute('**/api/v2/fixtures**');
    await page.route('**/api/v2/fixtures**', route => {
        const requestedDate = new URL(route.request().url()).searchParams.get('date');
        if (requestedDate === '2026-08-03') {
            return route.fulfill({status: 502, contentType: 'application/json', body: JSON.stringify({error: 'provider unavailable'})});
        }
        return route.fulfill({contentType: 'application/json', body: JSON.stringify(dayTwoPayload)});
    });

    await page.evaluate(() => window.history.go(-2));
    await expect(page.locator('#dashboard-status')).toContainText('Football data is temporarily unavailable');
    // The old, unconditional reset guaranteed a clean panel regardless of
    // fetch outcome; loadFixtures' catch branch never calls
    // reflectCurrentResults, so nothing reopens the panel on failure —
    // it must not still be showing the fixture from the date navigated away
    // from.
    await expect(page.locator('#match-context')).not.toContainText('Liverpool');
    await expect(page.locator('#match-context')).toContainText('Select a fixture');
});

test('a control outside the fixture stream keeps focus after a history navigation', async ({page}) => {
    await page.locator('.fixture-card[data-fixture-id="fx-arsenal"] .details-button').click();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('fixture=fx-arsenal');

    // `#next-date` sits outside `#fixture-stream`, which every render fully
    // replaces, so this proves only that the handler does not blur an
    // unrelated, undestroyed control onto <body> as a side effect of
    // restoring state — it does not exercise focus behavior for elements
    // the render pipeline recreates (e.g. fixture cards), which have no
    // focus-restoration logic here to test. WebKit does not focus a
    // <button> on click (unlike Chromium), so focus is set explicitly
    // rather than relied upon as a click side effect.
    await page.locator('#next-date').click();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await page.locator('#next-date').focus();
    await expect(page.locator('#next-date')).toBeFocused();

    await page.goBack();
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
    await expect(page.locator('#next-date')).toBeFocused();
});
