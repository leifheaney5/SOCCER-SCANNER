# Soccer Scanner Fixtures Dashboard Design

## Goal

Transform Soccer Scanner from three separate utility pages into a sleek, minimal fixtures-first dashboard. The primary user job is to scan today’s and upcoming football fixtures quickly, then reveal team form and league context only when it improves a match decision.

## Product scope

### Primary journey

The root route is the only primary product surface. It presents a date-led fixture stream, lets users narrow it by competition, and gives every match a clear state: live, upcoming, or finished. A user can choose a date, filter the stream, open a match, and inspect just enough context without leaving the dashboard.

### Secondary context

- Selecting a team opens an in-page team intelligence drawer or sheet; it shows club identity, season record, recent results, and form.
- Each competition group exposes a compact standings preview only when standings data is available. A “Full standings” action expands the relevant view in place rather than navigating to a top-level tab.
- Existing `/teams` and `/league-tables` routes remain available as compatibility routes, but are removed from primary navigation and visually redirect users toward the fixtures dashboard.

### Out of scope

- Accounts, saved teams, notifications, betting information, social feeds, and a new backend data provider.
- Replacing the existing Flask API contract.
- Adding a JavaScript framework or a large animation library.

## Information architecture

```text
Soccer Scanner
└── Fixtures dashboard (/)
    ├── Command header: brand, date controls, competition filter, team search
    ├── Match spotlight: the nearest live or next priority match
    ├── Fixture stream: competition groups with match cards
    ├── League pulse: contextual standings snapshot per competition
    └── Team intelligence drawer: opened from a team name or search result

Compatibility routes
├── /matches-today → fixtures dashboard
├── /teams → team intelligence entry point with dashboard return action
└── /league-tables → standings entry point with dashboard return action
```

## Visual direction

The visual language takes the useful qualities of Select XI—compact analytical controls, strong hierarchy, dark workspace surfaces, deliberate information density, and no decorative clutter—without copying its formation-builder UI.

- Canvas: near-black navy/charcoal background with layered, slightly lighter panels.
- Accent: a single field-green interaction color. Reserve amber/red for status and validation only.
- Typography: retain Inter initially; use a tight display scale, tabular numerals for time and scores, and muted metadata.
- Layout: a centered desktop workspace with a narrow context rail; a single-column flow on mobile.
- Components: rounded but restrained cards, hairline borders, quiet shadows, compact filter pills, and real team crests where source data supplies them.
- Content tone: direct labels such as “Today”, “Next up”, “Live”, “Form”, and “Standings”; no marketing copy or emojis.

## Dashboard behaviour

### Header and filters

The fixed header contains the Soccer Scanner wordmark, desktop navigation limited to the fixtures workspace, and a compact date switcher. The date switcher offers Yesterday, Today, Tomorrow, and a calendar input. A competition filter and a searchable team command control refine the already-loaded fixture data; the URL stores the selected date and competition so the view can be shared and refreshed.

### Match spotlight

Above the stream, show one featured event: a live match first, otherwise the nearest upcoming match. It has the competition, kickoff/status, both teams, score when available, and a subtle action to open context. If the selected date has no fixtures, replace this with an intentional empty state and a nearby-date action rather than a blank panel.

### Fixture stream

Group matches by competition. Each group has its logo/name, match count, and a collapsible league-pulse trigger. Match cards expose time/status, home and away names/crests, score, and an accessible disclosure control. The expanded card may show venue, matchday, and links to the two team drawers, but does not create a second navigation layer.

### Team intelligence

Desktop uses a right-side drawer; mobile uses a bottom sheet. Opening it preserves the selected fixture position and moves focus to the sheet heading. The sheet requests the existing team-analysis endpoint only after opening, displays a loading skeleton, then renders season record, form sequence, recent matches, and clear provider-error recovery. Closing restores focus to the initiating club control.

### League pulse

The dashboard only fetches/embeds standings on user request. A compact preview shows the relevant teams’ positions plus a small top-of-table context. Full standings appear in the same contextual panel and retain the existing provider attribution. This prevents an embedded standings view from dominating the fixtures experience or loading needlessly.

## Interaction and motion

Motion clarifies state changes; it never exists solely for decoration.

- Dashboard sections fade and rise once on first render, staggered by a maximum of 40 ms between sections.
- Date and competition changes cross-fade the fixture stream while announcing loading state to screen readers.
- Match expansion uses an opacity/height transition; drawers and sheets use a transform plus opacity transition.
- Live status uses a low-contrast pulse that stops under `prefers-reduced-motion`.
- Hover and keyboard focus use border/accent changes and a maximum 2 px lift; touch devices get no hover-dependent affordance.
- `prefers-reduced-motion: reduce` disables transitions and animations except immediate state visibility changes.

## Technical architecture

Keep Flask and vanilla JavaScript. Consolidate duplicated page-specific layout into a dashboard stylesheet and small focused ES modules:

- a state/query module for date, competition, and selected-team state;
- a fixtures-rendering module that creates DOM nodes rather than interpolating HTML;
- a team-drawer module that requests and displays existing analysis data;
- a standings-context module that lazy-loads contextual standings;
- a motion/focus module that centralises reduced-motion and dialog focus behaviour.

Backend route compatibility remains intact. Extend the fixture payload only if the frontend cannot derive the required match status, competition grouping, and team identifiers from the existing response; any extension must be additive and covered by API tests.

## Accessibility and resilience

- Use semantic headings, buttons for disclosures, labelled controls, and a `main` landmark.
- Maintain the existing skip link and provide visible `:focus-visible` states on every interactive control.
- Implement the drawer/sheet as an accessible dialog with focus trap, Escape close, focus restoration, and scroll containment.
- Provide text equivalents for status, scores, and colour-coded form.
- Preserve usable loading, empty, partial-data, and provider-failure states.
- Keep existing provider attribution and avoid fetching team analysis or standings until requested.

## Acceptance criteria

1. `/` is a fixtures-first dashboard with no primary Teams or League Tables navigation tabs.
2. A user can choose a date, filter by competition, and understand live/upcoming/finished fixture states without leaving `/`.
3. A user can open and close accessible team intelligence context from a fixture, with keyboard focus restored on close.
4. Standings are contextual and lazy-loaded, not a default competing surface.
5. The dashboard works from 320 px to desktop widths, has no horizontal page overflow, and honours reduced-motion settings.
6. Existing `/teams`, `/league-tables`, and `/matches-today` paths continue to return successful responses.
7. Existing API and backend tests remain green; new tests cover dashboard filtering, DOM state, keyboard interaction, and reduced-motion handling.
