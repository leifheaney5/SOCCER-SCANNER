import {expect, test} from '@playwright/test';
import {emptyFixturePayload, fixturePayload} from './test-data.js';

async function mockFixtures(page, payload = fixturePayload) {
    await page.route('**/api/matches-today**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
}

test('semantic shell shows spoiler control and fixture-shaped loading rows', async ({page}) => {
    await page.route('**/api/matches-today**', async route => {
        await new Promise(resolve => setTimeout(resolve, 1_000));
        await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({matches: [], total_matches: 0, date: '2026-08-03'}),
        });
    });

    await page.goto('/?date=2026-08-03');

    await expect(page.getByRole('heading', {name: 'Fixtures', exact: true})).toBeVisible();
    await expect(page.getByRole('region', {name: 'Fixture filters'})).toBeVisible();
    await expect(page.getByRole('button', {name: 'Reveal scores'})).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('[data-skeleton="fixture"]')).toHaveCount(6);
});

test('URL state initializes controls and filter changes replace the URL', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03&competition=Premier+League&status=live&q=Arsenal');

    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-03');
    await expect(page.locator('#competition-filter')).toHaveValue('Premier League');
    await expect(page.locator('#status-live')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#fixture-search')).toHaveValue('Arsenal');

    await page.locator('#fixture-search').fill('Celtic');
    await page.locator('#status-upcoming').click();
    await page.locator('#competition-filter').selectOption('Scottish Premiership');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('q=Celtic');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('status=upcoming');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('competition=Scottish+Premiership');
});

test('score preference defaults hidden and persists after reload', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');

    const toggle = page.locator('#score-toggle');
    await expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await expect(toggle).toHaveAccessibleName('Reveal scores');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('soccer-scanner:reveal-scores'))).toBeNull();

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(toggle).toHaveAccessibleName('Hide scores');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('soccer-scanner:reveal-scores'))).toBe('true');

    await page.reload();
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(toggle).toHaveAccessibleName('Hide scores');
});

test('hidden scores never enter DOM content and reveal consistently', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    await expect(page.getByText('Score hidden', {exact: true}).first()).toBeVisible();
    await expect(page.getByText('07:45 PM', {exact: true})).toBeVisible();
    const hiddenLeaks = await page.evaluate(() => {
        const secrets = ['97', '96', '95', '94'];
        const text = document.documentElement.textContent || '';
        const attributes = [...document.querySelectorAll('*')].flatMap(element => (
            [...element.attributes].map(attribute => attribute.value)
        )).join(' ');
        return secrets.filter(secret => (
            new RegExp(`\\b${secret}\\b`).test(text)
            || new RegExp(`\\b${secret}\\b`).test(attributes)
        ));
    });
    expect(hiddenLeaks).toEqual([]);

    await page.locator('#score-toggle').click();
    await expect(page.getByText('97 – 96', {exact: true})).toHaveCount(2);
    await expect(page.getByText('97 – 96', {exact: true}).first()).toBeVisible();
    await expect(page.getByText('95 – 94', {exact: true})).toBeVisible();
    await expect(page.getByText('Score unavailable', {exact: true})).toBeVisible();
    await expect(page.getByText('07:45 PM', {exact: true})).toBeVisible();
});

test('fixtures render paired identities, crest fallbacks, groups, and live-first feature', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const featured = page.locator('#featured-match');
    await expect(featured).toContainText('Live now');
    await expect(featured).toContainText('Arsenal');
    await expect(featured).toContainText('River Plate');
    await expect(featured.locator('.team-crest')).toHaveCount(2);

    await expect(page.locator('.competition-group')).toHaveCount(5);
    const premier = page.locator('.competition-group', {hasText: 'Premier League'});
    await expect(premier).toContainText('England');
    await expect(premier).toContainText('9 matches');
    await expect(premier.getByRole('button', {name: 'Show all 9 matches'})).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('.fixture-card')).toHaveCount(10);
    await premier.getByRole('button', {name: 'Show all 9 matches'}).click();
    await expect(page.locator('.fixture-card')).toHaveCount(13);

    await expect(page.locator('.fixture-card .team-row')).toHaveCount(26);
    await expect(page.locator('.fixture-card .team-crest')).toHaveCount(26);
    await expect(page.locator('.fixture-card img.team-crest-image').first()).toHaveAttribute('loading', 'lazy');
    await expect(page.locator('.fixture-card img.team-crest-image').first()).toHaveAttribute('decoding', 'async');
    await expect(page.locator('[data-fixture-id="missing-score"] .crest-fallback')).toHaveCount(2);
    await expect(page.locator('.fixture-card').first()).not.toContainText(' vs ');
});

test('date navigation, search, status, competition, and clear controls stay in sync', async ({page}) => {
    const requestedDates = [];
    await page.route('**/api/matches-today**', route => {
        const url = new URL(route.request().url());
        requestedDates.push(url.searchParams.get('date'));
        return route.fulfill({contentType: 'application/json', body: JSON.stringify(fixturePayload)});
    });
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    await page.locator('#previous-date').click();
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-02');
    await expect.poll(() => requestedDates).toContain('2026-08-02');
    await page.locator('#next-date').click();
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-03');
    await page.locator('#today-date').click();
    await expect(page.locator('#dashboard-date')).toHaveValue('2026-08-03');

    await page.locator('#fixture-search').fill('Celtic');
    await expect(page.locator('#fixture-result-count')).toContainText('1 match');
    await expect(page.locator('#clear-search')).toBeVisible();
    await page.locator('#clear-search').click();
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    await page.locator('#status-live').click();
    await expect(page.locator('#fixture-result-count')).toContainText('2 matches');
    await page.locator('#competition-filter').selectOption('Premier League');
    await expect(page.locator('#fixture-result-count')).toContainText('1 match');
    await expect(page.locator('#active-filter-count')).toHaveText('2');
    await expect(page.locator('#clear-filters')).toBeVisible();
    await page.locator('#clear-filters').click();
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await expect.poll(() => page.evaluate(() => location.search)).toBe('?date=2026-08-03');
});

test('empty date, filtered empty, provider error retry, partial, and stale states are distinct', async ({page}) => {
    await mockFixtures(page, emptyFixturePayload);
    await page.goto('/?date=2026-08-03');
    const emptyState = page.locator('.dashboard-state--empty');
    await expect(emptyState.getByRole('heading', {name: 'No matches scheduled'})).toBeVisible();
    await expect(emptyState.getByRole('button', {name: 'Previous day'})).toBeVisible();
    await expect(emptyState.getByRole('button', {name: 'Next day'})).toBeVisible();

    await page.unroute('**/api/matches-today**');
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03&q=NoSuchClub');
    await expect(page.getByRole('heading', {name: 'No fixtures match these filters'})).toBeVisible();
    await page.getByRole('button', {name: 'Clear filters'}).last().click();
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    await page.unroute('**/api/matches-today**');
    let attempts = 0;
    await page.route('**/api/matches-today**', route => {
        attempts += 1;
        return attempts === 1
            ? route.fulfill({status: 502, contentType: 'application/json', body: JSON.stringify({error: 'provider unavailable'})})
            : route.fulfill({contentType: 'application/json', body: JSON.stringify(fixturePayload)});
    });
    await page.goto('/?date=2026-08-03');
    await expect(page.getByRole('heading', {name: 'Football data is temporarily unavailable'})).toBeVisible();
    await page.getByRole('button', {name: 'Retry'}).click();
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    expect(attempts).toBe(2);

    await expect(page.locator('#data-notice')).toContainText('Showing saved fixture data');
    await page.unroute('**/api/matches-today**');
    await mockFixtures(page, {...fixturePayload, stale: false, partial: true});
    await page.reload();
    await expect(page.locator('#data-notice')).toContainText('Some fixture sources are delayed');
});

test('a superseded slow date response cannot replace the latest date', async ({page}) => {
    await page.route('**/api/matches-today**', async route => {
        const requested = new URL(route.request().url()).searchParams.get('date');
        if (requested === '2026-08-03') {
            await new Promise(resolve => setTimeout(resolve, 800));
            await route.fulfill({contentType: 'application/json', body: JSON.stringify(fixturePayload)});
            return;
        }
        const latest = {
            ...emptyFixturePayload,
            date: '2026-08-04',
            matches: [fixturePayload.matches.find(match => match.id === 'upcoming')],
            total_matches: 1,
        };
        await route.fulfill({contentType: 'application/json', body: JSON.stringify(latest)});
    });

    await page.goto('/?date=2026-08-03', {waitUntil: 'domcontentloaded'});
    await page.locator('#dashboard-date').fill('2026-08-04');
    await page.locator('#dashboard-date').dispatchEvent('change');
    await expect(page.locator('#fixture-result-count')).toContainText('1 match');
    await page.waitForTimeout(1_000);
    await expect(page.locator('#selected-date-label')).toContainText('August 4');
    await expect(page.locator('#fixture-stream')).toContainText('Celtic');
    await expect(page.locator('#fixture-stream')).not.toContainText('Arsenal');
});

test('desktop fixture selection populates complete spoiler-safe match context', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const card = page.locator('.fixture-card[data-fixture-id="live-secret"]');
    await card.getByRole('button', {name: /Open match details/}).click();
    await expect(card).toHaveClass(/is-selected/);
    await expect(page.locator('.fixture-card.is-selected')).toHaveCount(1);

    const context = page.locator('#match-context');
    await expect(context).toContainText('Premier League');
    await expect(context).toContainText('Live now');
    await expect(context).toContainText('Monday, August 3');
    await expect(context).toContainText('Scanner Stadium');
    await expect(context).toContainText('Matchday 4');
    await expect(context).toContainText('Regular season');
    await expect(context).toContainText('ESPN');
    await expect(context).toContainText('Score hidden');
    await expect(context.locator('.team-crest')).toHaveCount(2);
    await expect(context.getByRole('button', {name: 'Open Arsenal intelligence'})).toBeVisible();
    await expect(context.getByRole('button', {name: 'Open River Plate intelligence'})).toBeVisible();
    await expect(page.locator('#match-context-dialog')).not.toBeVisible();

    const hiddenContext = await context.textContent();
    expect(hiddenContext).not.toMatch(/\b97\b|\b96\b/);
    await page.locator('#score-toggle').click();
    await expect(context.getByText('97 – 96', {exact: true})).toBeVisible();
});

test('mobile match sheet traps interaction, closes, and restores fixture focus', async ({page}) => {
    await page.setViewportSize({width: 430, height: 800});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const details = page.locator('[data-fixture-id="live-secret"] .details-button');
    await details.click();
    const dialog = page.locator('#match-context-dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('open', '');
    await expect(page.locator('body')).toHaveClass(/dialog-open/);
    await expect(page.locator('#close-match-context')).toBeFocused();
    await expect(dialog).toContainText('Score hidden');

    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(page.locator('body')).not.toHaveClass(/dialog-open/);
    await expect(page.locator('[data-fixture-id="live-secret"] .details-button')).toBeFocused();

    await page.locator('[data-fixture-id="live-secret"] .details-button').click();
    await page.locator('#match-context-dialog').evaluate(element => {
        element.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    });
    await expect(dialog).not.toBeVisible();
    await expect(page.locator('[data-fixture-id="live-secret"] .details-button')).toBeFocused();
});
