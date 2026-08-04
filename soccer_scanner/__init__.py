import os

from flask import Flask

from .build_info import load_build_info
from .config import Config
from .routes.api import api
from .routes.health import health
from .routes.pages import pages
from .services.cache import TTLCache
from .services.fixtures import FixtureService
from .services.football_data import FootballDataClient
from .services.teams import TeamAnalysisService


def create_app(config=None):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    build_info = load_build_info(os.environ)
    app.extensions['build_info'] = build_info

    @app.context_processor
    def inject_build_info():
        return {'build': build_info.as_public_dict()}

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
    app.extensions['fixture_service'] = FixtureService(
        football_data,
        TTLCache(
            app.config['FIXTURE_CACHE_TTL'],
            stale_ttl_seconds=app.config['FIXTURE_STALE_TTL'],
            max_entries=app.config['FIXTURE_CACHE_MAX_ENTRIES'],
        ),
        timeout=timeout,
        fetch_deadline=app.config['FIXTURE_FETCH_DEADLINE'],
    )
    app.register_blueprint(pages)
    app.register_blueprint(api)
    app.register_blueprint(health)

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
            "object-src 'none'; base-uri 'self'; form-action 'self'",
        )
        return response
    return app
