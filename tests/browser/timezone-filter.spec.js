import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

test('filter timezone selector replaces the redundant header timezone button', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
    await page.goto('/?date=2026-08-03&timezone=UTC');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    await expect(page.locator('#timezone-trigger')).toHaveCount(0);
    const timezoneFilter = page.locator('#timezone-filter');
    await expect(timezoneFilter).toBeVisible();
    await expect(timezoneFilter).toHaveValue('UTC');

    await timezoneFilter.selectOption('Europe/London');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('timezone=Europe%2FLondon');
});
