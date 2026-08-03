import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

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
