import os
from pathlib import Path
import re
from time import monotonic
from uuid import uuid4

from flask import Flask, g, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .build_info import load_build_info
from .config import Config
from .domain.capabilities import build_capability_manifest
from .observability import MetricsRegistry, log_event
from .providers.espn import EspnProvider
from .providers.football_data import FootballDataProvider
from .providers.http import ProviderHttpClient
from .routes.api import api
from .routes.health import health
from .routes.pages import pages
from .services.cache_backend import build_cache_backend
from .services.fixture_service import CanonicalFixtureService
from .services.football_data import FootballDataClient
from .services.rate_limit import MemoryRateLimiter
from .services.teams import TeamAnalysisService
from .services.team_identity import TeamIdentityResolver


def create_app(config=None):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    trusted_proxy_hops = max(0, int(app.config.get('TRUSTED_PROXY_HOPS', 0)))
    if trusted_proxy_hops:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_hops,
            x_proto=trusted_proxy_hops,
            x_host=trusted_proxy_hops,
        )

    build_info = load_build_info(os.environ)
    app.extensions['build_info'] = build_info
    app.extensions['metrics'] = MetricsRegistry()
    app.extensions['cache_backend'] = build_cache_backend(
        app.config,
        app.extensions['metrics'],
        environment=build_info.environment,
    )
    app.extensions['rate_limiter'] = MemoryRateLimiter(
        limit=app.config['RATE_LIMIT_MAX_REQUESTS'],
        window_seconds=app.config['RATE_LIMIT_WINDOW_SECONDS'],
        max_keys=app.config['RATE_LIMIT_MAX_KEYS'],
    )
    app.extensions['provider_capabilities'] = build_capability_manifest(
        football_data_configured=bool(app.config.get('FOOTBALL_DATA_API_KEY')),
    )

    request_id_pattern = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')

    @app.before_request
    def begin_request_observation():
        supplied_request_id = request.headers.get('X-Request-ID', '')
        g.request_id = (
            supplied_request_id
            if request_id_pattern.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        g.request_started = monotonic()

    @app.before_request
    def enforce_expensive_route_rate_limit():
        expensive_endpoints = {
            'api.competitions',
            'api.competition_teams',
            'api.team',
            'api.team_analysis',
            'api.canonical_team_analysis',
            'api.fixtures_by_date',
            'api.fixtures_v2',
            'api.fixture_v2',
        }
        if request.endpoint not in expensive_endpoints:
            return None
        client_key = request.remote_addr or 'unknown'
        decision = app.extensions['rate_limiter'].check(
            f'{request.endpoint}:{client_key}',
        )
        if decision.allowed:
            return None
        response = jsonify({
            'error': {
                'code': 'rate_limited',
                'message': 'Too many requests. Please retry shortly.',
                'retryable': True,
                'retryAfterSeconds': decision.retryAfterSeconds,
                'requestId': g.request_id,
            },
        })
        response.status_code = 429
        response.headers['Retry-After'] = str(decision.retryAfterSeconds)
        return response

    @app.context_processor
    def inject_build_info():
        public_base = app.config['PUBLIC_BASE_URL']
        return {
            'build': build_info.as_public_dict(),
            'canonical_url': f'{public_base}{request.path}',
            'public_base_url': public_base,
        }

    timeout = (
        app.config['HTTP_CONNECT_TIMEOUT'],
        app.config['HTTP_READ_TIMEOUT'],
    )
    football_data = FootballDataClient(
        app.config.get('FOOTBALL_DATA_API_KEY'),
        app.config['FOOTBALL_DATA_BASE_URL'],
        timeout=timeout,
    )
    app.extensions['football_data'] = football_data
    app.extensions['team_analysis'] = TeamAnalysisService(football_data)
    app.extensions['team_identities'] = TeamIdentityResolver.from_file(
        Path(__file__).parent / 'data' / 'team-provider-map.json',
    )
    provider_options = {
        'timeout': timeout,
        'max_retries': app.config['PROVIDER_MAX_RETRIES'],
        'max_json_bytes': app.config['PROVIDER_MAX_JSON_BYTES'],
        'retry_after_max': app.config['PROVIDER_RETRY_AFTER_MAX'],
        'pool_connections': app.config['PROVIDER_POOL_CONNECTIONS'],
        'pool_maxsize': app.config['PROVIDER_POOL_MAXSIZE'],
    }
    espn_http = ProviderHttpClient(app.config['ESPN_BASE_URL'], **provider_options)
    football_http = ProviderHttpClient(
        app.config['FOOTBALL_DATA_BASE_URL'],
        **provider_options,
    )
    football_http.session.headers['X-Auth-Token'] = (
        app.config.get('FOOTBALL_DATA_API_KEY') or ''
    )
    app.extensions['espn_provider'] = EspnProvider(
        espn_http,
        identities=app.extensions['team_identities'],
    )
    app.extensions['football_data_provider'] = FootballDataProvider(
        football_http,
        app.extensions['team_identities'],
        enabled=bool(app.config.get('FOOTBALL_DATA_API_KEY')),
    )
    app.extensions['fixture_service'] = CanonicalFixtureService(
        app.extensions['espn_provider'],
        app.extensions['football_data_provider'],
        app.extensions['cache_backend'],
        cache_ttl_seconds=app.config['FIXTURE_CACHE_TTL'],
        stale_ttl_seconds=app.config['FIXTURE_STALE_TTL'],
        provider_budget_seconds=app.config['FIXTURE_FETCH_DEADLINE'],
    )
    app.register_blueprint(pages)
    app.register_blueprint(api)
    app.register_blueprint(health)

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': {
                    'code': 'not_found',
                    'message': 'The requested API route does not exist.',
                    'retryable': False,
                    'requestId': g.request_id,
                },
            }), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(_error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': {
                    'code': 'internal_error',
                    'message': 'The request could not be completed.',
                    'retryable': True,
                    'requestId': g.request_id,
                },
            }), 500
        return render_template('500.html'), 500

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=()',
        )
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
            "connect-src 'self'; frame-src https://widgets.sofascore.com; "
            "frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'",
        )
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        elif not request.path.startswith('/static/'):
            response.headers.setdefault('Cache-Control', 'no-cache')
        if request.path == '/static/sw.js':
            response.headers['Service-Worker-Allowed'] = '/'
            response.headers['Cache-Control'] = 'no-cache'
        if request.is_secure and build_info.environment == 'production':
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        response.headers['X-Request-ID'] = g.request_id
        metrics = app.extensions['metrics']
        metrics.increment('api.requests')
        if response.status_code >= 400:
            metrics.increment('api.errors')
        if response.status_code == 429:
            metrics.increment('api.rate_limited')
        log_event(
            app.logger,
            'request_completed',
            requestId=g.request_id,
            endpoint=request.endpoint,
            statusCode=response.status_code,
            durationMs=round((monotonic() - g.request_started) * 1000),
        )
        return response

    log_event(
        app.logger,
        'application_started',
        version=build_info.version,
        commitSha=build_info.commit_sha[:12],
        environment=build_info.environment,
    )
    return app
