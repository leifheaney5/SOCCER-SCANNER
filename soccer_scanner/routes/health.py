from flask import Blueprint, current_app, jsonify

health = Blueprint('health', __name__, url_prefix='/health')


@health.get('/live')
def live():
    return jsonify({'status': 'ok'})


@health.get('/ready')
def ready():
    required_services = ('football_data', 'fixture_service', 'team_analysis')
    missing = [name for name in required_services if name not in current_app.extensions]
    status = 'ready' if not missing else 'not_ready'
    return jsonify({'status': status, 'missing': missing}), 200 if not missing else 503
