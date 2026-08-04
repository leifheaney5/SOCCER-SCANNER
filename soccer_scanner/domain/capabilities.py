from dataclasses import asdict, dataclass
from enum import Enum


class Capability(str, Enum):
    EVENTS = 'events'
    LINEUPS = 'lineups'
    STATISTICS = 'statistics'
    BROADCASTS = 'broadcasts'
    SQUADS = 'squads'
    STANDINGS = 'standings'
    NOTIFICATIONS = 'notifications'


class CapabilityStatus(str, Enum):
    SUPPORTED = 'supported'
    UNAVAILABLE = 'unavailable'
    NOT_SUPPORTED = 'not_supported'


@dataclass(frozen=True)
class CapabilityOutcome:
    status: CapabilityStatus
    reason: str
    provider: str | None = None

    def as_dict(self):
        result = asdict(self)
        result['status'] = self.status.value
        return {key: value for key, value in result.items() if value is not None}


def build_capability_manifest(*, football_data_configured):
    not_implemented = {
        Capability.EVENTS: 'No contracted event-feed adapter is implemented.',
        Capability.LINEUPS: 'No contracted lineup-feed adapter is implemented.',
        Capability.STATISTICS: 'No contracted match-statistics adapter is implemented.',
        Capability.BROADCASTS: 'No licensed broadcast-listing source is configured.',
        Capability.NOTIFICATIONS: 'Notification delivery and consent infrastructure are not implemented.',
    }
    manifest = {
        capability.value: CapabilityOutcome(
            CapabilityStatus.NOT_SUPPORTED,
            reason,
        ).as_dict()
        for capability, reason in not_implemented.items()
    }
    provider_status = (
        CapabilityStatus.SUPPORTED
        if football_data_configured
        else CapabilityStatus.UNAVAILABLE
    )
    provider_reason = (
        'Available from the configured Football-Data.org integration.'
        if football_data_configured
        else 'Requires a configured Football-Data.org API key.'
    )
    for capability in (Capability.SQUADS, Capability.STANDINGS):
        manifest[capability.value] = CapabilityOutcome(
            provider_status,
            provider_reason,
            provider='football-data',
        ).as_dict()
    return manifest
