# Provider and identity mapping

Canonical team mappings live in `soccer_scanner/data/team-provider-map.json`. Each entry owns a stable lowercase kebab-case `canonicalId`, display name, aliases, and provider-qualified IDs. Provider IDs may be reused only within their provider namespace.

Resolution order is:

1. Exact `(provider, providerId)` match.
2. Accent-insensitive normalized alias only when it resolves uniquely.
3. Unresolved identity with observed provider provenance retained; no guessed canonical ID.

Fixture de-duplication requires the same canonical competition, home team, and away team; kickoff within ten minutes; and compatible season/stage values. The stable fixture ID hashes those inputs. Source freshness and a documented provider order choose fields deterministically, while provider IDs from all merged records are retained.

Mapping changes require fixtures for provider-ID resolution, unique alias resolution, ambiguity rejection, cross-provider merge, near-time non-merge, and canonical-ID stability. Do not silently rename an existing canonical ID: it is part of team URLs, favorites, fixture IDs, and exported calendar links.
