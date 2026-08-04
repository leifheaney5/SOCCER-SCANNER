from datetime import datetime, timedelta, timezone
import re

from flask import Blueprint, Response, current_app, redirect, render_template, url_for

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
    return render_template('league_tables.html')


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


def _fixture_from_link(canonical_fixture_id):
    if not re.fullmatch(r'fx_[a-f0-9]{24}', canonical_fixture_id):
        return None
    return current_app.extensions['fixture_service'].lookup_fixture(canonical_fixture_id)


@pages.get('/fixtures/<canonical_fixture_id>')
def fixture_link(canonical_fixture_id):
    match = _fixture_from_link(canonical_fixture_id)
    if match is None:
        return render_template('fixture_link_unavailable.html'), 404
    return redirect(url_for(
        'pages.fixtures',
        date=match.get('localDate'),
        timezone='UTC',
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
