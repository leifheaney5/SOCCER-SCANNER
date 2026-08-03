# Soccer Scanner Shared-Suite Workspace Redesign

## Decision

Replace the editorial fixtures dashboard with a direct sibling of Select XI’s product workspace. Soccer Scanner keeps its fixtures data model and field-green accent, but adopts the same compact, dense, practical layout language as the suite.

## First-screen layout

1. A compact suite header: Soccer Scanner wordmark at left; one active Fixtures workspace control; no marketing hero.
2. A fixed workspace toolbar directly below: date stepper, date picker, competition filter, status filter, and search in one horizontal control group.
3. A three-column desktop canvas:
   - narrow left rail for date and competition shortcuts;
   - central fixture board with competition panels and dense match rows;
   - right context rail for the selected match.
4. The right rail begins with an explicit empty state. Selecting a match fills it with teams, kickoff/status, venue, team form, and table-context entry points.
5. Mobile uses the same ordered surfaces in a single column; selected-match context opens as a bottom sheet.

## Visual rules

- Use Inter or the existing Select XI-compatible sans-serif treatment only; no display serif.
- Keep canvas, panel, border, spacing, and compact-button rhythm visually aligned with Select XI.
- Use field green only for active selections and positive/available states. Live and exception states receive a small amber/red marker, not a dominant colour block.
- Remove oversized title copy, excess vertical whitespace, rounded marketing-card presentation, and decorative motion.
- Match rows are information-dense: time/status, home team, away team, score, and a single selected state.

## Interaction rules

- Clicking a fixture selects it and updates the context rail without navigating away.
- Clicking a team inside the rail opens existing team intelligence in a modal/bottom sheet.
- Competition panels collapse only when requested; there is no separate Teams or Tables primary journey.
- All selection, filter, and panel state is keyboard-accessible and visible.
- Motion is limited to short selection/context transitions and disabled for reduced-motion users.

## Acceptance criteria

1. The initial desktop viewport reads as a suite workspace, not an editorial landing page.
2. Its header, toolbar, panel rhythm, typography, and density clearly align with Select XI.
3. Fixtures remain the sole primary task; team/table context is secondary and contextual.
4. No display serif, giant hero heading, or wide empty vertical space remains.
5. Existing Flask endpoints and compatibility routes continue to work.
