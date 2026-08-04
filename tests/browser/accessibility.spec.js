import AxeBuilder from '@axe-core/playwright';
import {expect, test} from '@playwright/test';
import {emptyFixturePayload, fixturePayload, teamPayload} from './test-data.js';

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

test('mobile navigation and nested fixture dialogs remain accessible', async ({page}) => {
    await page.setViewportSize({width: 390, height: 844});
    await mockFixtures(page);
    await page.route('**/api/v2/teams/*/analysis', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(teamPayload),
    }));
    await page.goto('/?date=2026-08-03');
    await page.locator('#nav-toggle').click();
    await expect(page.locator('#primary-navigation')).toBeVisible();
    await expectNoSeriousViolations(page);
    await page.locator('#nav-toggle').click();

    await page.locator('[data-fixture-id="live-secret"] .details-button').click();
    await expect(page.locator('#match-context-dialog')).toBeVisible();
    await expectNoSeriousViolations(page);
    await page.locator('#match-context-dialog').getByRole('button', {name: 'Open Arsenal intelligence'}).click();
    await expect(page.locator('#team-drawer')).toContainText('Arsenal');
    await expectNoSeriousViolations(page);
});

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

test('/calendar has no serious accessibility violations', async ({page}) => {
    await mockFixtures(page, emptyFixturePayload);
    await page.goto('/calendar?start=2026-08-03');
    await expect(page.locator('#calendar-status')).toContainText('7 days loaded');
    await expectNoSeriousViolations(page);
});
