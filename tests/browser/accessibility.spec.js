import AxeBuilder from '@axe-core/playwright';
import {expect, test} from '@playwright/test';
import {emptyFixturePayload, fixturePayload} from './test-data.js';

async function mockFixtures(page, payload = fixturePayload) {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
}

async function expectNoSeriousViolations(page) {
    const results = await new AxeBuilder({page}).analyze();
    expect(results.violations.filter(violation => ['critical', 'serious'].includes(violation.impact))).toEqual([]);
}

test('fixture dashboard and filters have no serious accessibility violations', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await expectNoSeriousViolations(page);
});

test('mobile navigation and fixture dialog remain accessible', async ({page}) => {
    await page.setViewportSize({width: 390, height: 844});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await page.locator('#nav-toggle').click();
    await expect(page.locator('#primary-navigation')).toBeVisible();
    await expectNoSeriousViolations(page);
    await page.locator('#nav-toggle').click();

    await page.locator('[data-fixture-id="live-secret"] .details-button').click();
    await expect(page.locator('#match-context-dialog')).toBeVisible();
    await expectNoSeriousViolations(page);
    await expect(page.locator('#match-context-dialog').getByRole('button', {name: /intelligence/})).toHaveCount(0);
});

test('mobile fixture filter dialog has accessible semantics and focus restoration', async ({page}) => {
    await page.setViewportSize({width: 390, height: 844});
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');

    const toggle = page.locator('#filter-toggle');
    await toggle.focus();
    await toggle.click();
    await expect(page.locator('#filter-dialog')).toHaveRole('dialog', {name: 'Fixture filters'});
    await expect(page.locator('#filter-dialog')).toContainText('Filter fixtures');
    await expect(page.locator('#fixture-search')).toBeVisible();
    await expect(page.locator('#status-all')).toBeVisible();
    await expect(page.locator('#filter-dialog #fixture-search')).toHaveCount(0);
    await expect(page.locator('#filter-dialog .status-filters')).toHaveCount(0);
    await expect(page.locator('#filter-dialog #competition-filter')).toBeVisible();
    await expectNoSeriousViolations(page);

    await page.locator('#close-filter-dialog').focus();
    await page.keyboard.press('Shift+Tab');
    await expect.poll(() => page.evaluate(() => (
        document.activeElement?.closest('#filter-dialog')?.id || ''
    ))).toBe('filter-dialog');

    await page.keyboard.press('Escape');
    await expect(page.locator('#filter-dialog')).toBeHidden();
    await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe('filter-toggle');
});

for (const {zoom, width} of [
    {zoom: 200, width: 640},
    {zoom: 400, width: 320},
]) {
    test(`fixture dashboard reflows without horizontal scrolling at ${zoom}% zoom`, async ({page}) => {
        await page.setViewportSize({width, height: 900});
        await mockFixtures(page);
        await page.goto('/?date=2026-08-03');
        await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

        const measurements = await page.evaluate(() => ({
            documentWidth: document.documentElement.scrollWidth,
            viewportWidth: document.documentElement.clientWidth,
            bodyWidth: document.body.scrollWidth,
            cardOverflow: [...document.querySelectorAll('.fixture-card')].some(card => (
                card.scrollWidth > card.clientWidth
            )),
        }));
        expect(measurements.documentWidth).toBeLessThanOrEqual(measurements.viewportWidth);
        expect(measurements.bodyWidth).toBeLessThanOrEqual(measurements.viewportWidth);
        expect(measurements.cardOverflow).toBe(false);
    });
}

test('empty and provider-error surfaces have no serious accessibility violations', async ({page}) => {
    await mockFixtures(page, emptyFixturePayload);
    await page.goto('/?date=2026-08-03');
    await expect(page.getByRole('heading', {name: 'No matches scheduled'})).toBeVisible();
    await expectNoSeriousViolations(page);

    await page.unroute('**/api/v2/fixtures**');
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({error: {code: 'provider_unavailable'}}),
    }));
    await page.reload();
    await expect(page.getByRole('heading', {name: 'Football data is temporarily unavailable'})).toBeVisible();
    await expectNoSeriousViolations(page);
});

for (const path of ['/teams', '/league-tables', '/privacy', '/data-sources', '/not-a-real-page']) {
    test(`${path} has no serious accessibility violations`, async ({page}) => {
        await page.goto(path);
        await expectNoSeriousViolations(page);
    });
}

test('the open header timezone popover has no serious accessibility violations', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await page.locator('#timezone-trigger').click();
    await expect(page.locator('#timezone-listbox')).toBeVisible();
    await expectNoSeriousViolations(page);
});

test('/calendar has no serious accessibility violations', async ({page}) => {
    await mockFixtures(page, emptyFixturePayload);
    await page.goto('/calendar?start=2026-08-03');
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    await expectNoSeriousViolations(page);
});
