"""Truthful orchestration for the canonical fixture API."""

from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from soccer_scanner.domain.identity import merge_fixtures
from soccer_scanner.domain.models import (
    FixtureState,
    FixtureUnavailable,
    ProviderOutcome,
    ProviderStatus,
)
from soccer_scanner.providers.http import RequestBudget

logger = logging.getLogger(__name__)

# Provider outcome -> the vocabulary ProviderHealthRegistry accepts.
_HEALTH_BY_STATUS = {
    ProviderStatus.SUCCESS: 'ok',
    ProviderStatus.PARTIAL: 'degraded',
    ProviderStatus.DISABLED: 'disabled',
}


class _ProviderFailure(RuntimeError):
    def __init__(self, outcome):
        super().__init__(outcome.status.value)
        self.outcome = outcome


class FixtureIdentityInvariantError(RuntimeError):
    """Raised before returning or caching a response with unsafe public IDs."""


def assert_unique_fixture_ids(matches):
    seen = set()
    for match in matches:
        fixture_id = match.get('canonicalFixtureId')
        if not fixture_id:
            raise FixtureIdentityInvariantError('Fixture is missing a public fixture ID.')
        if fixture_id in seen:
            raise FixtureIdentityInvariantError(
                f'Duplicate public fixture ID detected: {fixture_id}'
            )
        seen.add(fixture_id)


def _outcome_dict(outcome):
    payload = asdict(outcome)
    payload['status'] = outcome.status.value
    payload['fixtures'] = list(outcome.fixtures)
    payload['requestedResources'] = list(outcome.requestedResources)
    payload['completedResources'] = list(outcome.completedResources)
    payload['failureCategories'] = list(outcome.failureCategories)
    return payload


def _dict_outcome(payload):
    return ProviderOutcome(
        provider=payload['provider'],
        status=ProviderStatus(payload['status']),
        fixtures=tuple(payload.get('fixtures') or []),
        requestedResources=tuple(payload.get('requestedResources') or []),
        completedResources=tuple(payload.get('completedResources') or []),
        requestCount=int(payload.get('requestCount') or 0),
        timeoutCount=int(payload.get('timeoutCount') or 0),
        rateLimitCount=int(payload.get('rateLimitCount') or 0),
        sourceUpdatedAt=payload.get('sourceUpdatedAt'),
        durationMs=int(payload.get('durationMs') or 0),
        failureCategories=tuple(payload.get('failureCategories') or []),
    )


class CanonicalFixtureService:
    def __init__(
        self,
        espn_provider,
        football_data_provider,
        cache,
        *,
        cache_ttl_seconds=60,
        stale_ttl_seconds=900,
        provider_budget_seconds=4,
        identity_registry=None,
        provider_health=None,
        streaming_registry=None,
        now=None,
    ):
        self.providers = (espn_provider, football_data_provider)
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.stale_ttl_seconds = stale_ttl_seconds
        self.provider_budget_seconds = provider_budget_seconds
        self.identity_registry = identity_registry
        self.provider_health = provider_health
        self.streaming_registry = streaming_registry
        self.now = now or (lambda: datetime.now(timezone.utc))

    def fixtures_for_date(self, requested_date, timezone_name='UTC'):
        local_zone = ZoneInfo(timezone_name)
        provider_start, provider_end = self._provider_range(requested_date, local_zone)
        current = []
        stale = []
        failed = []
        provider_cache = {}

        for provider in self.providers:
            provider_name = self._provider_name(provider)
            cache_key = (
                f'provider-fixtures:{provider_name}:'
                f'{provider_start.isoformat()}:{provider_end.isoformat()}'
            )

            def load(selected=provider):
                provider_outcome = selected.fetch_range(
                    provider_start,
                    provider_end,
                    budget=RequestBudget(self.provider_budget_seconds),
                )
                if provider_outcome.status in {
                    ProviderStatus.UNAVAILABLE,
                    ProviderStatus.RATE_LIMITED,
                }:
                    raise _ProviderFailure(provider_outcome)
                return _outcome_dict(provider_outcome)

            try:
                lookup = self.cache.get_or_load(
                    cache_key,
                    load,
                    ttl_seconds=self.cache_ttl_seconds,
                    stale_ttl_seconds=self.stale_ttl_seconds,
                )
                provider_cache[provider_name] = lookup.status
                outcome = _dict_outcome(lookup.value)
                self._record_provider_health(outcome)
                if outcome.status is not ProviderStatus.DISABLED:
                    current.append(outcome)
                else:
                    current.append(outcome)
            except _ProviderFailure as error:
                failed.append(error.outcome)
                self._record_provider_health(error.outcome)
                provider_cache[provider_name] = 'miss'
                stale_lookup = self.cache.get(cache_key, allow_stale=True)
                if stale_lookup.status == 'stale':
                    stale.append(_dict_outcome(stale_lookup.value))
            except Exception as error:
                # Anything else (a cache-layer fault such as an oversized or
                # unserializable value, a Redis timeout, a parse error in
                # _outcome_dict, ...) must not take the whole request down:
                # the other provider still deserves a chance. But this
                # provider's outcome must be recorded as failed — both in
                # `failed` (so `is_partial` and the response's
                # `providers`/`coverage` blocks reflect reality instead of
                # being composed as if only healthy providers existed) and
                # in the health registry — and a within-TTL stale snapshot
                # should still be served if one exists. `detail` stays a
                # fixed, controlled string — never the exception message —
                # because it is echoed by the public unauthenticated
                # /health/providers endpoint; the exception itself is logged
                # server-side only.
                logger.exception(
                    'Unhandled error while fetching fixtures from provider %r',
                    provider_name,
                )
                provider_cache[provider_name] = 'miss'
                failure_outcome = ProviderOutcome(
                    provider=provider_name,
                    status=ProviderStatus.UNAVAILABLE,
                    fixtures=(),
                    requestedResources=(),
                    completedResources=(),
                    requestCount=0,
                    timeoutCount=0,
                    rateLimitCount=0,
                    sourceUpdatedAt=None,
                    durationMs=0,
                    failureCategories=('internal_error',),
                )
                failed.append(failure_outcome)
                self._record_provider_health(failure_outcome)
                try:
                    stale_lookup = self.cache.get(cache_key, allow_stale=True)
                except Exception:
                    # The cache itself may be what just failed; a second
                    # exception here must not escape and kill the request.
                    logger.exception(
                        'Stale-cache fallback also failed for provider %r',
                        provider_name,
                    )
                    stale_lookup = None
                if stale_lookup is not None and stale_lookup.status == 'stale':
                    stale.append(_dict_outcome(stale_lookup.value))
                continue

        usable_current = [
            outcome for outcome in current
            if outcome.status in {ProviderStatus.SUCCESS, ProviderStatus.PARTIAL}
        ]
        if usable_current:
            selected = usable_current
            is_partial = bool(failed) or any(
                outcome.status is ProviderStatus.PARTIAL for outcome in usable_current
            )
            matches = self._compose(selected, requested_date, local_zone)
            if is_partial:
                state = FixtureState.PARTIAL
            elif matches:
                state = FixtureState.SUCCESS
            else:
                state = FixtureState.EMPTY_CONFIRMED
            cache_status = self._cache_status(provider_cache.values())
        elif stale:
            selected = stale
            matches = self._compose(selected, requested_date, local_zone)
            state = FixtureState.STALE
            cache_status = 'stale'
        else:
            failures = [*failed, *current]
            rate_limited = any(
                outcome.status is ProviderStatus.RATE_LIMITED for outcome in failures
            )
            raise FixtureUnavailable(
                FixtureState.RATE_LIMITED if rate_limited else FixtureState.PROVIDER_UNAVAILABLE,
                (
                    'Fixture providers are rate limited.'
                    if rate_limited
                    else 'Fixture providers are temporarily unavailable.'
                ),
                retry_after_seconds=30,
            )

        provider_outcomes = {outcome.provider: outcome for outcome in [*current, *failed]}
        for outcome in stale:
            provider_outcomes.setdefault(outcome.provider, outcome)
        last_updated = max(
            (outcome.sourceUpdatedAt for outcome in selected if outcome.sourceUpdatedAt),
            default=self.now().isoformat(),
        )
        response = {
            'state': state.value,
            'date': requested_date.isoformat(),
            'timezone': timezone_name,
            'matches': matches,
            'matchStatistics': self._statistics(matches, local_zone),
            'lastUpdated': last_updated,
            'providers': {
                name: self._public_outcome(outcome, provider_cache.get(name, 'miss'))
                for name, outcome in sorted(provider_outcomes.items())
            },
            'coverage': {
                name: {
                    'requested': len(outcome.requestedResources),
                    'completed': len(outcome.completedResources),
                }
                for name, outcome in sorted(provider_outcomes.items())
            },
            'cache': {
                'status': cache_status,
                'providers': dict(sorted(provider_cache.items())),
            },
            'sourceStats': {
                **{outcome.provider: len(outcome.fixtures) for outcome in selected},
                'totalUnique': len(matches),
            },
            # Compatibility flags for the v1 release alias.
            'cached': cache_status in {'fresh', 'stale'},
            'stale': state is FixtureState.STALE,
            'partial': state in {FixtureState.PARTIAL, FixtureState.STALE},
            'total_matches': len(matches),
            'featured_matches': matches[:6],
            'source_stats': {
                **{outcome.provider: len(outcome.fixtures) for outcome in selected},
                'total_unique': len(matches),
            },
        }
        for match in matches:
            fixture_id = match.get('canonicalFixtureId')
            if not fixture_id:
                continue
            try:
                self.cache.set(
                    f'fixture-lookup:{fixture_id}',
                    match,
                    ttl_seconds=24 * 60 * 60,
                    stale_ttl_seconds=6 * 24 * 60 * 60,
                )
            except (ValueError, RuntimeError):
                # Fixture responses remain available if optional deep-link storage degrades.
                continue
        return response

    def lookup_fixture(self, canonical_fixture_id, timezone_name='UTC'):
        resolved_fixture_id = canonical_fixture_id
        if self.identity_registry is not None:
            resolved_fixture_id = (
                self.identity_registry.resolve_public_alias(canonical_fixture_id)
                or canonical_fixture_id
            )
        lookup = self.cache.get(
            f'fixture-lookup:{resolved_fixture_id}',
            allow_stale=True,
        )
        if lookup.status in {'fresh', 'stale'}:
            return lookup.value
        if self.identity_registry is None:
            return None
        identity = self.identity_registry.get(resolved_fixture_id)
        if identity is None or not identity.get('kickoffUtc'):
            return None
        try:
            local_zone = ZoneInfo(timezone_name)
            kickoff = datetime.fromisoformat(
                identity['kickoffUtc'].replace('Z', '+00:00')
            )
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            local_date = kickoff.astimezone(local_zone).date()
        except (TypeError, ValueError):
            return None
        for offset in (0, -1, 1):
            try:
                response = self.fixtures_for_date(
                    local_date + timedelta(days=offset),
                    timezone_name,
                )
            except FixtureUnavailable:
                continue
            match = next(
                (
                    candidate
                    for candidate in response['matches']
                    if candidate.get('canonicalFixtureId') == resolved_fixture_id
                ),
                None,
            )
            if match is not None:
                return match
        return None

    def _record_provider_health(self, outcome):
        # Runs on every request, including a cache hit (see `get_or_load`
        # above), so a status of 'ok' here stamps `lastSuccessAt` even when no
        # upstream call happened this request. It therefore means "this
        # provider's data last served a request successfully", not "the
        # provider was last actually reached upstream". The two can diverge
        # by at most `cache_ttl_seconds` (60s in production via
        # FIXTURE_CACHE_TTL), which is an accepted, bounded skew.
        if self.provider_health is None:
            return
        categories = ','.join(outcome.failureCategories)
        self.provider_health.record(
            outcome.provider,
            _HEALTH_BY_STATUS.get(outcome.status, 'unavailable'),
            detail=categories or None,
        )

    @staticmethod
    def _provider_name(provider):
        explicit = getattr(provider, 'provider_name', None)
        if explicit:
            return explicit
        outcome = getattr(provider, 'outcome', None)
        if outcome is not None:
            return outcome.provider
        name = provider.__class__.__name__.casefold()
        return 'football-data' if 'football' in name else 'espn'

    @staticmethod
    def _provider_range(requested_date, local_zone):
        local_start = datetime.combine(requested_date, time.min, local_zone)
        local_end = local_start + timedelta(days=1) - timedelta(microseconds=1)
        return (
            local_start.astimezone(timezone.utc).date(),
            local_end.astimezone(timezone.utc).date(),
        )

    def _compose(self, outcomes, requested_date, local_zone):
        merged = merge_fixtures(
            (fixture for outcome in outcomes for fixture in outcome.fixtures),
            identity_registry=self.identity_registry,
        )
        matches = []
        for match in merged:
            try:
                kickoff = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
                if kickoff.tzinfo is None:
                    kickoff = kickoff.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            local_date = kickoff.astimezone(local_zone).date()
            if local_date != requested_date:
                continue
            enriched = {**match, 'localDate': local_date.isoformat()}
            if self.streaming_registry is not None:
                described = [
                    self.streaming_registry.describe(item)
                    for item in (enriched.get('broadcasts') or [])
                ]
                enriched['streaming'] = [item for item in described if item]
            matches.append(enriched)
        matches.sort(key=lambda match: (match.get('utcDate') or '', match['canonicalFixtureId']))
        assert_unique_fixture_ids(matches)
        return matches

    @staticmethod
    def _cache_status(statuses):
        values = set(statuses)
        if values == {'fresh'}:
            return 'fresh'
        if values <= {'fresh', 'filled'} and 'filled' in values:
            return 'filled' if values == {'filled'} else 'mixed'
        return 'mixed'

    @staticmethod
    def _statistics(matches, local_zone):
        slots = {'morning': 0, 'afternoon': 0, 'evening': 0, 'lateNight': 0}
        for match in matches:
            try:
                kickoff = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
                if kickoff.tzinfo is None:
                    kickoff = kickoff.replace(tzinfo=timezone.utc)
                hour = kickoff.astimezone(local_zone).hour
            except (KeyError, TypeError, ValueError):
                continue
            if 6 <= hour < 12:
                slots['morning'] += 1
            elif 12 <= hour < 18:
                slots['afternoon'] += 1
            elif 18 <= hour < 24:
                slots['evening'] += 1
            else:
                slots['lateNight'] += 1
        return {'total': len(matches), 'byTimeSlot': slots}

    @staticmethod
    def _public_outcome(outcome, cache_status):
        return {
            'status': outcome.status.value,
            'requestedResources': list(outcome.requestedResources),
            'completedResources': list(outcome.completedResources),
            'requestCount': outcome.requestCount,
            'timeoutCount': outcome.timeoutCount,
            'rateLimitCount': outcome.rateLimitCount,
            'sourceUpdatedAt': outcome.sourceUpdatedAt,
            'durationMs': outcome.durationMs,
            'failureCategories': list(outcome.failureCategories),
            'cache': cache_status,
        }
