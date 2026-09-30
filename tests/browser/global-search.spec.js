import {test, expect} from '@playwright/test';

test('fixture search remains available without the redundant global search', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({state: 'success', matches: [], total: 0}),
    }));

    await page.goto('/?date=2026-08-13');

    await expect(page.locator('#fixture-search')).toBeVisible();
    await expect(page.locator('#global-search-trigger')).toHaveCount(0);
    await expect(page.locator('#global-search-dialog')).toHaveCount(0);
});
