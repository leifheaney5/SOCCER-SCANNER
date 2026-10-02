// Records a scripted soccer-radar.com walkthrough as full-resolution frames.
// Output: <out>/<dir>/fNNNNN.jpg plus <out>/timeline.json where each frame has
// a duration; stepped (scroll) frames get exactly 1/FPS, real-time frames get
// their measured on-screen duration.
const { chromium } = require('playwright');
const fs = require('fs');
const [out, dir] = [process.argv[2], process.argv[3] || 'hd2'];
const FPS = 30;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(`${out}/${dir}`, { recursive: true });
  const b = await chromium.launch({ args: ['--force-device-scale-factor=2.6666667'] });
  const ctx = await b.newContext({
    viewport: { width: 405, height: 720 }, deviceScaleFactor: 8 / 3, isMobile: true, hasTouch: true,
    timezoneId: 'America/New_York', colorScheme: 'dark', serviceWorkers: 'block',
  });
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);

  // Timeline entries: { name, dur } (dur filled in for real-time frames later).
  const timeline = [];
  const scenes = {};
  let clock = 0;            // output-time cursor in seconds
  let lastReal = null;      // { idx, ts } of the most recent real-time frame
  let stepping = false;
  let frameWaiter = null;

  const closeReal = (nowTs) => {
    if (lastReal) { timeline[lastReal.idx].dur = Math.max(0, nowTs - lastReal.ts); clock += timeline[lastReal.idx].dur; lastReal = null; }
  };
  cdp.on('Page.screencastFrame', async (f) => {
    const name = `${dir}/f${String(timeline.length).padStart(5, '0')}.jpg`;
    fs.writeFileSync(`${out}/${name}`, Buffer.from(f.data, 'base64'));
    const ts = f.metadata.timestamp;
    if (stepping) {
      timeline.push({ name, dur: 1 / FPS }); clock += 1 / FPS;
    } else {
      closeReal(ts);
      timeline.push({ name, dur: 0 });
      lastReal = { idx: timeline.length - 1, ts };
    }
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch {}
    if (frameWaiter) { const w = frameWaiter; frameWaiter = null; w(); }
  });
  const nextFrame = () => new Promise(res => { frameWaiter = res; setTimeout(() => { if (frameWaiter === res) { frameWaiter = null; res(); } }, 250); });
  // Scene marks in output time: close the open real-time frame at "now".
  const mark = (k) => { closeReal(Date.now() / 1000); if (timeline.length) lastReal = null; scenes[k] = clock; reopen(); };
  // After a mark, the last frame continues to be on screen; re-open it as real-time from now.
  const reopen = () => { if (timeline.length) { const idx = timeline.length; const prev = timeline[idx - 1]; timeline.push({ name: prev.name, dur: 0 }); lastReal = { idx, ts: Date.now() / 1000 }; } };

  const tap = async (sel) => {
    const el = p.locator(sel).first();
    const box = await el.boundingBox();
    const [x, y] = [box.x + box.width / 2, box.y + box.height / 2];
    await p.evaluate(([x, y]) => {
      const d = document.createElement('div');
      d.style.cssText = `position:fixed;left:${x - 22}px;top:${y - 22}px;width:44px;height:44px;border-radius:50%;border:3px solid #7CFF00;background:rgba(124,255,0,.25);z-index:2147483647;pointer-events:none;transition:transform .45s ease-out,opacity .45s ease-out`;
      document.body.appendChild(d);
      requestAnimationFrame(() => { d.style.transform = 'scale(1.6)'; d.style.opacity = '0'; });
      setTimeout(() => d.remove(), 600);
    }, [x, y]);
    await sleep(220);
    await el.click();
  };
  // Deterministic scroll: one scroll position per output frame.
  const steppedScroll = async (dy, seconds) => {
    closeReal(Date.now() / 1000);
    stepping = true;
    const start = await p.evaluate(() => scrollY);
    const n = Math.round(seconds * FPS);
    for (let i = 1; i <= n; i++) {
      const k = i / n, e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const wait = nextFrame();
      await p.evaluate((y) => scrollTo({ top: y, behavior: 'instant' }), Math.round(start + dy * e));
      await wait;
    }
    stepping = false;
    reopen();
  };

  await p.goto('https://soccer-radar.com/', { waitUntil: 'networkidle' });
  await p.waitForSelector('.details-button');
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 94, maxWidth: 1080, maxHeight: 1920, everyNthFrame: 1 });
  await sleep(700);
  mark('home'); await sleep(3000);
  mark('scroll'); await steppedScroll(1100, 3.2); await sleep(1500);
  await p.evaluate(() => scrollTo({ top: 0, behavior: 'instant' })); await sleep(250);
  mark('tabs'); await tap('#status-live'); await sleep(2000); await tap('#status-upcoming'); await sleep(1500);
  // Search for a team that is actually listed now, so the script works on any day.
  // Cards are kickoff-ordered; the last Upcoming card is the least likely to carry
  // a stale provider "scheduled" status for a match that already kicked off.
  if (!(await p.locator('.fixture-card .team-name').count())) { await tap('#status-all'); await sleep(800); }
  const team = (await p.locator('.fixture-card').last().locator('.team-name').first().textContent()).trim();
  mark('search'); await tap('#fixture-search'); await p.keyboard.type(team, { delay: 110 }); await sleep(1500);
  mark('details'); await tap('.details-button'); await sleep(3400);
  await p.keyboard.press('Escape'); await sleep(400);
  await p.evaluate(() => scrollTo({ top: 0, behavior: 'instant' })); await sleep(250);
  mark('filters'); await tap('#filter-toggle'); await sleep(3200);
  mark('end');
  await cdp.send('Page.stopScreencast');
  await ctx.close(); await b.close();
  const frames = timeline.filter(t => t.dur > 0);
  fs.writeFileSync(`${out}/timeline.json`, JSON.stringify({ scenes, frames }, null, 1));
  console.log('scenes', JSON.stringify(scenes), 'frames', frames.length, 'total', frames.reduce((a, f) => a + f.dur, 0).toFixed(2));
})().catch(e => { console.error(e); process.exit(1); });
