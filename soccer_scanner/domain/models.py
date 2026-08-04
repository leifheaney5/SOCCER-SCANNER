"""Typed provider and fixture service outcomes."""

from dataclasses import dataclass
from enum import Enum


class FixtureState(str, Enum):
    SUCCESS = 'success'
    PARTIAL = 'partial'
    STALE = 'stale'
    EMPTY_CONFIRMED = 'empty_confirmed'
    PROVIDER_UNAVAILABLE = 'provider_unavailable'
    RATE_LIMITED = 'rate_limited'
    INVALID_REQUEST = 'invalid_request'


class ProviderStatus(str, Enum):
    SUCCESS = 'success'
    PARTIAL = 'partial'
    UNAVAILABLE = 'unavailable'
    RATE_LIMITED = 'rate_limited'
    DISABLED = 'disabled'


@dataclass(frozen=True)
class ProviderOutcome:
    provider: str
    status: ProviderStatus
    fixtures: tuple
    requestedResources: tuple
    completedResources: tuple
    requestCount: int
    timeoutCount: int
    rateLimitCount: int
    sourceUpdatedAt: str | None
    durationMs: int
    failureCategories: tuple


class FixtureUnavailable(RuntimeError):
    def __init__(
        self,
        state,
        message,
        retry_after_seconds=None,
        last_successful_update=None,
    ):
        super().__init__(message)
        self.state = state
        self.retry_after_seconds = retry_after_seconds
        self.last_successful_update = last_successful_update
