const { chromium } = require('playwright');
const fs = require('fs');
const out = process.argv[2];
const logo = fs.readFileSync(require('path').join(__dirname, '../../../static/favicon.svg'), 'utf8');
const font = `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800&family=JetBrains+Mono:wght@500&display=block" rel="stylesheet">`;
const base = `*{margin:0;box-sizing:border-box}body{font-family:Inter,sans-serif;color:#fff}`;
const card = (title, sub, foot) => `<!doctype html><html><head>${font}<style>${base}
body{width:1080px;height:1920px;background:radial-gradient(circle at 50% 42%,#14260a 0,#000 62%);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:56px}
.logo svg{width:340px;height:340px;border-radius:44px;box-shadow:0 0 120px rgba(124,255,0,.28)}
h1{font-size:108px;font-weight:800;letter-spacing:6px}h1 span{color:#7CFF00}
p{font-size:54px;font-weight:500;color:#d6d6d6;text-align:center;line-height:1.3}
.foot{font-family:'JetBrains Mono',monospace;font-size:44px;color:#7CFF00;margin-top:40px}</style></head>
<body><div class="logo">${logo}</div><h1>SOCCER <span>RADAR</span></h1><p>${sub}</p>${foot ? `<div class="foot">${foot}</div>` : ''}</body></html>`;
const caption = (text) => `<!doctype html><html><head>${font}<style>${base}
body{width:1080px;height:340px;background:transparent;display:flex;align-items:center;justify-content:center}
.c{background:rgba(0,0,0,.86);border:3px solid #7CFF00;border-radius:36px;padding:34px 52px;font-size:60px;font-weight:700;line-height:1.18;text-align:center;max-width:980px;box-shadow:0 18px 60px rgba(0,0,0,.6)}</style></head>
<body><div class="c">${text}</div></body></html>`;
const captions = {
  c1: 'Today&rsquo;s fixtures,<br>in your local time',
  c2: 'Scores stay hidden<br>until <span style="color:#7CFF00">you</span> choose',
  c3: 'Jump to live, upcoming<br>or finished',
  c4: 'Find your team<br>in seconds',
  c5: 'Kickoff, venue and<br>calendar in one tap',
  c6: 'Filter by competition<br>and time window',
};
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.setContent(card('', 'Spoiler-safe soccer fixtures'), { waitUntil: 'networkidle' });
  await p.screenshot({ path: `${out}/title.png` });
  await p.setContent(card('', 'Fixtures without the spoilers.', 'soccer-radar.com'), { waitUntil: 'networkidle' });
  await p.screenshot({ path: `${out}/end.png` });
  await p.setViewportSize({ width: 1080, height: 340 });
  for (const [k, t] of Object.entries(captions)) {
    await p.setContent(caption(t), { waitUntil: 'networkidle' });
    await p.screenshot({ path: `${out}/${k}.png`, omitBackground: true });
  }
  await b.close();
})();
