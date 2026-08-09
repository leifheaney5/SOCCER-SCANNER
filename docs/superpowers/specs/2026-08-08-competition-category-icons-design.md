# Competition Category Icons Design

## Goal

Make competition group headers visually identify the actual competition: use official provider emblems when available, use the supplied handshake-and-ball mark for friendly categories without an official emblem, and retain the existing initials fallback for unknown competitions.

## Scope

- Web fixture competition-group headers only.
- Do not add icons to individual fixture rows.
- Do not fabricate or replace an official provider emblem.
- Friendly detection is limited to competition names containing the standalone word `friendly` after lowercasing.
- No provider, API, or iOS model changes.

## Design

`createCompetitionIdentity()` will resolve the image source in this order:

1. A non-empty `competition.emblem` supplied by the provider.
2. The local friendly category asset when the competition name is a friendly category.
3. The existing initials fallback for all other competitions without an emblem.

The supplied artwork will be stored as a compact transparent PNG under `static/icons/` and rendered through the existing `createCrest()` component so sizing, lazy loading, alt text, and fallback behavior remain consistent. A browser regression test will add a friendly group with no provider emblem and assert that the group header uses the local asset while an existing league group continues to use its provider emblem.
