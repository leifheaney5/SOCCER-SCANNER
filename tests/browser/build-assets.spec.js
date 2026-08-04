import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';


test('all first-party assets load and share the immutable build token', async ({page}) => {
    const firstPartyResponses = [];
    page.on('response', response => {
        const url = new URL(response.url());
        if (url.origin === 'http://127.0.0.1:5100' && url.pathname.startsWith('/static/')) {
            firstPartyResponses.push({url: response.url(), status: response.status()});
        }
    });
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));

    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    const version = await page.request.get('/health/version');
    const {assetVersion} = await version.json();

    expect(firstPartyResponses.filter(item => item.status >= 400)).toEqual([]);
    const scriptsAndStyles = firstPartyResponses.filter(item => /\.(?:js|css)$/.test(
        new URL(item.url).pathname,
    ));
    expect(scriptsAndStyles.length).toBeGreaterThan(4);
    expect(scriptsAndStyles.every(item => (
        new URL(item.url).searchParams.get('v') === assetVersion
    ))).toBe(true);
});
