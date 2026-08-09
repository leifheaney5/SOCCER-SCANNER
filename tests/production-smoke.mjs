import {chromium} from '@playwright/test';
import {
    assertProductionDependenciesReady,
    assertUniqueFixtureIds,
} from './production-smoke-invariants.mjs';

const baseURL = (process.env.BASE_URL || '').replace(/\/$/, '');
const expectedSha = (process.env.EXPECTED_SHA || '').toLowerCase();
const expectedEnvironment = (process.env.EXPECTED_ENVIRONMENT || 'production').toLowerCase();
if (!baseURL || !/^[0-9a-f]{40}$/.test(expectedSha) || !/^[a-z][a-z0-9-]{0,31}$/.test(expectedEnvironment)) {
    throw new Error('BASE_URL, a full 40-character EXPECTED_SHA, and a valid EXPECTED_ENVIRONMENT are required.');
}

async function getJson(path, expectedStatuses = [200]) {
    const response = await fetch(`${baseURL}${path}`, {headers: {'Cache-Control': 'no-cache'}});
    if (!expectedStatuses.includes(response.status)) {
        throw new Error(`${path} returned ${response.status}`);
    }
    return {response, body: await response.json()};
}

async function getText(path, expectedStatuses = [200]) {
    const response = await fetch(`${baseURL}${path}`, {headers: {'Cache-Control': 'no-cache'}});
    if (!expectedStatuses.includes(response.status)) {
        throw new Error(`${path} returned ${response.status}`);
    }
    return {response, body: await response.text()};
}

const live = await getJson('/health/live');
const ready = await getJson('/health/ready');
const version = await getJson('/health/version');
if (live.body.status !== 'ok' || ready.body.status !== 'ready') {
    throw new Error('Health endpoints did not report alive/ready.');
}
assertProductionDependenciesReady(ready.body);
if (version.body.commitSha !== expectedSha || ready.body.build.commitSha !== expectedSha) {
    throw new Error(`Live SHA ${version.body.commitSha} does not match ${expectedSha}.`);
}
if (String(version.body.environment).toLowerCase() !== expectedEnvironment) {
    throw new Error(`Unexpected environment ${version.body.environment}; expected ${expectedEnvironment}.`);
}
if (version.body.assetVersion !== expectedSha.slice(0, 12)) {
    throw new Error('Asset version is not derived from the expected revision.');
}

const fixtureDate = new Date().toISOString().slice(0, 10);
const fixture = await getJson(
    `/api/v2/fixtures?date=${fixtureDate}&timezone=UTC`,
    [200, 429, 503],
);
if (fixture.response.status === 200) {
    const allowedStates = new Set(['success', 'empty_confirmed', 'partial', 'stale']);
    if (!allowedStates.has(fixture.body.state) || !Array.isArray(fixture.body.matches)) {
        throw new Error('Fixture API returned an invalid success contract.');
    }
    assertUniqueFixtureIds(fixture.body.matches);
} else if (!['rate_limited', 'provider_unavailable'].includes(fixture.body?.error?.code)) {
    throw new Error('Fixture API failure did not use a stable error contract.');
}

for (const path of [
    '/robots.txt',
    '/sitemap.xml',
    '/static/favicon.svg',
    '/static/manifest.webmanifest',
    '/static/icons/streaming/peacock.svg',
]) {
    const asset = await getText(path);
    if (!asset.body.trim()) throw new Error(`${path} returned an empty body.`);
}
const terms = await getText('/terms');
if (!terms.body.includes('name="robots" content="noindex, follow"')) {
    throw new Error('Terms route is missing its noindex contract.');
}

const browser = await chromium.launch();
try {
    const page = await browser.newPage({viewport: {width: 320, height: 844}, colorScheme: 'dark'});
    const consoleErrors = [];
    const failedAssets = [];
    page.on('console', message => {
        if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', error => consoleErrors.push(error.message));
    page.on('response', response => {
        const url = new URL(response.url());
        if (url.origin === baseURL && url.pathname.startsWith('/static/') && response.status() >= 400) {
            failedAssets.push(`${response.status()} ${url.pathname}`);
        }
    });
    await page.goto(`${baseURL}/?date=${fixtureDate}&timezone=UTC`, {waitUntil: 'networkidle'});
    const assetVersions = await page.evaluate(() => [...document.querySelectorAll('script[src], link[rel="stylesheet"][href]')]
        .map(element => new URL(element.src || element.href))
        .filter(url => url.origin === location.origin)
        .map(url => url.searchParams.get('v')));
    if (!assetVersions.length || assetVersions.some(token => token !== expectedSha.slice(0, 12))) {
        throw new Error(`HTML assets do not all use ${expectedSha.slice(0, 12)}.`);
    }
    const pageSafety = await page.evaluate(() => ({
        revealedScores: document.querySelectorAll('.score-display--revealed').length,
        width: document.documentElement.scrollWidth,
        viewport: document.documentElement.clientWidth,
        timezone: document.querySelector('[data-timezone-label]')?.textContent || '',
        manifest: document.querySelector('link[rel="manifest"]')?.getAttribute('href') || '',
        favicon: document.querySelector('link[rel="icon"]')?.getAttribute('href') || '',
    }));
    if (pageSafety.revealedScores !== 0) throw new Error('Scores were rendered before user reveal.');
    if (!pageSafety.timezone || !pageSafety.manifest || !pageSafety.favicon) {
        throw new Error(`Required public controls/assets are missing: ${JSON.stringify(pageSafety)}.`);
    }
    if (pageSafety.width > pageSafety.viewport + 1) {
        throw new Error(`320px layout overflowed: ${pageSafety.width} > ${pageSafety.viewport}.`);
    }
    if (failedAssets.length || consoleErrors.length) {
        throw new Error(`Browser smoke failures: ${JSON.stringify({failedAssets, consoleErrors})}`);
    }
} finally {
    await browser.close();
}

console.log(JSON.stringify({
    status: 'ok',
    baseURL,
    commitSha: expectedSha,
    environment: expectedEnvironment,
    assetVersion: expectedSha.slice(0, 12),
    fixtureStatus: fixture.response.status,
    fixtureState: fixture.body.state || fixture.body?.error?.code,
    fixtureCount: fixture.body.matches?.length,
    uniqueFixtureIds: fixture.body.matches
        ? new Set(fixture.body.matches.map(match => match.canonicalFixtureId)).size
        : undefined,
}));
