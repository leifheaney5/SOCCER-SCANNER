from hmac import compare_digest

from flask import Blueprint, current_app, jsonify, request

health = Blueprint('health', __name__, url_prefix='/health')


def _rate_limit_health():
    limiter = current_app.extensions.get('rate_limiter')
    shared = bool(getattr(limiter, 'shared', False))
    degraded = bool(getattr(limiter, 'degraded', False))
    if not shared:
        status = 'development'
    elif degraded:
        status = 'degraded'
    else:
        status = 'ready'
    return {
        'backend': 'redis' if shared else 'memory',
        'shared': shared,
        'degraded': degraded,
        'status': status,
    }


def _provider_health():
    registry = current_app.extensions.get('provider_health')
    if registry is None:
        return {'status': 'unknown', 'providers': [], 'lastSuccessAt': None,
                'singleProvider': False}
    return registry.snapshot()


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
    rate_limit_health = _rate_limit_health()
    provider_health = _provider_health()
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
        # Process-local limiting in production means each worker enforces its
        # own budget, so the advertised limit is not the effective one.
        if not rate_limit_health['shared']:
            blocking.append('shared_rate_limiter_not_ready')
    status = 'ready' if not blocking else 'not_ready'
    return jsonify({
        'status': status,
        'missing': missing,
        'blocking': blocking,
        'build': current_app.extensions['build_info'].as_public_dict(),
        'cache': cache_health,
        'database': database_health,
        'rateLimit': rate_limit_health,
        'providers': provider_health,
    }), 200 if not blocking else 503


@health.get('/version')
def version():
    return jsonify(current_app.extensions['build_info'].as_public_dict())


@health.get('/metrics')
def metrics():
    # Operational counters describe provider behaviour and traffic shape, so
    # they are gated whenever an operations token is configured.
    expected = current_app.config.get('OPS_ADMIN_TOKEN')
    if expected:
        supplied = request.headers.get('X-Ops-Token', '')
        if not compare_digest(str(supplied), str(expected)):
            return jsonify({
                'error': {
                    'code': 'unauthorized',
                    'message': 'Operations token required.',
                    'retryable': False,
                },
            }), 401
    return jsonify(current_app.extensions['metrics'].snapshot())


@health.get('/providers')
def providers():
    # Always 200: this reports upstream state and is polled by monitoring,
    # which needs to distinguish "app is down" from "data is down".
    return jsonify(_provider_health())
