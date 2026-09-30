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

test('fixture card shows provider names and supplied regions for streaming services', async ({page}) => {
    await mockFixturesWithStreaming(page);
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('#fixture-result-count')).toContainText('13 matches');
    await expect(page.getByRole('button', {name: 'On TV'})).toHaveCount(0);

    const broadcast = page.locator('[data-fixture-id="live-secret"] .fixture-broadcast');
    await expect(broadcast.locator('xpath=..')).toHaveClass(/fixture-result/);
    await expect(broadcast).toHaveText('Peacock (Streaming) (US) · DAZN (Streaming) · Unverified Stream (Streaming)');
    await expect(broadcast).toHaveAttribute('aria-label', /Where to watch: Peacock \(Streaming\) \(US\)/);
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
    await expect(broadcast).toHaveText('Apple TV (Streaming) (us)');
    await expect(broadcast.locator('a')).toHaveCount(0);
});

test('fixture cards and details show every TV and streaming option plus honest gaps', async ({page}) => {
    const payload = structuredClone(fixturePayload);
    payload.matches[0].whereToWatch = [
        {...KNOWN_WITH_REGION, type: 'STREAMING'},
        {id: 'espn', displayName: 'ESPN', type: 'TV', region: 'US', officialUrl: 'https://www.espn.com/soccer/'},
        {id: 'espn', displayName: 'ESPN', type: 'STREAMING', region: 'US', officialUrl: 'https://www.espn.com/soccer/'},
        {id: 'usa-network', displayName: 'USA Network', type: 'TV', region: 'US', officialUrl: 'https://www.usanetwork.com/'},
    ];
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
    await page.goto('/?date=2026-08-03');

    const listedCard = page.locator('[data-fixture-id="live-secret"] .fixture-broadcast');
    await expect(listedCard).toContainText('Peacock');
    await expect(listedCard).toContainText('ESPN');
    await expect(listedCard).toContainText('USA Network');
    await expect(listedCard).toContainText('ESPN (TV)');
    await expect(listedCard).toContainText('ESPN (Streaming)');
    await expect(listedCard).toHaveAttribute('aria-label', /ESPN \(TV\).*ESPN \(Streaming\)/);
    await expect(listedCard).toHaveAttribute('aria-label', /Where to watch/);

    const unlistedCard = page.locator('.fixture-card[data-fixture-id="upcoming"]');
    await expect(unlistedCard).toContainText('Broadcast listing not provided');

    await page.setViewportSize({width: 1280, height: 900});
    await page.locator('[data-fixture-id="live-secret"] .details-button').click();
    const details = page.locator('#match-context');
    await expect(details.locator('.context-streaming-item')).toHaveCount(4);
    await expect(details).toContainText('USA Network');
    await expect(details.locator('.context-streaming-link[href="https://www.usanetwork.com/"]')).toHaveCount(1);
    await expect(details.locator('.context-streaming-item').filter({hasText: 'ESPN'}).nth(0)).toContainText('TV');
    await expect(details.locator('.context-streaming-item').filter({hasText: 'ESPN'}).nth(1)).toContainText('Streaming');
});

test('detail panel rejects HTTPS links that do not match the verified provider', async ({page}) => {
    const payload = structuredClone(fixturePayload);
    payload.matches[0].whereToWatch = [{
        id: 'peacock',
        displayName: 'Peacock',
        type: 'STREAMING',
        officialUrl: 'https://unrelated.example/watch',
    }];
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
    await page.goto('/?date=2026-08-03');
    await page.locator('[data-fixture-id="live-secret"] .details-button').click();

    const item = page.locator('.context-streaming-item', {hasText: 'Peacock'});
    await expect(item.locator('a')).toHaveCount(0);
    await expect(item.locator('.context-streaming-name')).toHaveText('Peacock');
});

test('region preference filters watch listings, keeps coverage truthful, and persists', async ({page}) => {
    const payload = structuredClone(fixturePayload);
    payload.matches[0].whereToWatch = [
        {...KNOWN_WITH_REGION, type: 'STREAMING'},
        {id: null, displayName: 'BBC Sport', type: 'TV', region: 'GB', officialUrl: null},
    ];
    payload.matches[0].broadcastCoverage = {
        status: 'available',
        regions: [{region: 'GB', status: 'available'}, {region: 'US', status: 'available'}],
    };
    payload.matches[2].whereToWatch = [];
    payload.matches[2].broadcastCoverage = {
        status: 'unverified',
        regions: [{region: 'GB', status: 'unverified'}, {region: 'US', status: 'unverified'}],
    };
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
    await page.goto('/?date=2026-08-03');
    await expect(page.locator('[data-fixture-id="live-secret"] .fixture-broadcast')).toContainText('BBC Sport');

    await page.locator('#broadcast-region').selectOption('US');
    await expect(page.locator('[data-fixture-id="live-secret"] .fixture-broadcast')).toContainText('Peacock');
    await expect(page.locator('[data-fixture-id="live-secret"] .fixture-broadcast')).not.toContainText('BBC Sport');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('soccer-radar:broadcast-region'))).toBe('US');

    await page.locator('#broadcast-region').selectOption('GB');
    await page.locator('[data-fixture-id="upcoming"] .details-button').click();
    await expect(page.locator('#match-context .context-streaming-empty')).toHaveText('Not verified yet for GB');

    await page.reload();
    await expect(page.locator('#broadcast-region')).toHaveValue('GB');
});

test('confirmed absence and stale listings have distinct accessible fallback labels', async ({page}) => {
    const payload = structuredClone(fixturePayload);
    payload.matches[2].whereToWatch = [];
    payload.matches[2].broadcastCoverage = {
        status: 'confirmed_none',
        regions: [{region: 'US', status: 'confirmed_none'}],
    };
    payload.matches[1].whereToWatch = [];
    payload.matches[1].broadcastCoverage = {
        status: 'stale',
        regions: [{region: 'US', status: 'stale'}],
    };
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
    await page.goto('/?date=2026-08-03');
    await page.locator('#broadcast-region').selectOption('US');

    const none = page.locator('[data-fixture-id="upcoming"] .fixture-broadcast');
    await expect(none).toHaveText('No listing confirmed for US');
    await expect(none).toHaveAttribute('aria-label', 'Where to watch: No listing confirmed for US');

    const stale = page.locator('[data-fixture-id="finished-secret"] .fixture-broadcast');
    await expect(stale).toHaveText('Broadcast listing may be out of date');
    await expect(stale).toHaveAttribute('aria-label', 'Where to watch: Broadcast listing may be out of date');
});
