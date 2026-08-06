import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

// ESPN emits no country for a competition, so the server only adds
// `competition.area` for competitions the registry has verified. These specs
// exercise the browser side of that contract: the filter must actually work
// when at least two countries resolve, and must hide itself — not just sit
// there empty — when fewer than two do.

function mappedCountriesPayload() {
    const payload = structuredClone(fixturePayload);
    payload.matches = payload.matches.slice(0, 3);
    // matches[0] and [1] are Premier League fixtures; matches[2] is the
    // Scottish Premiership fixture (Celtic vs Dundee) — the assigned areas
    // stay consistent with the competitions actually on each match.
    payload.matches[0].competition.area = {name: 'England'};
    payload.matches[1].competition.area = {name: 'England'};
    payload.matches[2].competition.area = {name: 'Scotland'};
    return payload;
}

function unmappedCountriesPayload() {
    const payload = structuredClone(fixturePayload);
    for (const match of payload.matches) {
        delete match.competition.area;
    }
    return payload;
}

test('the country control is visible, lists resolved countries, and filters fixtures when at least two resolve', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(mappedCountriesPayload()),
    }));
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');

    const control = page.locator('label.select-control', {has: page.locator('#country-filter')});
    await expect(control).toBeVisible();

    const options = await page.locator('#country-filter option').allTextContents();
    expect(options).toEqual(['All countries', 'England', 'Scotland']);

    await expect(page.locator('.fixture-card')).toHaveCount(3);
    await page.locator('#country-filter').selectOption('England');
    await expect.poll(() => page.evaluate(() => location.search)).toContain('country=England');
    await expect(page.locator('.fixture-card')).toHaveCount(2);
    await expect(page.locator('.fixture-card[data-fixture-id="live-secret"]')).toBeVisible();
    await expect(page.locator('.fixture-card[data-fixture-id="finished-secret"]')).toBeVisible();
    await expect(page.locator('.fixture-card[data-fixture-id="upcoming"]')).toHaveCount(0);
});

test('the country control hides itself, and clears an unresolvable selection, when fewer than two countries resolve', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(unmappedCountriesPayload()),
    }));
    await page.goto('/?date=2026-08-03&country=England');
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');

    const control = page.locator('label.select-control', {has: page.locator('#country-filter')});
    await expect(control).toBeHidden();

    // A country carried in from the URL cannot be honored when the control
    // is hidden, so it must be reconciled away rather than silently applied.
    await expect.poll(() => page.evaluate(() => location.search)).not.toContain('country=');

    // With no usable country filter, every fixture in the payload still shows
    // (some competition groups collapse behind a "Show all" toggle, so the
    // result count — not a raw `.fixture-card` count — is the honest total).
    await expect(page.locator('#fixture-result-count')).toContainText(`${fixturePayload.matches.length} matches`);
});
