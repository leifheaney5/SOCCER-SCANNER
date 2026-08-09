import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

test('calendar loads only a seven-day window and navigates by bounded weeks', async ({page}) => {
    const requested = [];
    await page.route('**/api/v2/fixtures**', route => {
        const url = new URL(route.request().url());
        const date = url.searchParams.get('date');
        requested.push(date);
        return route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({...fixturePayload, date}),
        });
    });

    await page.goto('/calendar?start=2026-08-03&timezone=America%2FNew_York');
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    expect([...new Set(requested)]).toEqual([
        '2026-08-03', '2026-08-04', '2026-08-05', '2026-08-06',
        '2026-08-07', '2026-08-08', '2026-08-09',
    ]);

    requested.length = 0;
    await page.locator('#calendar-next').click();
    await expect(page.locator('#calendar-start')).toHaveValue('2026-08-10');
    await expect.poll(() => [...new Set(requested)].length).toBe(7);
    await expect.poll(() => page.evaluate(() => location.search)).toContain('start=2026-08-10');
});

test('calendar view, jump date, timezone, and spoiler rules stay shareable', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => {
        const date = new URL(route.request().url()).searchParams.get('date');
        return route.fulfill({contentType: 'application/json', body: JSON.stringify({...fixturePayload, date, stale: false, partial: false})});
    });
    await page.goto('/calendar?start=2026-08-03');
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    await expect(page.locator('#calendar-results')).not.toContainText('97 – 96');
    await expect(page.locator('#calendar-results')).toContainText('Score hidden');

    await page.locator('#calendar-view-grid').click();
    await expect(page.locator('#calendar-results')).toHaveAttribute('data-view', 'grid');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('view=grid');
    await page.locator('#calendar-timezone').selectOption('Europe/London');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('timezone=Europe%2FLondon');
    await page.locator('#calendar-start').fill('2026-08-17');
    await page.locator('#calendar-start').dispatchEvent('change');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('start=2026-08-17');
});

test('calendar remains reflow-safe at 320px', async ({page}) => {
    await page.setViewportSize({width: 320, height: 800});
    await page.route('**/api/v2/fixtures**', route => {
        const date = new URL(route.request().url()).searchParams.get('date');
        return route.fulfill({contentType: 'application/json', body: JSON.stringify({...fixturePayload, date})});
    });
    await page.goto('/calendar?start=2026-08-03&view=grid');
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('one unavailable day keeps the other six days and retries independently', async ({page}) => {
    const attempts = new Map();
    await page.route('**/api/v2/fixtures**', route => {
        const date = new URL(route.request().url()).searchParams.get('date');
        const attempt = (attempts.get(date) || 0) + 1;
        attempts.set(date, attempt);
        if (date === '2026-08-05' && attempt === 1) {
            return route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'unavailable'})});
        }
        return route.fulfill({contentType: 'application/json', body: JSON.stringify({...fixturePayload, date, stale: false, partial: false})});
    });

    await page.goto('/calendar?start=2026-08-03');
    await expect(page.locator('#calendar-status')).toContainText('6 days loaded; 1 need attention');
    await expect(page.locator('.calendar-day[data-date="2026-08-05"]')).toHaveAttribute('data-state', 'error');
    await expect(page.locator('.calendar-day[data-date="2026-08-03"] .calendar-fixture')).toHaveCount(13);

    await page.locator('.calendar-day[data-date="2026-08-05"] .calendar-retry').click();
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    await expect(page.locator('.calendar-day[data-date="2026-08-05"]')).toHaveAttribute('data-state', 'success');
    expect(attempts.get('2026-08-05')).toBe(2);
});

test('calendar score visibility rerenders without refetching loaded days', async ({page}) => {
    let requestCount = 0;
    await page.route('**/api/v2/fixtures**', route => {
        requestCount += 1;
        const date = new URL(route.request().url()).searchParams.get('date');
        return route.fulfill({contentType: 'application/json', body: JSON.stringify({...fixturePayload, date})});
    });
    await page.goto('/calendar?start=2026-08-03');
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    expect(requestCount).toBe(7);
    await page.locator('#score-toggle').click();
    await expect(page.locator('#calendar-results')).toContainText('97 – 96');
    expect(requestCount).toBe(7);
    await page.locator('#score-toggle').click();
    await expect(page.locator('#calendar-results')).toContainText('Score hidden');
    expect(requestCount).toBe(7);
});
