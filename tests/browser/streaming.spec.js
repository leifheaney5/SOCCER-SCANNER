import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

const KNOWN_WITH_REGION = {
    id: 'peacock',
    displayName: 'Peacock',
    region: 'US',
    regionKnown: true,
    officialUrl: 'https://www.peacocktv.com/',
    logoPath: '/static/icons/streaming/peacock.svg',
    source: 'espn',
};

const KNOWN_WITHOUT_REGION = {
    id: 'dazn',
    displayName: 'DAZN',
    region: 'Region unknown',
    regionKnown: false,
    officialUrl: 'https://www.dazn.com/',
    source: 'espn',
};

const UNKNOWN_SERVICE = {
    id: null,
    displayName: 'Unverified Stream',
    region: 'Region unknown',
    regionKnown: false,
    officialUrl: null,
    source: 'espn',
};

async function mockFixturesWithStreaming(page) {
    const payload = structuredClone(fixturePayload);
    payload.matches[0].streaming = [KNOWN_WITH_REGION, KNOWN_WITHOUT_REGION, UNKNOWN_SERVICE];
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
}

test('fixture card shows the first streaming service with its region and a +N count', async ({page}) => {
    await mockFixturesWithStreaming(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await expect(page.getByRole('button', {name: 'On TV'})).toHaveCount(0);

    const broadcast = page.locator('[data-fixture-id="live-secret"] .fixture-broadcast');
    await expect(broadcast.locator('xpath=..')).toHaveClass(/fixture-result/);
    await expect(broadcast).toHaveText('Peacock · US +2');
    await expect(broadcast).toHaveAttribute('aria-label', /Peacock \(US\)/);
    await expect(broadcast.locator('img')).toHaveAttribute('width', '18');
    await expect(broadcast.locator('img')).toHaveAttribute('height', '18');
});

test('detail panel renders each streaming service honestly, linking only verified services', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await mockFixturesWithStreaming(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const card = page.locator('.fixture-card[data-fixture-id="live-secret"]');
    await card.getByRole('button', {name: /Open match details/}).click();

    const context = page.locator('#match-context');

    // The known service with a reported region shows its display name and region.
    const known = context.locator('.context-streaming-item', {hasText: 'Peacock'});
    await expect(known).toContainText('Peacock');
    await expect(known).toContainText('US');
    await expect(known.locator('.streaming-service-icon')).toHaveCount(1);
    await expect(known.locator('img')).toHaveAttribute('width', '28');

    // The known service without a reported region shows "Region unknown" —
    // never a guessed region.
    const regionless = context.locator('.context-streaming-item', {hasText: 'DAZN'});
    await expect(regionless).toContainText('Region unknown');
    await expect(regionless.locator('.streaming-service-icon--generic')).toHaveCount(1);

    // The unrecognised service renders as plain text, with no anchor at all.
    const unverified = context.locator('.context-streaming-item', {hasText: 'Unverified Stream'});
    await expect(unverified.locator('a')).toHaveCount(0);

    await expect(context).toContainText(
        'Availability varies by region and subscription. Listings may be incomplete or out of date.',
    );

    // Every rendered anchor is a real, safe outbound link.
    const anchors = context.locator('.context-streaming-link');
    await expect(anchors).toHaveCount(2);
    const anchorCount = await anchors.count();
    for (let index = 0; index < anchorCount; index += 1) {
        const anchor = anchors.nth(index);
        await expect(anchor).toHaveAttribute('target', '_blank');
        const rel = await anchor.getAttribute('rel');
        expect(rel).toContain('noopener');
        expect(rel).toContain('noreferrer');
        const href = await anchor.getAttribute('href');
        expect(href?.startsWith('https://')).toBe(true);
    }
});

test('detail panel shows streaming observation freshness when supplied', async ({page}) => {
    const payload = structuredClone(fixturePayload);
    payload.matches[0].streaming = [{
        displayName: 'Peacock',
        region: 'US',
        regionKnown: true,
        officialUrl: 'https://www.peacocktv.com/',
        logoPath: '/static/icons/streaming/peacock.svg',
        observedAt: '2026-08-03T18:30:00Z',
    }];
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
    await page.goto('/?date=2026-08-03');
    await page.locator('[data-fixture-id="live-secret"] .details-button').click();
    await expect(page.locator('.context-streaming')).toContainText('Observed');
});

test('older cached payloads without a streaming array still show unlinked broadcast names', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');

    const broadcast = page.locator('[data-fixture-id="live-secret"] .fixture-broadcast');
    await expect(broadcast).toHaveText('Streaming: Apple TV');
    await expect(broadcast.locator('a')).toHaveCount(0);
});
