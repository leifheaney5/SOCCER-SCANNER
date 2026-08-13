# Notification decision

## Status

`not_applicable` for the current guest-only release.

## Decision

Do not implement push notifications, APNs registration, background delivery, or
notification preferences in this release. Soccer Scanner has no accounts,
cross-device identity, consent workflow, or notification delivery service.
Adding a notification toggle without those foundations would imply a capability
the product cannot reliably honor.

## Reconsideration trigger

Reopen this decision only after a product owner explicitly approves the user
value and privacy/consent model, and the team has defined account/device
identity, opt-in/out semantics, delivery provider, revocation, retention,
failure handling, and platform release requirements. Until then the
`notifications` and `apns` feature flags stay disabled.
