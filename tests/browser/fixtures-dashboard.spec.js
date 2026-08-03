import {expect, test} from '@playwright/test';
import {emptyFixturePayload, fixturePayload, teamPayload} from './test-data.js';

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
    await expect(toggle.locator('svg')).toHaveAttribute('data-icon', 'eye-off');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('soccer-scanner:reveal-scores'))).toBeNull();

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(toggle).toHaveAccessibleName('Hide scores');
    await expect(toggle.locator('svg')).toHaveAttribute('data-icon', 'eye');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('soccer-scanner:reveal-scores'))).toBe('true');

    await page.reload();
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(toggle).toHaveAccessibleName('Hide scores');
    await expect(toggle.locator('svg')).toHaveAttribute('data-icon', 'eye');
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

    await page.keyboard.press('Shift+Tab');
    expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press('Tab');
    expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);

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

test('team drawer renders complete intelligence, protects scores, caches, and restores focus', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await mockFixtures(page);
    let teamRequests = 0;
    await page.route('**/api/team-analysis/*', async route => {
        teamRequests += 1;
        await new Promise(resolve => setTimeout(resolve, 350));
        await route.fulfill({contentType: 'application/json', body: JSON.stringify(teamPayload)});
    });
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await page.locator('.fixture-card[data-fixture-id="live-secret"] .details-button').click();

    const trigger = page.locator('#match-context').getByRole('button', {name: 'Open Arsenal intelligence'});
    await trigger.click();
    const drawer = page.locator('#team-drawer');
    await expect(drawer).toBeVisible();
    await expect(page.locator('#close-team-drawer')).toBeFocused();
    await expect(drawer.locator('[data-skeleton="team"]')).toHaveCount(4);
    await expect(drawer).toContainText('Arsenal');
    await expect(drawer).toContainText('Founded 1886');
    await expect(drawer).toContainText('Emirates Stadium');
    await expect(drawer).toContainText('Red / White');
    await expect(drawer).toContainText('10 played');
    await expect(drawer).toContainText('6 wins');
    await expect(drawer).toContainText('2 draws');
    await expect(drawer).toContainText('2 losses');
    await expect(drawer).toContainText('22 goals for');
    await expect(drawer).toContainText('11 goals against');
    await expect(drawer).toContainText('+11 goal difference');
    await expect(drawer.locator('.form-result')).toHaveCount(5);
    await expect(drawer.getByLabel('Win').first()).toHaveText('W');
    await expect(drawer.getByLabel('Draw')).toHaveText('D');
    await expect(drawer.getByLabel('Loss')).toHaveText('L');
    await expect(drawer).toContainText('Chelsea');
    await expect(drawer).toContainText('Liverpool');
    await expect(drawer).toContainText('2 players');
    await expect(drawer).toContainText('4-3-3');
    await expect(drawer.getByText('Score hidden', {exact: true})).toBeVisible();

    await page.keyboard.press('Shift+Tab');
    expect(await drawer.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press('Tab');
    expect(await drawer.evaluate(element => element.contains(document.activeElement))).toBe(true);

    const hiddenLeaks = await drawer.evaluate(element => {
        const content = `${element.textContent} ${[...element.querySelectorAll('*')].flatMap(child => [...child.attributes].map(attribute => attribute.value)).join(' ')}`;
        return ['97', '96'].filter(secret => new RegExp(`\\b${secret}\\b`).test(content));
    });
    expect(hiddenLeaks).toEqual([]);

    await page.keyboard.press('Escape');
    await expect(drawer).not.toBeVisible();
    await expect(trigger).toBeFocused();
    await trigger.click();
    await expect(drawer).toContainText('Arsenal');
    expect(teamRequests).toBe(1);
    await page.locator('#close-team-drawer').click();

    await page.locator('#score-toggle').click();
    await page.locator('#match-context').getByRole('button', {name: 'Open Arsenal intelligence'}).click();
    await expect(drawer.getByText('97 – 96', {exact: true})).toBeVisible();
});

test('team drawer exposes provider retry and limited-data states', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await mockFixtures(page);
    let arsenalAttempts = 0;
    await page.route('**/api/team-analysis/*', route => {
        const teamId = route.request().url().split('/').at(-1);
        if (teamId === 'live-secret-home') {
            arsenalAttempts += 1;
            return arsenalAttempts === 1
                ? route.fulfill({status: 502, contentType: 'application/json', body: JSON.stringify({error: 'raw provider failure'})})
                : route.fulfill({contentType: 'application/json', body: JSON.stringify(teamPayload)});
        }
        return route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({
                team_info: {id: teamId, name: 'River Plate', crest: null},
                squad: [],
                formation_data: {},
                recent_matches: [],
                upcoming_matches: [],
                stats: {},
                top_performers: {},
                competition_analysis: {},
            }),
        });
    });
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await page.locator('.fixture-card[data-fixture-id="live-secret"] .details-button').click();

    await page.locator('#match-context').getByRole('button', {name: 'Open Arsenal intelligence'}).click();
    const drawer = page.locator('#team-drawer');
    await expect(drawer.getByRole('heading', {name: 'Team intelligence unavailable'})).toBeVisible();
    await expect(drawer).not.toContainText('raw provider failure');
    await drawer.getByRole('button', {name: 'Retry'}).click();
    await expect(drawer).toContainText('Emirates Stadium');
    expect(arsenalAttempts).toBe(2);
    await page.locator('#close-team-drawer').click();

    await page.locator('#match-context').getByRole('button', {name: 'Open River Plate intelligence'}).click();
    await expect(drawer).toContainText('Limited team data');
    await expect(drawer).toContainText('River Plate');
});

test('visual tokens, type roles, and reduced motion match the product contract', async ({page}) => {
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.setViewportSize({width: 1440, height: 1000});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const styles = await page.evaluate(() => {
        const root = getComputedStyle(document.documentElement);
        const body = getComputedStyle(document.body);
        const header = getComputedStyle(document.querySelector('.app-header'));
        const score = getComputedStyle(document.querySelector('.score-display--kickoff'));
        const card = getComputedStyle(document.querySelector('.fixture-card'));
        const liveDot = getComputedStyle(document.querySelector('.live-dot'));
        const context = getComputedStyle(document.querySelector('#match-context'));
        return {
            tokens: {
                bgPrimary: root.getPropertyValue('--bg-primary').trim(),
                bgSecondary: root.getPropertyValue('--bg-secondary').trim(),
                bgCard: root.getPropertyValue('--bg-card').trim(),
                accent: root.getPropertyValue('--accent-primary').trim(),
                border: root.getPropertyValue('--border-color').trim(),
            },
            bodyBackground: body.backgroundColor,
            bodyFont: body.fontFamily,
            headerPosition: header.position,
            scoreFont: score.fontFamily,
            transitionDuration: card.transitionDuration,
            animationName: liveDot.animationName,
            contextPosition: context.position,
        };
    });
    expect(styles.tokens).toEqual({
        bgPrimary: '#000000',
        bgSecondary: '#0a0a0a',
        bgCard: '#141414',
        accent: '#7CFF00',
        border: '#2a2a2a',
    });
    expect(styles.bodyBackground).toBe('rgb(0, 0, 0)');
    expect(styles.bodyFont).toContain('Inter');
    expect(styles.headerPosition).toBe('sticky');
    expect(styles.scoreFont).toContain('IBM Plex Mono');
    expect(styles.transitionDuration).toBe('0s');
    expect(styles.animationName).toBe('none');
    expect(styles.contextPosition).toBe('sticky');
});

for (const width of [320, 375, 430, 768, 1024, 1280, 1440]) {
    test(`dashboard has no horizontal overflow at ${width}px`, async ({page}) => {
        await page.setViewportSize({width, height: width < 600 ? 800 : 900});
        await mockFixtures(page);
        await page.goto('/?date=2026-08-03');
        await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

        const measurements = await page.evaluate(() => {
            const targetIds = ['previous-date', 'today-date', 'next-date', 'filter-toggle', 'score-toggle'];
            return {
                documentWidth: document.documentElement.scrollWidth,
                viewportWidth: document.documentElement.clientWidth,
                bodyWidth: document.body.scrollWidth,
                targets: targetIds.map(id => {
                    const box = document.getElementById(id).getBoundingClientRect();
                    return {id, width: box.width, height: box.height};
                }),
                cardOverflow: [...document.querySelectorAll('.fixture-card')].some(card => card.scrollWidth > card.clientWidth),
                contextDisplay: getComputedStyle(document.getElementById('match-context')).display,
                filterToggleDisplay: getComputedStyle(document.getElementById('filter-toggle')).display,
                secondaryDisplay: getComputedStyle(document.getElementById('secondary-filters')).display,
            };
        });
        expect(measurements.documentWidth).toBeLessThanOrEqual(measurements.viewportWidth);
        expect(measurements.bodyWidth).toBeLessThanOrEqual(measurements.viewportWidth);
        expect(measurements.cardOverflow).toBe(false);
        if (width < 1100) expect(measurements.contextDisplay).toBe('none');
        else expect(measurements.contextDisplay).not.toBe('none');

        if (width <= 767) {
            expect(measurements.filterToggleDisplay).not.toBe('none');
            expect(measurements.secondaryDisplay).toBe('none');
            for (const target of measurements.targets) {
                expect(target.height, `${target.id} height`).toBeGreaterThanOrEqual(44);
                expect(target.width, `${target.id} width`).toBeGreaterThanOrEqual(44);
            }
            await expect(page.locator('.fixture-card').first().locator('.fixture-mobile-meta')).toBeVisible();
            await page.locator('#filter-toggle').click();
            await expect(page.locator('#secondary-filters')).toBeVisible();
        } else {
            expect(measurements.filterToggleDisplay).toBe('none');
            expect(measurements.secondaryDisplay).not.toBe('none');
        }
        await expect(page.locator('.fixture-card').first().locator('.details-button')).toBeVisible();
    });
}

test('narrow mobile keeps the featured score between the teams and the date legible', async ({page}) => {
    await page.setViewportSize({width: 375, height: 812});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const layout = await page.locator('#featured-match').evaluate(featured => {
        const [home, away] = featured.querySelectorAll('.team-identity--featured');
        const score = featured.querySelector('.score-display--featured');
        const date = document.getElementById('dashboard-date');
        const homeBox = home.getBoundingClientRect();
        const scoreBox = score.getBoundingClientRect();
        const awayBox = away.getBoundingClientRect();
        const dateBox = date.getBoundingClientRect();
        return {
            homeX: homeBox.x,
            scoreX: scoreBox.x,
            awayX: awayBox.x,
            dateWidth: dateBox.width,
        };
    });

    expect(layout.homeX).toBeLessThan(layout.scoreX);
    expect(layout.scoreX).toBeLessThan(layout.awayX);
    expect(layout.dateWidth).toBeGreaterThanOrEqual(130);
});

test('landscape mobile remains scroll-safe and match details stay operable', async ({page}) => {
    await page.setViewportSize({width: 812, height: 375});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const overflow = await page.evaluate(() => ({
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
    }));
    expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth);

    const details = page.locator('[data-fixture-id="live-secret"] .details-button');
    await details.click();
    await expect(page.locator('#match-context-dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#match-context-dialog')).not.toBeVisible();
    await expect(details).toBeFocused();
});
