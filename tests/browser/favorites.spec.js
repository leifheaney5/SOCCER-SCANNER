import {expect, test} from '@playwright/test';
import {fixturePayload} from './test-data.js';

async function mockFixtures(page) {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(fixturePayload),
    }));
}

test('favorites repository validates, deduplicates, exports, imports, and clears', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    const result = await page.evaluate(async () => {
        const {createFavoritesRepository} = await import('/static/js/favorites.js');
        localStorage.removeItem('soccer-scanner:favorites');
        const repository = createFavoritesRepository(localStorage);
        repository.toggle('teams', 'arsenal');
        repository.toggle('teams', 'arsenal');
        repository.toggle('teams', 'arsenal');
        repository.toggle('competitions', 'premier-league');
        repository.toggle('fixtures', 'fixture-1');
        const exported = repository.exportText();
        const imported = repository.importText(exported);
        localStorage.setItem('soccer-scanner:favorites', '{broken');
        const recovered = createFavoritesRepository(localStorage).snapshot();
        repository.clear();
        return {imported, recovered, cleared: repository.snapshot()};
    });

    expect(result.imported).toEqual({
        version: 1,
        teams: ['arsenal'],
        competitions: ['premier-league'],
        fixtures: ['fixture-1'],
    });
    expect(result.recovered).toEqual({version: 1, teams: [], competitions: [], fixtures: []});
    expect(result.cleared).toEqual({version: 1, teams: [], competitions: [], fixtures: []});
});

test('fixture favorites persist and favorites-only is URL-backed', async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-03');
    const favorite = page.locator('[data-fixture-id="live-secret"] [data-action="toggle-favorite"]');
    await favorite.click();
    await expect(favorite).toHaveAttribute('aria-pressed', 'true');

    await page.reload();
    await expect(page.locator('[data-fixture-id="live-secret"] [data-action="toggle-favorite"]')).toHaveAttribute('aria-pressed', 'true');
    await page.locator('#favorites-only').check();
    await expect(page.locator('#fixture-result-count')).toContainText('1 match');
    await expect(page.getByRole('heading', {name: 'Your matches'})).toBeVisible();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('favorites=1');
});
