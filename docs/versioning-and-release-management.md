# Versioning and release management

## Version sources

- The application semantic version is owned by `soccer_scanner/build_info.py`.
- The full Git SHA is injected through `GIT_COMMIT_SHA` and exposed by
  `/health/version`; a short or guessed SHA is not release evidence.
- Web asset query tokens are derived from build identity. Do not hand-edit them.
- API contracts are versioned under `/api/v2`; additive fields are preferred,
  while removals or incompatible changes require a new API version or a
  documented deprecation window.
- The service-worker cache namespace changes with its build token so old shell
  and fixture snapshots can be evicted safely.
- Database changes use Alembic expand-and-contract migrations only.

## Release rules

1. Work lands on a conventional branch and is reviewed before integration.
2. The full local release matrix and the remote CI gates must pass against the
   candidate SHA.
3. A release note records Added, Changed, Deprecated, Removed, Fixed, and
   Security changes that actually shipped.
4. Production verification requires Railway terminal success, exact SHA parity
   from `/health/version`, readiness, and the production smoke suite.
5. Rollback means redeploying a previously verified SHA. Never rewrite history
   or mutate a production database manually.

## Deprecation

Document a replacement, compatibility window, affected clients, and removal
date before removing an API field or route. Disabled capabilities remain
explicitly disabled and documented; they are not represented by fabricated
successful data.
