from datetime import date
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from flask import Blueprint, current_app, g, jsonify, request

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
    try:
        return jsonify(current_app.extensions['team_analysis'].analyze(team_id))
    except requests.RequestException as error:
        return provider_error(error)


@api.get('/v2/teams/<canonical_id>/analysis')
def canonical_team_analysis(canonical_id):
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
