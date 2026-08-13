import {test, expect} from '@playwright/test';

test('operations dashboard renders live status without echoing the token', async ({page}) => {
    await page.route('**/api/v2/operations', async route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
            build: {version: '2.0.0', environment: 'development'},
            readiness: {status: 'ready', cache: {status: 'ready'}},
            providers: {status: 'ok', providers: []},
            rateLimit: {status: 'ready'},
            metrics: {counters: {'api.requests': 4}, timings: {}},
        }),
    }));
    await page.goto('/operations');
    await page.locator('#operations-token').fill('test-token');
    await page.getByRole('button', {name: 'Load status'}).click();
    await expect(page.locator('#operations-status')).toHaveText('Operational status loaded.');
    await expect(page.locator('#operations-values')).toContainText('development');
    await expect(page.locator('#operations-values')).not.toContainText('test-token');
});
