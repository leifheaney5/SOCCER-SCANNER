import {expect, test} from '@playwright/test';
import {fixturePayload, teamPayload} from './test-data.js';

test.use({serviceWorkers: 'block'});

test('capture synthetic desktop release states', async ({page}, testInfo) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await page.screenshot({path: testInfo.outputPath('desktop-default.png'), fullPage: true});

    await page.locator('#score-toggle').click();
    await page.screenshot({path: testInfo.outputPath('desktop-revealed.png'), fullPage: true});
    await page.locator('#fixture-search').fill('Arsenal');
    await page.screenshot({path: testInfo.outputPath('desktop-filtered.png'), fullPage: true});
    await page.locator('.fixture-card[data-fixture-id="live-secret"] .details-button').click();
    await page.screenshot({path: testInfo.outputPath('desktop-context.png'), fullPage: true});
    await page.locator('.fixture-card[data-fixture-id="live-secret"] .favorite-button').click();
    await page.screenshot({path: testInfo.outputPath('desktop-favorite.png'), fullPage: true});

    await page.evaluate(async () => {
        const version = new URL(document.querySelector('script[src*="fixtures.js"]').src).searchParams.get('v');
        const renderer = await import(`/static/js/fixture-renderer.js?v=${encodeURIComponent(version)}`);
        renderer.renderNotice(document.getElementById('data-notice'), {stale: false, partial: true});
    });
    await expect(page.locator('#data-notice')).toContainText('Some fixture sources are delayed');
    await page.screenshot({path: testInfo.outputPath('desktop-partial.png'), fullPage: true});
    await page.evaluate(async () => {
        const version = new URL(document.querySelector('script[src*="fixtures.js"]').src).searchParams.get('v');
        const renderer = await import(`/static/js/fixture-renderer.js?v=${encodeURIComponent(version)}`);
        renderer.renderNotice(document.getElementById('data-notice'), {stale: true, partial: true});
    });
    await expect(page.locator('#data-notice')).toContainText('Showing saved fixture data');
    await page.screenshot({path: testInfo.outputPath('desktop-stale.png'), fullPage: true});
    await page.evaluate(async () => {
        const version = new URL(document.querySelector('script[src*="fixtures.js"]').src).searchParams.get('v');
        const renderer = await import(`/static/js/fixture-renderer.js?v=${encodeURIComponent(version)}`);
        renderer.renderEmptyState(document.getElementById('fixture-stream'));
    });
    await expect(page.getByRole('heading', {name: 'No matches scheduled'})).toBeVisible();
    await page.screenshot({path: testInfo.outputPath('desktop-empty.png'), fullPage: true});
    await page.evaluate(async () => {
        const version = new URL(document.querySelector('script[src*="fixtures.js"]').src).searchParams.get('v');
        const renderer = await import(`/static/js/fixture-renderer.js?v=${encodeURIComponent(version)}`);
        renderer.renderRequestError(document.getElementById('fixture-stream'), () => {});
    });
    await expect(page.getByRole('heading', {name: 'Football data is temporarily unavailable'})).toBeVisible();
    await page.screenshot({path: testInfo.outputPath('desktop-error.png'), fullPage: true});
});

test('capture synthetic mobile sheet and team drawer states', async ({page}, testInfo) => {
    await page.setViewportSize({width: 390, height: 844});
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
    await page.route('**/api/v2/teams/*/analysis', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(teamPayload),
    }));
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await page.screenshot({path: testInfo.outputPath('mobile-default.png'), fullPage: true});
    await page.locator('.fixture-card[data-fixture-id="live-secret"] .details-button').click();
    await expect(page.locator('#match-context-dialog')).toBeVisible();
    await page.screenshot({path: testInfo.outputPath('mobile-match-sheet.png'), fullPage: true});
    await page.locator('#match-context-dialog').getByRole('button', {name: 'Open Arsenal intelligence'}).click();
    await expect(page.locator('#team-drawer')).toContainText('Arsenal');
    await page.screenshot({path: testInfo.outputPath('mobile-team-drawer.png'), fullPage: true});
});
