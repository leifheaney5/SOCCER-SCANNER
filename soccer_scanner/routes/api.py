from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from flask import Blueprint, current_app, jsonify, request

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


@api.get('/matches-today')
def fixtures_by_date():
    raw_date = request.args.get('date', date.today().isoformat())
    try:
        requested_date = date.fromisoformat(raw_date)
    except ValueError:
        return jsonify({'error': 'Invalid date. Use YYYY-MM-DD.', 'code': 'invalid_date'}), 400
    timezone_name = request.args.get('timezone', 'UTC')
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return jsonify({
            'error': 'Invalid IANA timezone.',
            'code': 'invalid_timezone',
        }), 400
    return jsonify(current_app.extensions['fixture_service'].fixtures_for_date(
        requested_date, timezone_name
    ))
