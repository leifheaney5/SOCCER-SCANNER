# Accounts and preferences decision

- Status: accepted
- Date: 2026-08-04
- Decision owner: Soccer Scanner product and engineering

## Context

Soccer Scanner currently has no identity provider, verified email delivery, account-support process, native token exchange, or tested data-export and deletion pipeline. The web client nevertheless offered favorites and default score visibility through indefinite browser `localStorage`. That hybrid implied an account-like durable feature without cross-device recovery, server-side lifecycle controls, or a truthful native synchronization path.

The product brief permits either a complete account system or an explicit guest-only product. It forbids persistent favorites and saved defaults without real accounts.

## Decision

Soccer Scanner will ship in deliberate guest mode until the prerequisites for a production account system exist.

- There is no registration, login, account placeholder, or anonymous-account record.
- Favorite controls, favorite filters, favorite navigation, and favorite import/export are not offered.
- The score-reveal choice is session-scoped and scores begin hidden in each new browsing session.
- Timezone, date, filters, and selected fixture remain URL-backed so a shared link is deterministic.
- Existing legacy `localStorage` keys are no longer read or written. They are not silently imported into a future account.
- Cross-device synchronization, account notifications, and server-side saved defaults are unavailable.

This decision applies consistently to web and the initial iOS foundation. The native app must not create fake anonymous accounts to preserve preferences.

## Why accounts are deferred

Accounts would add real product value for cross-device favorites, saved defaults, and notification preferences. They also require all of the following before release:

- a maintained identity provider and verified recovery path;
- secure web sessions plus a documented native token and Keychain strategy;
- rate limiting, session rotation and revocation, CSRF protection, and isolation tests;
- account export, deletion, audit, support, and backup-retention behavior;
- email or social-login operations, including Sign in with Apple review when applicable.

Implementing only a subset would create avoidable security, privacy, and support risk. Guest mode is the smaller truthful product until those dependencies are selected and funded.

## Reconsideration triggers

Reopen this decision when at least one roadmap increment requires cross-device state or remote notifications and the team has selected an identity provider, email/support ownership, native authentication, and a complete data-lifecycle design. A replacement decision must include migration, deletion, export, retention, incident response, and web/iOS acceptance tests.

## Consequences

- Personalization is limited to the current session and shareable URL state.
- A browser refresh in the same tab may retain score visibility; a new session starts spoiler-safe.
- The backend remains free of user-profile and favorite tables.
- Privacy copy can accurately state that no account is required and no guest favorite profile is maintained.
- Legacy browser data may remain in a visitor's storage until that visitor clears site data, but application code does not access it.
