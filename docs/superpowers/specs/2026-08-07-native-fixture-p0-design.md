# Native Fixture P0 Design

## Scope

This slice completes the first serious TestFlight-facing native fixture
experience using the existing SwiftUI app, typed API client, spoiler-safe
models, and dependency-injection seam. It covers:

- repair of the native decoder to match the current keyed `providers` API
  contract;
- previous day, today, next day, and native direct-date selection;
- interactive timezone selection that controls both API bucketing and display;
- local All, Live, Upcoming, and Finished filtering;
- local search across team, competition, and area names;
- cancellation/generation protection for date, timezone, refresh, and deep-link
  races;
- route-driven fixture Universal Links for cold and warm delivery;
- fixture-detail lookup with an honest missing-fixture state; and
- a native Settings/About surface with privacy, terms, data-source, support,
  website, version, build, and non-production environment information.

This is an implementation slice, not a claim that the iOS app is buildable or
ready for App Store submission. Xcode compilation and UI tests remain verified
only by the macOS GitHub Actions workflow. Apple Team ID, bundle registration,
legal ownership, and App Store Connect state remain human-controlled.

## Existing constraints and decisions

The backend already provides `GET /api/v2/fixtures` and
`GET /api/v2/fixtures/<canonicalFixtureId>`. The native client will use those
typed endpoints rather than add a new server route. The public fixture ID is
used exactly as returned by the API; the client will not derive or rewrite it.

The current native `FixtureDay` decoder expects `providers` to be an array,
while the server emits a keyed object containing provider outcome records. The
decoder will accept the authoritative keyed shape and normalize it into a
stable array for the existing partial-state logic. Tests that use the stale
array shape will be replaced with captured keyed payloads; no server contract
change is needed.

Scores remain hidden on launch and are never persisted. Filtering and search
operate on decoded fixture metadata only. A fixture status retains the
canonical taxonomy in `MatchStatus`; filters group statuses for navigation but
do not rewrite the fixture's status or score semantics.

## Architecture

`FixtureListViewModel` remains the single owner of the selected day, timezone,
loaded provider state, spoiler preference, and local query state. It will add:

- a `FixtureFilter` value containing status and search text;
- a computed filtered view of the loaded day;
- an explicit request generation token, checked after every awaited response;
- cancellation of the prior load task when a new selection supersedes it; and
- a typed fixture lookup method for route resolution.

The view model keeps the last usable data visible during refreshes where
possible, so changing a date does not create a disruptive full-screen flash.
An older response may finish, but it cannot mutate state after a newer request
has taken ownership of the generation token.

`AppRoute` models supported fixture routes and the fallback states for unknown
or unavailable destinations. `AppRouter` owns the pending route and consumes
both `.onOpenURL` and `NSUserActivityTypeBrowsingWeb`. The app root injects the
router into `FixtureListView`; the list resolves a fixture route through the
typed fixture endpoint, applies the route timezone, and pushes the detail view.
If the lookup returns not-found or cannot be decoded, the list remains usable
and presents a non-spoiler unavailable-destination message.

The Settings screen is reached from the list toolbar and uses system `Link`
controls for the existing website, privacy, terms, data sources, and support
URLs. It does not invent legal or Apple identity values. The environment label
is shown only outside production.

## UI behavior

The fixture screen uses a compact top control group:

1. previous-day button, selected-day button/date picker, today button, and
   next-day button;
2. timezone menu with device-local time plus a short list of common IANA zones;
3. segmented All/Live/Upcoming/Finished control; and
4. searchable list with an explicit no-results-after-filtering state.

The date picker is native SwiftUI and operates on a calendar day in the
selected timezone. Date changes preserve the selected timezone. Timezone
changes preserve the selected calendar day and reload it under the new zone.
Rows use flexible layout rather than a fixed status column, keep long team and
competition names readable under Dynamic Type, and retain meaningful
accessibility labels for status, kickoff, teams, and hidden scores.

## Deep-link data flow

1. The scene receives a URL through `.onOpenURL` or a browsing-web activity.
2. `DeepLink.parse` validates scheme, host, route shape, fixture ID, and an
   optional IANA timezone.
3. `AppRouter` stores the validated route; malformed/unknown routes become a
   safe no-op with no arbitrary navigation.
4. The fixture list consumes the route once, applies its timezone, and calls
   the typed fixture lookup.
5. A successful lookup computes the fixture's selected-zone day from its UTC
   kickoff, updates the list day without allowing a stale day response to win,
   and pushes detail.
6. A missing fixture shows an honest unavailable state and leaves the list
   navigable.

## Error and reliability behavior

The existing typed `APIError` taxonomy is preserved. A not-found fixture route
is distinct from an unavailable provider response and from an empty day. Raw
provider exception text remains out of client-facing messages.

Every load captures its requested day and timezone, increments a generation,
and verifies both before applying a response. Cancellation is treated as a
non-presenting event. Pull-to-refresh, retry, date changes, timezone changes,
and route resolution all use the same guard.

## Verification

Unit tests will cover date shifts, timezone/day preservation, local status and
search filtering, no-results distinction, stale-response suppression, typed
fixture lookup, route consumption, malformed links, and missing-fixture
fallback. UI tests will cover date controls, timezone control, status/search
controls, details, score privacy, retry/error behavior, and largest Dynamic
Type. The Windows run will cover syntax/documentation/static checks and any
available non-Xcode tests; only a green `iOS` macOS workflow can prove the
Swift project compiles and its UI tests pass.

## Deferred slices

Physical-device VoiceOver validation, provider-health deployment verification,
secondary-provider production enablement, and App Store portal actions remain
separate follow-up work. The related mobile-web bottom-sheet and installed-PWA
safe-area slice is implemented in the current working tree and covered by the
browser matrix; it is not a claim of physical-device validation or production
deployment.
