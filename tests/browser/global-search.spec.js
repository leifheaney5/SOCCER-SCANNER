import {test, expect} from '@playwright/test';

test('global search debounces requests and renders score-free typed results', async ({page}) => {
    let requests = 0;
    await page.route('**/api/v2/search**', async route => {
        requests += 1;
        await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({
                state: 'success',
                query: 'Arsenal',
                total: 2,
                results: [
                    {type: 'team', id: 'arsenal', name: 'Arsenal', canonicalId: 'arsenal'},
                    {type: 'fixture', id: 'fx_' + 'a'.repeat(24), date: '2026-08-13', utcDate: '2026-08-13T18:00:00Z',
                        status: {code: 'scheduled'}, homeTeam: {id: 'arsenal', name: 'Arsenal'},
                        awayTeam: {id: 'chelsea', name: 'Chelsea'}, competition: {id: 'premier-league', name: 'Premier League'},
                        score: {fullTime: {home: 97, away: 96}}},
                ],
                days: [{date: '2026-08-13', state: 'success', matches: 1}],
            }),
        });
    });

    await page.goto('/?date=2026-08-13');
    await page.getByRole('button', {name: 'Search anywhere'}).click();
    const input = page.locator('#global-search-input');
    await expect(input).toBeFocused();
    await input.fill('Arse');
    await input.pressSequentially('nal');
    await expect(page.locator('#global-search-results')).toContainText('Arsenal');
    await expect(page.locator('#global-search-results')).toContainText('Premier League');
    await expect(page.locator('#global-search-results')).not.toContainText('97');
    await expect.poll(() => requests).toBe(1);

    await input.press('ArrowDown');
    await expect(page.locator('[role="option"]').first()).toHaveAttribute('aria-selected', 'true');
    await input.press('Escape');
    await expect(page.locator('#global-search-dialog')).toBeHidden();
});

test('global search becomes a full-screen, scroll-safe surface at 320px', async ({page}) => {
    await page.setViewportSize({width: 320, height: 568});
    await page.route('**/api/v2/search**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({state: 'success', results: [], total: 0, days: []}),
    }));
    await page.goto('/?date=2026-08-13');
    await page.getByRole('button', {name: 'Search anywhere'}).click();
    await expect(page.locator('#global-search-dialog')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
});
