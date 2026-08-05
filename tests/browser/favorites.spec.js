import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

async function mockFixtures(page) {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
}

test('guest mode does not expose favorites or account-like persistence', async ({page}) => {
    await mockFixtures(page);
    await page.addInitScript(() => {
        localStorage.setItem('soccer-scanner:favorites', JSON.stringify({
            version: 1,
            teams: ['arsenal'],
            competitions: [],
            fixtures: ['live-secret'],
        }));
    });
    await page.goto('/?date=2026-08-03&favorites=1');

    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await expect(page.getByRole('link', {name: 'Favorites'})).toHaveCount(0);
    await expect(page.locator('#favorites-only')).toHaveCount(0);
    await expect(page.locator('[data-action="toggle-favorite"]')).toHaveCount(0);
    await expect(page.locator('#export-favorites, #import-favorites, #clear-favorites')).toHaveCount(0);
    await page.locator('#fixture-search').fill('Arsenal');
    await expect.poll(() => page.evaluate(() => location.search)).not.toContain('favorites=1');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('soccer-scanner:favorites'))).toContain('live-secret');
});
