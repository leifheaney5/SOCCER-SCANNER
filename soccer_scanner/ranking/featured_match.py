"""Favorite-aware featured-match selection without reordering schedules."""

from datetime import datetime, timezone


LIVE = {'in_progress', 'half_time', 'extra_time', 'penalties'}
UPCOMING = {'scheduled', 'delayed', 'unknown'}
FINISHED = {'finished'}


def _status(match):
    raw = match.get('status')
    return str(raw.get('code') if isinstance(raw, dict) else raw or '').casefold()


def _kickoff(match):
    try:
        value = datetime.fromisoformat(str(match.get('utcDate')).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return datetime.max.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _favorite(match, team_ids):
    return any(
        (match.get(side) or {}).get('canonicalId') in team_ids
        for side in ('homeTeam', 'awayTeam')
    )


def select_featured_match(matches, *, favorite_team_ids=()):
    fixtures = list(matches or [])
    favorites = set(favorite_team_ids or ())
    stable = lambda match: (_kickoff(match), str(match.get('canonicalFixtureId') or ''))

    for predicate in (
        lambda match: _status(match) in LIVE and _favorite(match, favorites),
        lambda match: _status(match) in LIVE,
        lambda match: _status(match) in UPCOMING and _favorite(match, favorites),
        lambda match: _status(match) in UPCOMING,
    ):
        candidates = [match for match in fixtures if predicate(match)]
        if candidates:
            return min(candidates, key=stable)
    completed = [match for match in fixtures if _status(match) in FINISHED]
    if completed:
        return max(completed, key=lambda match: (_kickoff(match), str(match.get('canonicalFixtureId') or '')))
    return None
