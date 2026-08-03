import {expect, test} from '@playwright/test';

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
