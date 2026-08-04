"""Validated, public-safe application build identity."""

from dataclasses import dataclass
import re

from .version import __version__


_SHA_PATTERN = re.compile(r'^[0-9a-fA-F]{7,64}$')
_SAFE_TOKEN_PATTERN = re.compile(r'[^0-9A-Za-z._-]+')


def _first_value(environ, *names):
    for name in names:
        value = environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


@dataclass(frozen=True)
class BuildInfo:
    version: str
    commit_sha: str
    build_timestamp: str | None
    environment: str
    asset_version: str

    def as_public_dict(self):
        return {
            'version': self.version,
            'commitSha': self.commit_sha,
            'buildTimestamp': self.build_timestamp,
            'environment': self.environment,
            'assetVersion': self.asset_version,
        }


def load_build_info(environ):
    """Load build metadata from the deployment environment.

    Production must be tied to a real revision. Development and tests can use
    an explicit, cache-safe application version when no revision is available.
    """

    version = _first_value(environ, 'APP_VERSION') or __version__
    environment = (
        _first_value(environ, 'APP_ENVIRONMENT', 'RAILWAY_ENVIRONMENT_NAME')
        or 'development'
    )
    commit_sha = _first_value(environ, 'GIT_COMMIT_SHA', 'RAILWAY_GIT_COMMIT_SHA')

    if commit_sha and not _SHA_PATTERN.fullmatch(commit_sha):
        raise RuntimeError('Application commit SHA is malformed.')
    if environment.lower() in {'production', 'prod'} and not commit_sha:
        raise RuntimeError('Application commit SHA is required in production.')

    commit_sha = commit_sha.lower() if commit_sha else 'unknown'
    fallback_token = _SAFE_TOKEN_PATTERN.sub('-', version).strip('-._') or 'development'
    asset_version = commit_sha[:12] if commit_sha != 'unknown' else fallback_token
    build_timestamp = _first_value(
        environ,
        'BUILD_TIMESTAMP',
        'RAILWAY_DEPLOYMENT_CREATED_AT',
    )

    return BuildInfo(
        version=version,
        commit_sha=commit_sha,
        build_timestamp=build_timestamp,
        environment=environment,
        asset_version=asset_version,
    )
