# Soccer Radar — App Store launch kit

Prepared 2026-10-01 against `main` at `9fe711a`. Covers the three open release
blockers (screenshots, Terms, physical-device review) plus the product reel.
Nothing here was submitted, uploaded or committed.

---

## 1. Screenshots

### What App Store Connect accepts (checked 2026-10-01 against Apple's
[screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications))

| Slot | Portrait pixels | Required? |
| --- | --- | --- |
| iPhone 6.9" | 1320×2868, 1290×2796, 1260×2736 | Either 6.9" **or** 6.5" is required |
| iPhone 6.5" | 1284×2778, 1242×2688 | Only if 6.9" is not provided |
| iPad 13" | 2064×2752, 2048×2732 | Required: the app runs on iPad |

1–10 images per slot, PNG or JPEG, **no alpha channel**.

**The 6.5" set isn't strictly required.** A 6.9" set (from iPhone 14 Pro Max
through 17 Pro Max, or iPhone Air) satisfies the iPhone requirement.

### Capture paths

**A. Physical devices via TestFlight (fastest, real release build).**
1. Install the latest TestFlight build on a 6.9" iPhone (or a 6.5" model such
   as iPhone 11 Pro Max, 12/13 Pro Max, or 14 Plus) and on a 13" iPad.
2. Screenshot with Side + Volume Up.
3. Transfer the originals by AirDrop or Photos → Export Unmodified Original.
   Messages and email recompress them.
4. Confirm the pixel size matches the table before uploading.

**B. Simulator capture on GitHub Actions (if you lack a 13" iPad or a qualifying iPhone).**
The repository has no screenshot automation; the UI tests attach no images.
This path needs a new UI test plus a `workflow_dispatch` option in
`.github/workflows/ios.yml`. That's a protected path, so it needs your approval.
It would create `iPhone 14 Plus` (1284×2778) and `iPad Pro 13-inch (M4)`
(2064×2752) simulators, capture the shot list below, flatten alpha, and
upload the PNGs as a workflow artifact.

### Shot list (native app screens, in upload order)

| # | Screen | How to get there | Point it makes |
| --- | --- | --- | --- |
| 1 | Fixture list, scores hidden | Launch the app (scores start hidden every launch) | Spoiler-safe by default |
| 2 | Fixture detail, Spoiler control | Tap a finished match; leave "Reveal score" untapped | You choose when to see scores |
| 3 | Where to watch | Detail → Where to watch, pick a broadcast region. Use a fixture with a verified listing (often a weekend league match); "Not verified yet" is truthful but sells nothing | TV/streaming info when a provider reports it |
| 4 | Live filter | Status picker → Live while matches are in progress | Live, upcoming and finished at a glance |
| 5 | Advanced filters sheet | Filter button → Competition / Time window | Narrow to what you follow |
| 6 | Date navigation and timezone | Previous/Today/Next, timezone menu | Local kickoff times |

Before upload: check every image for a revealed score (release checklist
requires a spoiler-leakage review). Keep the status bar clean: full battery,
no notifications, Focus on. Keep default text size and one appearance
(dark mode matches the brand).

---

## 2. Terms of Service: inputs only you or your lawyer can supply

Source: `templates/terms.html`. The fastlane `release_upload` and
`release_submit` lanes refuse to build while the literal
`[TO BE COMPLETED BY LEGAL OWNER]` remains (`clients/ios/fastlane/Fastfile:131`).

| # | Placeholder | Line(s) | What's needed | Notes |
| --- | --- | --- | --- | --- |
| 1 | Operating entity (legal name) | 12–18 (banner), 83–88 ("the operator") | Exact registered name | Should match the **Seller** name on your Apple Developer account, which App Store users see. Names in your files that might apply, *unconfirmed*: "Trequa" (in-flight support address `support@trequa.io`), "Hawkeye Tech Solutions LLC", or you as an individual. |
| 2 | Registered address | 141–145 | Address for legal notices | If you trade as an individual, ask your adviser about a registered-agent or mailing address instead of a home address. |
| 3 | Effective date | 20 | Date the final text takes effect | Usually the publish date of the reviewed version. |
| 4 | Governing law | 141–145 | Jurisdiction (e.g. a US state) | |
| 5 | Venue / dispute resolution | 141–145 | Courts of [county, state], or arbitration | Choosing arbitration brings more decisions (class-action waiver, opt-out, small-claims carve-out) and needs counsel. |
| 6 | Liability cap | 124–131 | Amount or formula | The app is free, so "fees paid" formulas resolve to $0. Many free services use a fixed sum; the number is a legal call. |
| 7 | Jurisdiction carve-outs | 124–131 | Statutory rights the cap can't limit | E.g. consumer-law rights in some regions, liability that can't be excluded by law. Counsel decides scope. |
| 8 | Contact for legal notices | 141–145 | Email (and address) | `support@trequa.io` is the native Settings support link (PR #27). Confirm whether it's also the legal-notice address. |

### Accuracy issue to fix in the same edit

The **Accounts** section (lines 98–106) says *"No persistent favorites or
saved defaults are kept."* The broadcast-region preference **is** persisted:

- Web: `localStorage['soccer-radar:broadcast-region']` (`static/js/fixtures.js:114`)
- iOS: `@AppStorage("soccer-radar:broadcast-region")` (`clients/ios/SoccerScanner/Features/FixtureDetail/FixtureDetailView.swift:4`)

Pins and score reveal are session-only (`sessionStorage`), so the rest of the
sentence holds. Have the reviewer change it to say that one on-device display
preference (broadcast region) is stored on the device and never sent to the
server.

### Drafting slots for counsel (not legal advice; fill and review before use)

> **Effective date:** [DATE]
>
> These Terms are an agreement between you and [LEGAL NAME] ("we", "us"),
> [ENTITY TYPE AND JURISDICTION OF FORMATION, if any], of [ADDRESS].
>
> **Limitation of liability.** … To the maximum extent permitted by law, our
> total liability for all claims relating to the service will not exceed
> [AMOUNT / FORMULA]. [CARVE-OUTS, e.g. nothing in these Terms limits liability
> that cannot be limited under applicable law.]
>
> **Governing law and disputes.** These Terms are governed by the laws of
> [JURISDICTION], without regard to its conflict-of-law rules. [VENUE OR
> ARBITRATION CLAUSE.]
>
> **Contact.** [LEGAL NAME], [ADDRESS], [EMAIL].

After the values are approved: remove the "LEGAL REVIEW REQUIRED" banner
(lines 12–18), update "Last updated", and decide whether to lift
`noindex` (line 7).

---

## 3. Physical-device TestFlight review script

Facts below come from the native source (file references inline). Record each
step as Pass/Fail and attach a screenshot for any Fail.

**Record per session:** device model · iOS version · TestFlight build number · tester · date

### A. Install and first launch
- [ ] Install from TestFlight; the app opens to the fixture list for today in device-local time.
- [ ] Previous / Today / Next and the date picker change the day (`FixtureListView.swift:252–298`).
- [ ] Timezone menu offers "Device local time" plus the fixed zones and re-labels kickoff times (`:300–327`).

### B. Spoiler behaviour (release-critical)
- [ ] On launch, every finished or live row shows **"Score hidden"** with the eye-slash icon. No digits appear anywhere (`FixtureListView.swift:687–705`).
- [ ] The list toolbar button reads "Reveal scores"; tapping shows scores, and it now reads "Hide scores" (`:104–112`).
- [ ] In detail, the "Spoiler control" section offers "Reveal score" / "Hide score" (`FixtureDetailView.swift:55–67`).
- [ ] Reveal, then **force-quit and relaunch**: scores are hidden again. Reveal is per-launch by design (`FixtureListViewModel.swift:283–287`).
- [ ] With scores hidden, share or copy a fixture link: the shared text contains no score.
- [ ] With scores hidden, open the app switcher: the snapshot shows no score.
- [ ] Rows with no score show "Score unavailable", never "0 – 0".

### C. VoiceOver
- [ ] Swipe through a hidden-score row: VoiceOver says "Score hidden" and **never reads digits** until you reveal.
- [ ] After reveal, VoiceOver reads the score.
- [ ] Every toolbar control has a spoken name: search, score toggle, settings, previous/today/next, date picker, timezone, status filter, advanced filters.
- [ ] The advanced filter sheet can be opened, changed, applied and dismissed with VoiceOver alone.
- [ ] Where-to-watch links read as links with the service name.

### D. Dynamic Type
- [ ] Settings → Accessibility → Larger Text at the largest accessibility size: the list switches to vertical layout and a menu-style status picker (`FixtureListView.swift:130–194`). No truncated team names hide which match a row is.
- [ ] Also check the smallest size; tap targets stay at least 44 pt (`Theme.swift:19–20`).

### E. Layout, safe areas, orientation
- [ ] iPhone: portrait and both landscapes. Nothing sits under the notch or Dynamic Island, and nothing is clipped by the home indicator.
- [ ] iPad: all four orientations, including upside-down (`project.yml:39–47`). The list uses `NavigationStack` (no split view), so check that rows aren't stretched awkwardly at 13" landscape.
- [ ] iPad Split View / Slide Over: the app stays usable at narrow widths.

### F. Universal Links
Paste each URL into Notes and tap it:
- [ ] `https://soccer-radar.com/fixtures/<fx_id>` opens that fixture **in the app** (`Support/DeepLink.swift:24–63`).
- [ ] The same path on `https://soccerscanner.pro/...` also opens in the app.
- [ ] A malformed fixture ID opens a usable fixture list, or falls back to Safari. It never shows a blank screen.
- [ ] A link to a fixture that no longer exists shows "Fixture unavailable — This match is no longer available…".
- Prerequisite: both `/.well-known/apple-app-site-association` endpoints return the real `TEAM_ID.com.leifheaney.soccerradar` (release checklist).

### G. Offline and provider errors
- [ ] Airplane mode, then pull to refresh: "Fixtures unavailable — You appear to be offline." with Retry (`APIClient.swift:21–38`, `FixtureListView.swift:462–479`).
- [ ] Turn the network back on and tap Retry: fixtures load.
- [ ] If a notice appears, the wording matches: "Showing recently cached fixtures." (stale) or "Some fixtures may be missing." (partial). An outage must never show as "No fixtures".

### H. Detail, Where to watch, Settings
- [ ] Detail shows Kick-off, Timezone, Competition, Country, Venue (`FixtureDetailView.swift:70–87`).
- [ ] Change the broadcast region, quit, relaunch: the region persists (expected; `@AppStorage`).
- [ ] Settings shows Version and Build matching the TestFlight build. The Website, Privacy, Terms and Data sources links open (`SettingsView.swift:15–52`).
- [ ] Settings → Support shows `support@trequa.io`, and tapping it opens Mail.

---

## 4. Product reel

`soccer-radar-reel.mp4`: 1080×1920, 30 fps, H.264 High / AAC (silent track),
29.6 s, about 3.4 MB. Captured from live https://soccer-radar.com on
2026-10-01 at a 405×720 phone viewport, rendered at 2.67× for full resolution.

Storyboard: title card → today's fixtures → scroll with hidden scores →
Live/Upcoming tabs → search "Real Madrid" → Match context → filter sheet →
end card (`soccer-radar.com`).

- Copy stays within `marketing/README.md` "safe claims". It makes no
  completeness, streaming-guarantee or real-time claims; "Where to watch" shows
  "Not verified yet" because that's what the provider reported.
- **Capture-only CSS override:** on phone widths the live site draws venue and
  competition text on top of each other in fixture cards (both are placed in
  grid-area `meta`, `static/css/fixtures.css:1622` with
  `fixture-renderer.js:373`). The reel hides the venue line in list cards to
  avoid showing that bug. The site itself is unchanged.
- The silent audio track exists for platform compatibility. Add licensed
  music in Instagram or TikTok.
- The reel shows the **website**, not the native app. Don't use it as an
  App Store app preview video; Apple requires those to show the app itself.
