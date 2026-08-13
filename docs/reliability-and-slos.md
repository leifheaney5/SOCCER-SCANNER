# Reliability and service-level objectives

These are product targets and measurement rules, not claims about an unmeasured
period. A release report must include the measurement window, sample size,
environment, and exact deployed SHA.

## Availability targets

| Surface | Target | Measurement |
| --- | ---: | --- |
| Process liveness | 99.9% monthly | Successful `/health/live` probes |
| Fixture API | 99.5% monthly | Non-5xx `/api/v2/fixtures` responses, excluding invalid requests |
| Search API | 99.5% monthly when enabled | Non-5xx `/api/v2/search` responses, excluding invalid requests |
| Readiness | 99.9% monthly | `/health/ready` with no blocking dependency |

Provider outages are reported as unavailable or partial data; they must not be
counted as confirmed empty schedules.

## Latency targets

Targets are measured server-side from request start to response completion:

- Fixture API: p50 ≤ 500 ms, p95 ≤ 2 s, p99 ≤ 4 s.
- Search API: p50 ≤ 1 s, p95 ≤ 4 s, p99 ≤ 6 s.
- Seven-day calendar: p95 ≤ 8 s for the complete client window, with each
  successful day rendered independently.

The fixture orchestration deadline is a hard upper bound for provider work. A
slow provider may produce a partial response; it may not multiply the request
budget by starting a fresh deadline for each provider.

## Data and cache signals

Track, without scores or raw payloads:

- fresh, stale, miss, and expired cache outcomes;
- provider success, partial, unavailable, rate-limited, and timeout counts;
- fixture API and search request latency distributions;
- search result state and calendar per-day completion state;
- streaming observations, matched/unmatched/ambiguous counts, verified links,
  known-region percentage, and stale records.

Metrics are bounded, allow-listed, and redacted by the observability layer.
Dashboards and alerts must never include provider credentials, scores, full
private URLs, or personal search text.

## Alerting

The synthetic fixture monitor is the availability alert. A failed production
fixture probe is actionable even when `/health/ready` remains healthy, because
provider health is distinct from process and dependency health. Investigate
repeated partial responses, truncation flags, cache degradation, and provider
rate limits before treating them as empty coverage.
