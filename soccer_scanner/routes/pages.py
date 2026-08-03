from flask import Blueprint, render_template

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
