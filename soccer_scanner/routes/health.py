from flask import Blueprint, current_app, jsonify

health = Blueprint('health', __name__, url_prefix='/health')


@health.get('/live')
def live():
    return jsonify({'status': 'ok'})


@health.get('/ready')
def ready():
    required_services = ('football_data', 'fixture_service', 'team_analysis')
    missing = [name for name in required_services if name not in current_app.extensions]
    cache_health = current_app.extensions['cache_backend'].health()
    identities = current_app.extensions['fixture_identities']
    database_health = identities.health()
    database_health['durable'] = identities.durable
    blocking = [f'missing_service:{name}' for name in missing]
    environment = current_app.extensions['build_info'].environment.lower()
    if environment in {'production', 'prod'}:
        if not identities.durable:
            blocking.append('database_not_durable')
        if database_health.get('status') != 'ready':
            blocking.append('database_not_ready')
        if not (
            cache_health.get('shared') is True
            and cache_health.get('status') == 'ready'
        ):
            blocking.append('shared_cache_not_ready')
    status = 'ready' if not blocking else 'not_ready'
    return jsonify({
        'status': status,
        'missing': missing,
        'blocking': blocking,
        'build': current_app.extensions['build_info'].as_public_dict(),
        'cache': cache_health,
        'database': database_health,
    }), 200 if not blocking else 503


@health.get('/version')
def version():
    return jsonify(current_app.extensions['build_info'].as_public_dict())


@health.get('/metrics')
def metrics():
    return jsonify(current_app.extensions['metrics'].snapshot())
