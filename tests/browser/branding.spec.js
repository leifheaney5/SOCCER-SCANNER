import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

test('the header exposes the accessible home link with an inline mark', async ({page}) => {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
    await page.goto('/?date=2026-08-03');

    const homeLink = page.getByRole('link', {name: 'Soccer Scanner home'});
    await expect(homeLink).toBeVisible();
    await expect(homeLink.locator('svg')).toHaveCount(1);
    await expect(homeLink.locator('svg')).toHaveAttribute('aria-hidden', 'true');
});

test('the header mark stays proportionate to the wordmark on legacy team and table pages', async ({page}) => {
    // /teams and /league-tables load their own stylesheets (teams.css, standings.css) that
    // predate the shared app-header design and once set .app-title to font-size: 2.2em. Both
    // stylesheets already carry a later, higher-specificity override bringing it back to the
    // shared header's 15px; this guards that override so a future edit can't silently drop it
    // and leave the fixed-size 26x26 mark dwarfed by an oversized wordmark.
    for (const path of ['/teams', '/league-tables']) {
        await page.goto(path);

        const homeLink = page.getByRole('link', {name: 'Soccer Scanner home'});
        await expect(homeLink).toBeVisible();
        await expect(homeLink.locator('.app-title-mark')).toHaveCount(1);

        const fontSize = await page.locator('.app-title').evaluate(el => getComputedStyle(el).fontSize);
        expect(fontSize, path).toBe('15px');
    }
});

test('every declared icon resolves with an image content type', async ({page}) => {
    const iconPaths = [
        '/static/favicon.svg',
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
