import {test, expect} from '@playwright/test';
import {sanitizeFixturePayload} from '../../static/js/offline-cache.js';
import {fixturePayload} from './test-data.js';

test.use({serviceWorkers: 'allow'});

test('manifest is installable and the worker controls the application scope', async ({page}) => {
    await page.goto('/offline');
    const manifest = await page.evaluate(async () => fetch('/static/manifest.webmanifest').then(response => response.json()));
    expect(manifest.name).toBe('Soccer Scanner');
    expect(manifest.start_url).toBe('/');
    expect(manifest.scope).toBe('/');
    expect(manifest.display).toBe('standalone');

    const registration = await page.evaluate(async () => {
        const ready = await navigator.serviceWorker.ready;
        return {scope: ready.scope, scriptURL: ready.active?.scriptURL};
    });
    expect(registration.scope).toBe('http://127.0.0.1:5100/');
    expect(registration.scriptURL).toContain('/static/sw.js');
});

test('offline fixture snapshots remove scores and exclude live matches', () => {
    const cached = sanitizeFixturePayload(fixturePayload, '2026-08-04T00:00:00Z');
    expect(cached.offline).toBe(true);
    expect(cached.stale).toBe(true);
    expect(cached.matches.some(match => match.canonicalFixtureId === 'live-secret')).toBe(false);
    expect(JSON.stringify(cached)).not.toContain('97');
    expect(JSON.stringify(cached)).not.toContain('96');
    expect(cached.matches.every(match => match.score === undefined)).toBe(true);
});

test('offline snapshots preserve verified streaming metadata while removing scores', () => {
    const payload = structuredClone(fixturePayload);
    payload.matches.find(match => match.id === 'upcoming').streaming = [{
        displayName: 'Peacock',
        region: 'US',
        officialUrl: 'https://www.peacocktv.com/',
        observedAt: '2026-08-03T18:00:00Z',
    }];
    const cached = sanitizeFixturePayload(payload, '2026-08-04T00:00:00Z');
    const stored = cached.matches.find(match => match.id === 'upcoming');

    expect(stored.streaming[0].displayName).toBe('Peacock');
    expect(stored.streaming[0].observedAt).toBe('2026-08-03T18:00:00Z');
    expect(stored.score).toBeUndefined();
});

test('installed shell supplies an explicit offline page', async ({page, context, browserName}) => {
    await page.goto('/offline');
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.reload();
    await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
    const cachedOfflineShell = await page.evaluate(async () => Boolean(await caches.match('/offline')));
    expect(cachedOfflineShell).toBe(true);
    if (browserName === 'webkit') return;
    await context.setOffline(true);
    await page.goto('/uncached-while-offline');
    await expect(page.getByRole('heading', {name: 'You are offline'})).toBeVisible();
});

test('installed shell caches the source transparency page', async ({page}) => {
    await page.goto('/offline');
    await page.evaluate(() => navigator.serviceWorker.ready);
    const cachedSourcesPage = await page.evaluate(async () => Boolean(await caches.match('/data-sources')));
    expect(cachedSourcesPage).toBe(true);
});
