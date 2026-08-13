from datetime import date
import hmac
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from flask import Blueprint, abort, current_app, g, jsonify, request

from soccer_scanner.domain.models import FixtureState, FixtureUnavailable

api = Blueprint('api', __name__, url_prefix='/api')


def provider_error(error):
    current_app.logger.warning('Football provider request failed: %s', error)
    status = 502
    if isinstance(error, requests.HTTPError) and error.response is not None:
        status = 429 if error.response.status_code == 429 else 502
    return jsonify({
        'error': 'Football data is temporarily unavailable. Please try again.',
        'code': 'provider_unavailable',
    }), status


@api.get('/competitions')
def competitions():
    try:
        return jsonify(current_app.extensions['football_data'].get('competitions'))
    except requests.RequestException as error:
        return provider_error(error)


@api.get('/teams/<competition_id>')
def competition_teams(competition_id):
    try:
        return jsonify(current_app.extensions['football_data'].get(
            f'competitions/{competition_id}/teams'
        ))
    except requests.RequestException as error:
        return provider_error(error)


@api.get('/team/<team_id>')
def team(team_id):
    try:
        return jsonify(current_app.extensions['football_data'].get(f'teams/{team_id}'))
    except requests.RequestException as error:
        return provider_error(error)


@api.get('/team-analysis/<team_id>')
def team_analysis(team_id):
    if not current_app.extensions['feature_flags'].is_enabled('team_intelligence'):
        abort(404)
    try:
        return jsonify(current_app.extensions['team_analysis'].analyze(team_id))
    except requests.RequestException as error:
        return provider_error(error)


@api.get('/v2/teams/<canonical_id>/analysis')
def canonical_team_analysis(canonical_id):
    if not current_app.extensions['feature_flags'].is_enabled('team_intelligence'):
        abort(404)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', canonical_id):
        return jsonify({
            'error': {
                'code': 'team_identity_unavailable',
                'message': 'Verified team analysis is unavailable for this team.',
                'retryable': False,
                'requestId': g.request_id,
            },
        }), 404
    identities = current_app.extensions['team_identities']
    provider_id = identities.provider_id(canonical_id, 'football-data')
    if provider_id is None:
        return jsonify({
            'error': {
                'code': 'team_identity_unavailable',
                'message': 'Verified team analysis is unavailable for this team.',
                'retryable': False,
                'requestId': g.request_id,
            },
        }), 404
    try:
        analysis = current_app.extensions['team_analysis'].analyze(provider_id)
        team_info = analysis.setdefault('team_info', {})
        team_info['canonicalId'] = canonical_id
        team_info['provider'] = 'football-data'
        team_info['providerId'] = provider_id
        return jsonify(analysis)
    except requests.RequestException as error:
        return provider_error(error)


def _fixture_error(code, message, status, *, retryable=False, retry_after=None):
    response = jsonify({
        'error': {
            'code': code,
            'message': message,
            'retryable': retryable,
            'retryAfterSeconds': retry_after,
            'lastSuccessfulUpdate': None,
            'requestId': g.request_id,
        },
    })
    response.status_code = status
    if retry_after is not None:
        response.headers['Retry-After'] = str(retry_after)
    return response


def _fixtures_by_date(*, versioned):
    if versioned:
        allowed = {'date', 'timezone'}
        unknown = sorted(set(request.args) - allowed)
        if unknown:
            return _fixture_error(
                'invalid_request',
                'Unsupported fixture query parameters.',
                400,
            )
    raw_date = request.args.get('date', date.today().isoformat())
    try:
        requested_date = date.fromisoformat(raw_date)
    except ValueError:
        if versioned:
            return _fixture_error('invalid_date', 'Invalid date. Use YYYY-MM-DD.', 400)
        return jsonify({'error': 'Invalid date. Use YYYY-MM-DD.', 'code': 'invalid_date'}), 400
    timezone_name = request.args.get('timezone', 'UTC')
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        if versioned:
            return _fixture_error('invalid_timezone', 'Invalid IANA timezone.', 400)
        return jsonify({
            'error': 'Invalid IANA timezone.',
            'code': 'invalid_timezone',
        }), 400
    try:
        return jsonify(current_app.extensions['fixture_service'].fixtures_for_date(
            requested_date, timezone_name
        ))
    except FixtureUnavailable as error:
        code = (
            'rate_limited'
            if error.state is FixtureState.RATE_LIMITED
            else 'provider_unavailable'
        )
        status = 429 if error.state is FixtureState.RATE_LIMITED else 503
        return _fixture_error(
            code,
            str(error),
            status,
            retryable=True,
            retry_after=error.retry_after_seconds,
        )


@api.get('/v2/fixtures')
def fixtures_v2():
    return _fixtures_by_date(versioned=True)


@api.get('/v2/search')
def search_v2():
    if not current_app.extensions['feature_flags'].is_enabled('search'):
        abort(404)
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return _fixture_error('invalid_query', 'Search requires at least two characters.', 400)
    timezone_name = request.args.get('timezone', 'UTC')
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return _fixture_error('invalid_timezone', 'Invalid IANA timezone.', 400)

    def parse_date(name):
        raw = request.args.get(name)
        return date.fromisoformat(raw) if raw else None

    try:
        start_date = parse_date('start')
        end_date = parse_date('end')
        limit = min(50, max(1, int(request.args.get('limit', '20'))))
        offset = max(0, int(request.args.get('offset', '0')))
        result = current_app.extensions['search_service'].search(
            query,
            timezone_name=timezone_name,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    except (TypeError, ValueError):
        return _fixture_error('invalid_request', 'Invalid search parameters.', 400)
    return jsonify(result)


@api.get('/v2/capabilities')
def capabilities_v2():
    return jsonify({
        'capabilities': current_app.extensions['provider_capabilities'],
    })


@api.get('/v2/app-config')
def app_config_v2():
    """Non-sensitive client configuration for web and native clients.

    Only values a client may legitimately branch on are exposed. Connection
    strings, tokens and provider keys are never included.
    """
    build = current_app.extensions['build_info'].as_public_dict()
    return jsonify({
        'apiVersion': 'v2',
        'publicBaseUrl': current_app.config['PUBLIC_BASE_URL'],
        'environment': build['environment'],
        'webVersion': build['version'],
        # Clients older than this must prompt to upgrade rather than guess at
        # response shapes they cannot parse.
        'minimumSupportedClient': {'ios': '1.0.0', 'web': '2.0.0'},
        'features': current_app.extensions['feature_flags'].as_dict(),
        'defaults': {
            'timezone': 'UTC',
            'scoresHiddenByDefault': True,
        },
        'links': {
            'privacy': '/privacy',
            'terms': '/terms',
            'dataSources': '/data-sources',
        },
    })


@api.get('/v2/operations')
def operations_v2():
    expected = str(current_app.config.get('OPS_ADMIN_TOKEN') or '')
    supplied = request.headers.get('X-Ops-Token', '')
    if expected and not hmac.compare_digest(supplied, expected):
        return _fixture_error('unauthorized', 'Operations token required.', 401)
    from soccer_scanner.routes.health import _provider_health, _rate_limit_health, ready

    ready_response = ready()
    if isinstance(ready_response, tuple):
        ready_response = ready_response[0]
    identities = current_app.extensions['fixture_identities']
    try:
        unresolved = identities.unresolved_report(limit=1)['total']
    except Exception:
        unresolved = None
    broadcast_registry = current_app.extensions.get('broadcast_sources')
    streaming_registry = current_app.extensions.get('streaming_registry')
    standings = current_app.extensions.get('standings_seasons')
    return jsonify({
        'build': current_app.extensions['build_info'].as_public_dict(),
        'readiness': ready_response.get_json(),
        'providers': _provider_health(),
        'rateLimit': _rate_limit_health(),
        'metrics': current_app.extensions['metrics'].snapshot(),
        'diagnostics': {
            'unresolvedIdentityCount': unresolved,
            'streamingRegistryServices': streaming_registry.service_count() if streaming_registry else 0,
            'broadcastSources': [
                {'id': source['id'], 'status': source.get('status'), 'scope': source.get('scope', [])}
                for source in (broadcast_registry.sources() if broadcast_registry else [])
            ],
            'standings': {
                'stale': standings.is_stale() if standings else None,
                'reviewWarnings': standings.review_warnings() if standings else [],
            },
            'backups': {
                'status': 'not_exposed',
                'message': 'Backup configuration requires provider-console verification.',
            },
        },
    })


@api.get('/internal/identity-report')
def identity_report():
    configured_token = str(current_app.config.get('OPS_ADMIN_TOKEN') or '')
    authorization = request.headers.get('Authorization', '')
    supplied_token = (
        authorization[7:]
        if authorization.startswith('Bearer ')
        else ''
    )
    if not configured_token or not hmac.compare_digest(supplied_token, configured_token):
        return _fixture_error(
            'unauthorized',
            'Valid operations credentials are required.',
            401,
        )
    raw_limit = request.args.get('limit', '100')
    try:
        limit = min(500, max(1, int(raw_limit)))
    except ValueError:
        return _fixture_error('invalid_request', 'Limit must be an integer.', 400)
    return jsonify(
        current_app.extensions['fixture_identities'].unresolved_report(limit=limit)
    )


@api.get('/v2/fixtures/<canonical_fixture_id>')
def fixture_v2(canonical_fixture_id):
    if not re.fullmatch(r'fx_[a-f0-9]{24}', canonical_fixture_id):
        return _fixture_error('invalid_fixture_id', 'Invalid canonical fixture ID.', 400)
    match = current_app.extensions['fixture_service'].lookup_fixture(canonical_fixture_id)
    if match is None:
        return _fixture_error('fixture_not_found', 'Fixture link is unavailable or expired.', 404)
    return jsonify({'fixture': match})


@api.get('/matches-today')
def fixtures_by_date():
    return _fixtures_by_date(versioned=False)
