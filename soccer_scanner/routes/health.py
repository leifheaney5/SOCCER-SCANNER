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
    return jsonify({
        'status': status,
        'missing': missing,
        'build': current_app.extensions['build_info'].as_public_dict(),
        'cache': current_app.extensions['cache_backend'].health(),
    }), 200 if not missing else 503


@health.get('/version')
def version():
    return jsonify(current_app.extensions['build_info'].as_public_dict())


@health.get('/metrics')
def metrics():
    return jsonify(current_app.extensions['metrics'].snapshot())
