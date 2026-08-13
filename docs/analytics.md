# Privacy-safe analytics

Soccer Scanner currently does not require product analytics. The guest-mode
contract and spoiler boundary take precedence over instrumentation.

If measurement is introduced later, it must be consent-aware, documented before
collection, and limited to aggregate product reliability and interaction shape.
It must never record:

- score values, score-reveal state, or raw fixture payloads;
- provider keys, operations tokens, or authentication material;
- personal search text, full private URLs, complete device tokens, or precise
  location;
- unbounded request headers, IP addresses, or cross-session identifiers.

Allowed examples are a coarse event name such as `search_opened`, viewport
bucket (`320`, `375`, `768`, `desktop`), response state (`success` or `partial`),
and bounded duration bucket. Events must not be used to reconstruct a visitor's
fixture interests or score history.

Default retention is 30 days for operational aggregates and zero days for raw
interaction events unless a human privacy owner approves a different period.
There is no analytics SDK, consent banner, or analytics endpoint in the current
release; this document is a guardrail, not a claim that collection exists.
