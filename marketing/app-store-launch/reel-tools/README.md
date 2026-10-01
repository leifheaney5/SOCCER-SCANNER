# Reel tools

Rebuilds `../soccer-radar-reel.mp4` from the live site. Needs the repo's
`node_modules` (`npm ci`), Python 3, and `ffmpeg` on `PATH`. Run from this
folder; `<out>` is any empty scratch directory.

```bash
node cards.cjs <out>                  # title, end and caption PNGs (Inter via Google Fonts)
node record.cjs <out> hd              # 1080x1920 frames from https://soccer-radar.com + timeline.json
python compose.py <out> <out>/reel.mp4
node live-check.cjs <out>             # optional: asserts no venue/competition overlap at 390/320px
```

- `record.cjs` drives a 405×720 phone viewport. It launches Chromium with
  `--force-device-scale-factor` because headless screencasts otherwise come
  out at CSS-pixel size. Scroll is stepped one frame at a time for a true
  30 fps.
- The search scene types the first team currently listed, so the script
  works on any day. Captions live in `cards.cjs`. Keep them within the safe
  claims in `marketing/README.md`.
- `compose.py` writes H.264 High, `yuv420p` limited-range BT.709, with a
  silent AAC track.
- Captures show real, live data. Check the frames for revealed scores and
  for provider statuses that look wrong before publishing.
