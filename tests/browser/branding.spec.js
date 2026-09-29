import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

test.beforeEach(async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
});

test('the header exposes the accessible home link with an inline mark', async ({page}) => {
    await page.goto('/?date=2026-08-03');

    const homeLink = page.getByRole('link', {name: 'Soccer Radar home'});
    await expect(homeLink).toBeVisible();
    await expect(homeLink.locator('svg')).toHaveCount(1);
    await expect(homeLink.locator('svg')).toHaveAttribute('aria-hidden', 'true');
    await expect(homeLink.locator('.app-title-mark circle')).toHaveCount(8);
});

test('the full Soccer Radar wordmark remains visible at phone width', async ({page}) => {
    await page.setViewportSize({width: 320, height: 844});
    await page.goto('/?date=2026-08-03');

    const wordmark = page.locator('.app-title-wordmark');
    await expect(wordmark).toBeVisible();
    await expect(wordmark).toContainText('SOCCER');
    await expect(wordmark).toContainText('RADAR');
    const homeLinkBounds = await page.getByRole('link', {name: 'Soccer Radar home'}).boundingBox();
    expect(homeLinkBounds.x + homeLinkBounds.width).toBeLessThanOrEqual(320);
});

test('the footer is centered and identifies the copyright and app version', async ({page}) => {
    await page.goto('/?date=2026-08-03');

    const footer = page.locator('.app-footer');
    const container = footer.locator('.footer-container');
    await expect(container).toHaveCSS('justify-content', 'center');
    await expect(container).toContainText('© 2026 Soccer Radar');
    await expect(container).toContainText('Version 2.0.0');
});

test('the header mark stays proportionate to the wordmark on legacy team and table pages', async ({page}) => {
    // /teams and /league-tables load their own stylesheets (teams.css, standings.css) that
    // predate the shared app-header design and once set .app-title to font-size: 2.2em. Both
    // stylesheets already carry a later, higher-specificity override bringing it back to the
    // shared header's 15px; this guards that override so a future edit can't silently drop it
    // and leave the fixed-size 34x34 mark dwarfed by an oversized wordmark.
    for (const path of ['/teams', '/league-tables']) {
        await page.goto(path);

        const homeLink = page.getByRole('link', {name: 'Soccer Radar home'});
        await expect(homeLink).toBeVisible();
        await expect(homeLink.locator('.app-title-mark')).toHaveCount(1);

        const fontSize = await page.locator('.app-title').evaluate(el => getComputedStyle(el).fontSize);
        expect(fontSize, path).toBe('15px');
    }
});

test('page metadata and the favicon use the Soccer Radar identity and canonical origin', async ({page}) => {
    await page.goto('/?date=2026-08-03');

    await expect(page).toHaveTitle('Fixtures | Soccer Radar');
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'https://soccer-radar.com/');
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', 'https://soccer-radar.com/');

    const websiteJsonLd = await page.locator('script[type="application/ld+json"]').textContent();
    expect(JSON.parse(websiteJsonLd)['@graph'][0].name).toBe('Soccer Radar');

    const favicon = await page.request.get('/static/favicon.svg');
    expect(await favicon.text()).toContain('aria-label="Soccer Radar"');
});

test('every declared icon resolves with an image content type', async ({page}) => {
    const iconPaths = [
        '/static/favicon.svg',
        '/static/branding/soccer-radar-logo.svg',
        '/static/branding/soccer-radar-logo-outlined.svg',
        '/static/icons/favicon-32.png',
        '/static/icons/apple-touch-icon.png',
        '/static/icons/icon-192.png',
        '/static/icons/icon-512.png',
        '/static/icons/icon-maskable-512.png',
        '/static/social-card.png',
    ];

    for (const path of iconPaths) {
        const response = await page.request.get(path);
        expect(response.status(), path).toBe(200);
        expect(response.headers()['content-type'], path).toMatch(/^image\//);
    }
});

test('the manifest parses and every declared icon URL resolves', async ({page}) => {
    await page.goto('/?date=2026-08-03');

    const manifestUrl = await page.locator('link[rel="manifest"]').getAttribute('href');
    const manifestResponse = await page.request.get(manifestUrl);
    expect(manifestResponse.status()).toBe(200);
    const manifest = await manifestResponse.json();

    expect(manifest.icons.length).toBeGreaterThan(0);
    const maskable = manifest.icons.filter(icon => (icon.purpose || '').includes('maskable'));
    expect(maskable.length).toBeGreaterThan(0);
    for (const icon of maskable) {
        expect(icon.src).toMatch(/\.png$/);
    }

    for (const icon of manifest.icons) {
        const response = await page.request.get(icon.src);
        expect(response.status(), icon.src).toBe(200);
    }
});
