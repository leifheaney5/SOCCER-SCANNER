# Soccer Scanner Fixtures Dashboard Design

## Goal

Turn Soccer Scanner into a production-quality fixture-scanning workspace that belongs to the same product family as Select XI while keeping the Flask, Jinja, vanilla JavaScript, provider, cache, API, and compatibility-route architecture intact.

The page has one primary job: help a supporter scan a matchday quickly without accidentally seeing results. Team and match intelligence remain available as contextual, on-demand detail.

## Chosen approach

Replace the compressed all-purpose fixture script with focused ES modules and rebuild the fixture template around a two-column desktop workspace. Do not restore the legacy feature-heavy renderer: it interpolated provider content into HTML, mixed unrelated responsibilities, and exposed scores by default. Do not extend the current minified source: it directly conflicts with the maintainability requirements.

The fixture API stays unchanged. The browser owns filter state, score preference, grouping, rendering, focus management, and request cancellation. Backend payload changes are unnecessary because the normalized payload already includes crests, scores, competition identity, venue, status, source, matchday/season metadata, provider health, cache state, and last-updated time.

## Visual direction

### Palette

- Canvas: `#000000`
- Secondary surface: `#0a0a0a`
- Card surface: `#141414`
- Raised surface: `#1a1a1a`
- Border: `#2a2a2a`
- Primary text: `#ffffff`
- Secondary text: `#a0a0b0`
- Muted text: `#6a6a7a`
- Interaction lime: `#7cff00`, with `#a8ff4d` for hover/focus
- Status colors: success `#22c55e`, warning `#f59e0b`, danger `#ef4444`

Lime marks active, selected, live, focused, and actionable states. It is not used as a body-text color or large background wash.

### Type and spacing

- Inter is the interface face.
- IBM Plex Mono is the data face for scores, kickoff times, dates, match counts, and status codes.
- Orbitron is limited to the two-part Soccer Scanner wordmark.
- The spacing system uses 4 px increments.
- Controls use 6 px radii; match cards and larger controls use 10 px; modal sheets use 16 px only on mobile.

### Signature: the matchday ledger

The fixture stream reads like a digital matchday ledger. Each row has a stable mono status/time rail, paired home/away identity rows, a fixed score cell, and a details action. This creates a recognizable soccer-specific scanning rhythm without copying Select XI's formation-builder layout. The date summary above the stream functions as the ledger heading, and competition headers act as restrained dividers rather than oversized cards.

### Layout

```text
+-----------------------------------------------------------------------+
| Wordmark | Fixtures | Select XI               [eye] Reveal scores     |
+-----------------------------------------------------------------------+
| Fixtures                                    Mon, Aug 3                |
| 42 matches   3 live   18 upcoming   21 finished   Updated 14:32      |
+-----------------------------------------------------------------------+
| <  Today  >  [date] | Search | Competition | All Live Up Finished    |
+-----------------------------------------------+-----------------------+
| Compact featured match                        | Match context         |
| Competition group                             | (sticky, 320 px)      |
| 18:30 | home row | score/hidden | details     |                       |
|       | away row |              |             |                       |
+-----------------------------------------------+-----------------------+
```

The centered shell is at most 1,400 px wide. The fixture stream dominates; an optional 320 px context panel appears only from 1,100 px upward. Below that width, match context is a modal bottom sheet. There is no permanent left rail. Mobile keeps date navigation visible, moves secondary filters into an expandable panel, and reflows fixture cards into status/score, team, and metadata/action rows without horizontal overflow.

## Component boundaries

- `fixture-state.js`: URL-backed date, competition, status, and query state; date arithmetic; status normalization; summary counts; featured-match selection; filter/group functions.
- `score-preference.js`: one configurable default, localStorage persistence under `soccer-scanner:reveal-scores`, accessible toggle state, and score-value validation.
- `crest.js`: safe image nodes with explicit dimensions, async/lazy behavior, initials fallback, and error replacement.
- `fixture-renderer.js`: skeleton, degraded/empty/error states, summary, feature card, competition groups, fixture cards, and spoiler-safe score nodes using DOM construction and `textContent` only.
- `match-context.js`: selected-fixture rendering, desktop sticky panel, responsive dialog/sheet behavior, Escape handling, focus restoration, and team-intelligence launch actions.
- `team-drawer.js`: cached team-analysis fetches, loading/retry/partial states, identity, season record, form, recent/upcoming matches, squad summary, focus trap, Escape, restoration, and score-preference rerendering.
- `fixtures.js`: application controller, request abort/stale-response protection, delegated event wiring, debounced search, filter/date coordination, URL synchronization, and orchestration only.

Each module exports its public functions so Node or browser tests can exercise real production behavior. Provider-derived text is never interpolated into HTML.

## Score privacy invariant

The default is controlled by one constant and is `false` for first-time visitors. Toggling updates all score-bearing surfaces and persists the preference.

When scores are hidden, the renderer must not create score values in visible text, visually hidden text, ARIA labels, titles, tooltips, data attributes, or any other DOM content. Live and finished matches render only a neutral `Score hidden` label with an eye-off icon. Upcoming matches render kickoff time. Team recent-match results use the same rule. Team order, emphasis, and accessible names do not encode the winner.

When scores are revealed, valid live/finished values from `score.fullTime.home` and `.away` appear as tabular numerals. Malformed or missing values render `Score unavailable`. Postponed, cancelled, and suspended states never imply a score.

## Data and interaction flow

1. The controller reads URL filters and the persisted score preference before the first fixture render.
2. It requests `/api/matches-today` with the selected local date and IANA timezone. A newer date request aborts the older request and stale responses are ignored.
3. The renderer updates competition choices, summary counts, the featured match, grouped fixture cards, and the state announcement.
4. Filter changes update the URL with `history.replaceState` and rerender the already-loaded payload. Search is debounced; date changes fetch again while preserving the surrounding shell.
5. Selecting a fixture updates the desktop context panel or opens the responsive context sheet. Selecting a team lazily requests `/api/team-analysis/<id>` and caches successful responses for the session.
6. Changing score visibility rerenders every score-bearing surface from in-memory data without refetching.

## State treatment

- Initial and date-change loading use fixture-shaped skeleton rows.
- An empty provider result says `No matches scheduled` and offers adjacent date navigation.
- A filter-empty result says `No fixtures match these filters` and offers `Clear filters`.
- A failed request says `Football data is temporarily unavailable` and offers `Retry`.
- Partial and stale payloads show distinct inline notices plus last-updated time without raw provider exceptions.
- Missing crests become initial-based neutral shields; missing venue/matchday/stage values are omitted or described as unavailable.
- Team-analysis failures keep the drawer open with retry. A response with missing sections is explicitly marked `Limited team data` while rendering everything available.

## Accessibility and motion

- Keep the skip link, logical headings, semantic controls, visible `:focus-visible`, 44 px mobile targets, and live status/result-count announcements.
- The score control is a labelled pressed button with eye/eye-off SVG and an accurate state description.
- Dialogs use native `dialog`, trap focus, close on Escape/backdrop, lock background scrolling, respect safe-area insets, and restore focus.
- Competition disclosure buttons expose `aria-expanded` and `aria-controls`.
- Form sequences include text (`W`, `D`, `L`) and never rely on color alone.
- Motion is 150–250 ms and limited to controls, selection, sheets, loading opacity, and a restrained live dot. `prefers-reduced-motion: reduce` removes nonessential animation and smooth scrolling.

## Performance and security

- No runtime framework, icon library, or animation dependency.
- Fixture crests below the featured match use `loading="lazy"`, `decoding="async"`, fixed width/height, and `object-fit: contain`.
- Render only changed dashboard sections and use one delegated listener per interactive region.
- Team analysis is lazy, cached, and not duplicated in flight.
- All icons are inline SVG generated from trusted local templates.
- Provider content is assigned with `textContent`; no provider-derived `innerHTML` or `insertAdjacentHTML` is allowed.
- Existing CSP and cache headers remain intact.

## Testing and verification

- Python route tests verify the semantic shell, compatibility routes, CSP-safe external assets, and unchanged API behavior.
- Playwright browser tests intercept fixture/team endpoints with complete representative payloads and cover hidden-by-default scores, persistence, DOM absence, revealed scores, upcoming states, crests/fallbacks, grouping, filters, URL state, date controls, loading, retry, partial/stale notices, match context, drawer rendering, keyboard close/focus restoration, reduced motion, and overflow at all requested widths.
- The full Python suite, Playwright suite, compile check, and `git diff --check` must pass.
- Manual screenshots and accessibility snapshots are inspected at 320, 375, 430, 768, 1,024, 1,280, and 1,440 px. Browser assertions check `scrollWidth <= clientWidth` at each width and verify score literals are absent while hidden.

## Acceptance criteria

1. The visual canvas, surfaces, type roles, density, borders, and lime accent align with Select XI without copying its builder layout.
2. The header, summary, unified toolbar, fixture stream, featured match, competition grouping, and responsive context surface are complete and functional.
3. Every team identity has a crest or intentional fallback, and every fixture uses separate home/away rows.
4. Scores are hidden by default, absent from all DOM content while hidden, consistently revealed on request, and persisted across reloads.
5. The match context and team-intelligence drawer render meaningful existing provider data and implement accessible modal behavior.
6. Loading, empty, filtered-empty, provider-error, partial, stale, missing-crest, missing-score, and team-analysis error states are intentional and actionable.
7. URL state survives refresh and sharing; outdated requests and duplicate analysis requests are controlled.
8. The page has no horizontal overflow and remains usable from 320 px through 1,440 px, including keyboard and reduced-motion modes.
9. Existing Flask/API/provider/cache/compatibility architecture is preserved, all tests pass, and primary source files remain readable and modular.
