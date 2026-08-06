from datetime import datetime, timedelta, timezone
import json
import re

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, current_app, redirect, render_template, request, url_for

pages = Blueprint('pages', __name__)


@pages.get('/')
def fixtures():
    return render_template('matches_today.html')


@pages.get('/matches-today')
def legacy_fixtures():
    return render_template('matches_today.html')


@pages.get('/teams')
def teams():
    return render_template('index.html')


@pages.get('/league-tables')
def league_tables():
    seasons = current_app.extensions['standings_seasons']
    return render_template(
        'league_tables.html',
        competitions=seasons.competitions,
        seasons_stale=seasons.is_stale(),
    )


@pages.get('/calendar')
def calendar():
    return render_template('calendar.html')


@pages.get('/privacy')
def privacy():
    return render_template('privacy.html')


@pages.get('/data-sources')
def data_sources():
    return render_template('data_sources.html')


@pages.get('/offline')
def offline():
    return render_template('offline.html')


@pages.get('/terms')
def terms():
    return render_template('terms.html')


# Surfaces that must never be advertised to crawlers or listed in the sitemap.
_NON_INDEXABLE = ('/api/', '/health/', '/offline')

_SITEMAP_ROUTES = (
    ('/', 'daily', '1.0'),
    ('/calendar', 'daily', '0.8'),
    ('/teams', 'weekly', '0.6'),
    ('/league-tables', 'weekly', '0.6'),
    ('/data-sources', 'monthly', '0.3'),
    ('/privacy', 'yearly', '0.2'),
    # /terms is a labelled engineering draft (see templates/terms.html) and
    # carries its own noindex meta tag; it stays reachable via the route and
    # footer link but is deliberately excluded from the sitemap.
)


def _is_production():
    return current_app.extensions['build_info'].environment.lower() in {'production', 'prod'}


@pages.get('/robots.txt')
def robots():
    base = current_app.config['PUBLIC_BASE_URL'].rstrip('/')
    # A crawlable staging environment competes with production for the same
    # content, so every non-production deployment refuses indexing outright.
    if not _is_production():
        return Response('User-agent: *\nDisallow: /\n', mimetype='text/plain')
    lines = ['User-agent: *', 'Allow: /']
    lines += [f'Disallow: {path}' for path in _NON_INDEXABLE]
    lines += ['', f'Sitemap: {base}/sitemap.xml', '']
    return Response('\n'.join(lines), mimetype='text/plain')


@pages.get('/sitemap.xml')
def sitemap():
    base = current_app.config['PUBLIC_BASE_URL'].rstrip('/')
    today = datetime.now(timezone.utc).date().isoformat()
    entries = [
        '  <url>'
        f'<loc>{base}{path}</loc>'
        f'<lastmod>{today}</lastmod>'
        f'<changefreq>{frequency}</changefreq>'
        f'<priority>{priority}</priority>'
        '</url>'
        for path, frequency, priority in _SITEMAP_ROUTES
    ]
    document = '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        *entries,
        '</urlset>',
        '',
    ])
    return Response(document, mimetype='application/xml')


@pages.get('/.well-known/apple-app-site-association')
def apple_app_site_association():
    """Served only when real Apple identifiers are configured.

    Apple requires this file be returned as JSON with no redirect. Publishing
    placeholder identifiers would break universal links for whoever really
    owns them, so an unconfigured deployment returns 404 instead.
    """
    team_id = current_app.config.get('APPLE_TEAM_ID')
    bundle_id = current_app.config.get('APPLE_BUNDLE_ID')
    if not team_id or not bundle_id:
        return render_template('404.html'), 404
    payload = {
        'applinks': {
            'details': [{
                'appIDs': [f'{team_id}.{bundle_id}'],
                'components': [
                    {'/': '/fixtures/*', 'comment': 'Fixture detail'},
                    {'/': '/teams/*', 'comment': 'Team detail'},
                    {'/': '/competitions/*', 'comment': 'Competition detail'},
                    {'/': '/calendar', 'comment': 'Calendar'},
                ],
            }],
        },
        'webcredentials': {'apps': [f'{team_id}.{bundle_id}']},
    }
    return Response(
        json.dumps(payload, indent=2),
        mimetype='application/json',
        headers={'Cache-Control': 'public, max-age=3600'},
    )


def _fixture_from_link(canonical_fixture_id):
    if not re.fullmatch(r'fx_[a-f0-9]{24}', canonical_fixture_id):
        return None
    return current_app.extensions['fixture_service'].lookup_fixture(canonical_fixture_id)


def _resolved_timezone(requested):
    """Honour an explicit, valid IANA zone; otherwise fall back to UTC.

    A stored ``localDate`` belongs to whichever zone produced it, so it can
    never be reused as if it were a UTC day.
    """
    if not requested:
        return timezone.utc, 'UTC'
    try:
        return ZoneInfo(str(requested)), str(requested)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc, 'UTC'


def _fixture_day_in_zone(match, zone):
    """The calendar day a fixture belongs to, in the supplied zone."""
    raw = str(match.get('utcDate') or '').strip()
    if not raw:
        return None
    try:
        instant = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(zone).date().isoformat()


@pages.get('/fixtures/<canonical_fixture_id>')
def fixture_link(canonical_fixture_id):
    match = _fixture_from_link(canonical_fixture_id)
    if match is None:
        return render_template('fixture_link_unavailable.html'), 404
    zone, zone_name = _resolved_timezone(request.args.get('timezone'))
    return redirect(url_for(
        'pages.fixtures',
        date=_fixture_day_in_zone(match, zone) or match.get('localDate'),
        timezone=zone_name,
        fixture=canonical_fixture_id,
    ))


def _ics_escape(value):
    return str(value or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


@pages.get('/fixtures/<canonical_fixture_id>.ics')
def fixture_calendar(canonical_fixture_id):
    match = _fixture_from_link(canonical_fixture_id)
    if match is None:
        return render_template('fixture_link_unavailable.html'), 404
    try:
        kickoff = datetime.fromisoformat(str(match['utcDate']).replace('Z', '+00:00'))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        kickoff = kickoff.astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError):
        return render_template('fixture_link_unavailable.html'), 404
    home = match.get('homeTeam', {}).get('name') or 'Home team'
    away = match.get('awayTeam', {}).get('name') or 'Away team'
    competition = match.get('competition', {}).get('name') or 'Soccer fixture'
    public_url = f"{current_app.config['PUBLIC_BASE_URL']}/fixtures/{canonical_fixture_id}"
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Soccer Scanner//Fixtures//EN',
        'CALSCALE:GREGORIAN',
        'BEGIN:VEVENT',
        f'UID:{canonical_fixture_id}@soccerscanner.pro',
        f'DTSTAMP:{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}',
        f'DTSTART:{kickoff.strftime("%Y%m%dT%H%M%SZ")}',
        f'DTEND:{(kickoff + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")}',
        f'SUMMARY:{_ics_escape(home)} vs {_ics_escape(away)}',
        f'DESCRIPTION:{_ics_escape(competition)}',
    ]
    if match.get('venue'):
        lines.append(f'LOCATION:{_ics_escape(match["venue"])}')
    lines.extend([f'URL:{public_url}', 'END:VEVENT', 'END:VCALENDAR', ''])
    return Response(
        '\r\n'.join(lines),
        mimetype='text/calendar',
        headers={'Content-Disposition': f'attachment; filename="{canonical_fixture_id}.ics"'},
    )


@pages.get('/teams/<canonical_id>')
def team_page(canonical_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', canonical_id):
        return render_template('404.html'), 404
    provider_id = current_app.extensions['team_identities'].provider_id(canonical_id, 'football-data')
    if provider_id is None:
        return render_template('404.html'), 404
    return render_template('team_page.html', canonical_id=canonical_id)


@pages.get('/competitions/<canonical_id>')
def competition_page(canonical_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', canonical_id):
        return render_template('404.html'), 404
    return render_template(
        'competition_page.html',
        canonical_id=canonical_id,
        competition_name=canonical_id.replace('-', ' ').title(),
    )
