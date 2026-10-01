const { chromium } = require('playwright');
const out = process.argv[2];
(async () => {
  const b = await chromium.launch();
  let failed = 0;
  for (const width of [390, 320]) {
    const ctx = await b.newContext({ viewport: { width, height: 844 }, isMobile: true, deviceScaleFactor: 2, serviceWorkers: 'block' });
    const p = await ctx.newPage();
    await p.goto('https://soccer-radar.com/', { waitUntil: 'networkidle' });
    await p.waitForSelector('.fixture-card');
    const cssHasFix = await p.evaluate(() => [...document.styleSheets].some(s => { try { return [...s.cssRules].some(r => r.cssText && r.cssText.includes(':has(.fixture-meta > *)')); } catch { return false; } }));
    const r = await p.evaluate(() => {
      const cards = [...document.querySelectorAll('.fixture-card')];
      let withVenue = 0, overlaps = 0;
      for (const c of cards) {
        const v = c.querySelector('.fixture-venue'), m = c.querySelector('.fixture-mobile-meta');
        if (!v || !m) continue;
        withVenue++;
        const a = v.getBoundingClientRect(), d = m.getBoundingClientRect();
        if (a.top < d.bottom && d.top < a.bottom && a.left < d.right && d.left < a.right) overlaps++;
      }
      return { cards: cards.length, withVenue, overlaps };
    });
    console.log(`${width}px cssHasFix=${cssHasFix} cards=${r.cards} withVenue=${r.withVenue} overlaps=${r.overlaps}`);
    if (!cssHasFix || r.overlaps || !r.withVenue) failed = 1;
    if (width === 390) {
      const card = p.locator('.fixture-card:has(.fixture-venue)').first();
      await card.scrollIntoViewIfNeeded(); await p.waitForTimeout(300);
      await card.screenshot({ path: `${out}/live-card-390.png` });
    }
    await ctx.close();
  }
  await b.close();
  console.log(failed ? 'RESULT: FAIL' : 'RESULT: PASS');
  process.exit(failed);
})();
