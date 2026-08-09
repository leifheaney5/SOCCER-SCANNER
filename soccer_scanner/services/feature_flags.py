"""Server-enforced feature flags.

Flags are declared here with an owner, an expiry and a safe default so a stale
flag is visible rather than silently permanent. Environment variables may
override a default per environment; nothing is client-controlled, because a
client-toggled flag is not an enforcement boundary.
"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class FeatureFlag:
    name: str
    default: bool
    owner: str
    expires: str
    description: str

    @property
    def env_var(self):
        return f'FEATURE_{self.name.upper()}'


FEATURE_FLAGS = (
    FeatureFlag('accounts', False, 'product', '2026-12-31',
                'User accounts. Off by the accounts-and-preferences ADR.'),
    FeatureFlag('favorites', False, 'product', '2026-12-31',
                'Persistent favorites. Requires accounts.'),
    FeatureFlag('streaming_links', True, 'product', '2026-12-31',
                'Official streaming-service links on fixture details.'),
    FeatureFlag('streaming_logos', False, 'design', '2026-12-31',
                'Local streaming-service logo assets.'),
    FeatureFlag('team_intelligence', False, 'engineering', '2026-12-31',
                'Temporarily disabled team analysis drawer and API.'),
    FeatureFlag('calendar_range_api', False, 'engineering', '2026-12-31',
                'Bounded multi-day calendar range endpoint.'),
    FeatureFlag('search', False, 'engineering', '2026-12-31',
                'Global search across teams, competitions and fixtures.'),
    FeatureFlag('notifications', False, 'product', '2026-12-31',
                'Push notifications. Requires the notifications ADR.'),
    FeatureFlag('apns', False, 'product', '2026-12-31',
                'Apple Push Notification service delivery.'),
    FeatureFlag('pwa_fixture_caching', True, 'engineering', '2026-12-31',
                'Offline snapshot of terminal fixtures.'),
    FeatureFlag('experimental_seo_pages', False, 'marketing', '2026-12-31',
                'Generated team and competition landing pages.'),
    FeatureFlag('ios_beta', False, 'engineering', '2026-12-31',
                'Native iOS beta capabilities.'),
)

_FLAGS_BY_NAME = {flag.name: flag for flag in FEATURE_FLAGS}


def _coerce(value, default):
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default


class FeatureFlagRegistry:
    def __init__(self, environ=None, overrides=None):
        source = os.environ if environ is None else environ
        self._values = {}
        for flag in FEATURE_FLAGS:
            resolved = _coerce(source.get(flag.env_var), flag.default)
            self._values[flag.name] = resolved
        for name, value in (overrides or {}).items():
            if name in self._values:
                self._values[name] = bool(value)

    def is_enabled(self, name):
        """Unknown flags are disabled: fail closed, never fail open."""
        return bool(self._values.get(name, False))

    def as_dict(self):
        return dict(self._values)

    def describe(self):
        return [
            {
                'name': flag.name,
                'enabled': self._values[flag.name],
                'default': flag.default,
                'owner': flag.owner,
                'expires': flag.expires,
                'description': flag.description,
            }
            for flag in FEATURE_FLAGS
        ]
