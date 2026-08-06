import {expect, test} from '@playwright/test';
import {emptyFixturePayload, fixturePayload} from './test-data.js';

function payloadWithOneFixture() {
    const payload = structuredClone(emptyFixturePayload);
    const match = structuredClone(fixturePayload.matches.find(item => item.id === 'upcoming'));
    match.utcDate = '2026-08-05T00:30:00Z';
    payload.date = '2026-08-05';
    payload.matches = [match];
    payload.total_matches = 1;
    return payload;
}

async function mockFixtures(page, payload = payloadWithOneFixture()) {
    await page.route('**/api/v2/fixtures**', route => route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(payload),
    }));
}

// The Tokyo abbreviation returned by Intl varies by engine (some report
// "JST", others "GMT+9"), so tests read the app's own formatting instead of
// hard-coding a string that would make one browser project flaky.
async function tokyoLabel(page) {
    return page.evaluate(async () => {
        const {formatTimezoneLabel} = await import('/static/js/time-zone.js');
        return formatTimezoneLabel('Asia/Tokyo');
    });
}

test.beforeEach(async ({page}) => {
    await mockFixtures(page);
    await page.goto('/?date=2026-08-05&timezone=UTC');
    // fixtures.js resolves its dynamic-import module graph (top-level await)
    // after the browser's `load` event fires, so the app's own initial
    // fetch can still be in flight when goto() resolves. Wait for a
    // deterministic render signal before interacting with the page.
    await expect(page.locator('#dashboard-status')).toContainText('fixtures shown');
});

test('the trigger sits in the header and shows the current zone abbreviation', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    await expect(page.locator('.app-header').locator('#timezone-trigger')).toBeVisible();
    await expect(trigger.locator('[data-timezone-label]')).toHaveText('UTC');
});

test('aria-haspopup and aria-controls describe the actual popup, not the listbox nested inside it', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    // #timezone-listbox — the element aria-controls references and the one
    // the trigger toggles — has role="dialog"; the role="listbox" is two
    // levels deeper on #timezone-options, so aria-haspopup must describe
    // the dialog, not the listbox.
    await expect(trigger).toHaveAttribute('aria-haspopup', 'dialog');
    await expect(trigger).toHaveAttribute('aria-controls', 'timezone-listbox');
    await expect(page.locator('#timezone-listbox')).toHaveAttribute('role', 'dialog');
});

test('the trigger accessible name includes the IANA zone identifier', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    await expect(trigger).toHaveAccessibleName(/UTC/);

    // Prove it holds for a non-degenerate zone too, where the abbreviation
    // and the identifier are different strings.
    await trigger.click();
    await page.locator('#timezone-search').fill('Tokyo');
    await page.locator('#timezone-options [role="option"]', {hasText: 'Asia/Tokyo'}).click();
    await expect(trigger).toHaveAccessibleName(/Asia\/Tokyo/);
});

test('clicking the trigger opens the popover, expands it, and focuses the search field', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    await trigger.click();
    await expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await expect(page.locator('#timezone-listbox')).toBeVisible();
    await expect(page.locator('#timezone-search')).toBeFocused();
});

test('typing narrows the option list to matching zones', async ({page}) => {
    await page.locator('#timezone-trigger').click();
    await page.locator('#timezone-search').fill('Tokyo');

    const options = page.locator('#timezone-options [role="option"]');
    await expect(options).toHaveCount(1);
    await expect(options.first()).toContainText('Asia/Tokyo');
});

test('selecting a zone updates the trigger, closes the popover, restores focus, and updates the URL', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    const expected = await tokyoLabel(page);

    await trigger.click();
    await page.locator('#timezone-search').fill('Tokyo');
    await page.locator('#timezone-options [role="option"]', {hasText: 'Asia/Tokyo'}).click();

    await expect(trigger.locator('[data-timezone-label]')).toHaveText(expected.shortLabel);
    await expect(page.locator('#timezone-listbox')).toBeHidden();
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
    await expect(trigger).toBeFocused();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('timezone=Asia%2FTokyo');
});

test('the filter-panel timezone select stays in sync with the header control, and vice versa', async ({page}) => {
    await page.locator('#timezone-trigger').click();
    await page.locator('#timezone-search').fill('Tokyo');
    await page.locator('#timezone-options [role="option"]', {hasText: 'Asia/Tokyo'}).click();

    // One value, two controls: the filter-panel select reflects the choice
    // made through the header control.
    await expect(page.locator('#timezone-filter')).toHaveValue('Asia/Tokyo');

    // And the reverse: changing the filter-panel select updates the header
    // trigger, since both read the same underlying state.
    await page.locator('#timezone-filter').selectOption('Europe/London');
    const expectedLondon = await page.evaluate(async () => {
        const {formatTimezoneLabel} = await import('/static/js/time-zone.js');
        return formatTimezoneLabel('Europe/London');
    });
    await expect(page.locator('#timezone-trigger [data-timezone-label]')).toHaveText(expectedLondon.shortLabel);
});

test('pressing Escape closes the popover and restores focus to the trigger', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    await trigger.click();
    await expect(page.locator('#timezone-search')).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(page.locator('#timezone-listbox')).toBeHidden();
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
    await expect(trigger).toBeFocused();
});

test('changing the zone changes the rendered kickoff time', async ({page}) => {
    const kickoff = page.locator('[data-fixture-id="upcoming"] .score-display--kickoff');
    await expect(kickoff).toHaveText('12:30 AM');

    await page.locator('#timezone-trigger').click();
    await page.locator('#timezone-search').fill('Tokyo');
    await page.locator('#timezone-options [role="option"]', {hasText: 'Asia/Tokyo'}).click();

    await expect(kickoff).toHaveText('09:30 AM');
});

test('the popover stays fully inside the viewport at 320px', async ({page}) => {
    await page.setViewportSize({width: 320, height: 800});
    await page.locator('#timezone-trigger').click();
    await expect(page.locator('#timezone-listbox')).toBeVisible();

    const box = await page.locator('#timezone-listbox').boundingBox();
    expect(box).not.toBeNull();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(320);
});

test('clicking outside the popover closes it and restores focus to the trigger', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    await trigger.click();
    await expect(page.locator('#timezone-listbox')).toBeVisible();

    await page.locator('#page-title').click();
    await expect(page.locator('#timezone-listbox')).toBeHidden();
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
    await expect(trigger).toBeFocused();
});

test('the control is reachable and operable by keyboard alone', async ({page}) => {
    const trigger = page.locator('#timezone-trigger');
    const expected = await tokyoLabel(page);

    await trigger.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#timezone-search')).toBeFocused();

    await page.keyboard.type('Tokyo');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');

    await expect(trigger.locator('[data-timezone-label]')).toHaveText(expected.shortLabel);
    await expect(trigger).toBeFocused();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('timezone=Asia%2FTokyo');
});
