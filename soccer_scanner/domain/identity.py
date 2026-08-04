"""Canonical fixture identity and deterministic field-level merging."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json


KICKOFF_TOLERANCE_SECONDS = 10 * 60
SOURCE_ORDER = {'espn': 0, 'football-data': 1}


def _instant(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _identity_value(container):
    if not isinstance(container, dict):
        return None
    return container.get('canonicalId')


def fixtures_refer_to_same_event(left, right, *, tolerance_seconds=KICKOFF_TOLERANCE_SECONDS):
    left_time = _instant(left.get('utcDate'))
    right_time = _instant(right.get('utcDate'))
    if left_time is None or right_time is None:
        return False
    if abs((left_time - right_time).total_seconds()) > tolerance_seconds:
        return False
    required = ('competition', 'homeTeam', 'awayTeam')
    if any(not _identity_value(left.get(field)) or not _identity_value(right.get(field)) for field in required):
        return False
    if any(_identity_value(left[field]) != _identity_value(right[field]) for field in required):
        return False
    left_season = (left.get('season') or {}).get('year')
    right_season = (right.get('season') or {}).get('year')
    if left_season is not None and right_season is not None and left_season != right_season:
        return False
    left_stage = left.get('stage')
    right_stage = right.get('stage')
    if left_stage and right_stage and left_stage != right_stage:
        return False
    return True


def _provider(fixture):
    providers = fixture.get('providerIds') or {}
    return next(iter(providers), 'unknown')


def _freshness(fixture):
    return _instant(fixture.get('sourceUpdatedAt')) or datetime.min.replace(tzinfo=timezone.utc)


def _ranked(group, *, provider_first=False):
    return sorted(
        group,
        key=lambda fixture: (
            SOURCE_ORDER.get(_provider(fixture), 99) if provider_first else -_freshness(fixture).timestamp(),
            -_freshness(fixture).timestamp() if provider_first else SOURCE_ORDER.get(_provider(fixture), 99),
            json.dumps(fixture.get('providerIds') or {}, sort_keys=True),
        ),
    )


def _first_value(group, field, *, provider_first=False):
    for fixture in _ranked(group, provider_first=provider_first):
        value = fixture.get(field)
        if value is not None and value != '' and value != []:
            return deepcopy(value)
    return None


def _merge_entity(group, field):
    entities = [fixture.get(field) for fixture in _ranked(group, provider_first=True)]
    entities = [entity for entity in entities if isinstance(entity, dict)]
    if not entities:
        return None
    result = deepcopy(entities[0])
    provider_ids = {}
    for entity in entities:
        provider_ids.update(entity.get('providerIds') or {})
        for key, value in entity.items():
            if key in {'provider', 'providerId', 'providerIds'}:
                continue
            if result.get(key) in (None, '') and value not in (None, ''):
                result[key] = deepcopy(value)
    result['providerIds'] = provider_ids
    return result


def _score(group):
    candidates = []
    for fixture in group:
        score = fixture.get('score')
        full_time = score.get('fullTime') if isinstance(score, dict) else None
        has_score = isinstance(full_time, dict) and (
            full_time.get('home') is not None or full_time.get('away') is not None
        )
        candidates.append((has_score, _freshness(fixture), -SOURCE_ORDER.get(_provider(fixture), 99), score))
    return deepcopy(max(candidates, key=lambda item: item[:3])[3]) if candidates else None


def _canonical_id(group, merged):
    kickoffs = sorted(instant for item in group if (instant := _instant(item.get('utcDate'))) is not None)
    kickoff = kickoffs[0].replace(second=0, microsecond=0).isoformat() if kickoffs else 'unknown'
    seed = '|'.join([
        str(_identity_value(merged.get('competition')) or 'unknown'),
        str(_identity_value(merged.get('homeTeam')) or 'unknown'),
        str(_identity_value(merged.get('awayTeam')) or 'unknown'),
        kickoff,
        str((merged.get('season') or {}).get('year') or ''),
        str(merged.get('stage') or ''),
    ])
    return f'fx_{hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]}'


def _merge_group(group):
    provider_ids = {}
    for fixture in group:
        provider_ids.update(fixture.get('providerIds') or {})
    merged = {
        'canonicalFixtureId': None,
        'providerIds': provider_ids,
        'utcDate': min(
            (fixture.get('utcDate') for fixture in group if _instant(fixture.get('utcDate'))),
            key=lambda value: _instant(value),
            default=None,
        ),
        'localDate': None,
        'status': _first_value(group, 'status'),
        'homeTeam': _merge_entity(group, 'homeTeam'),
        'awayTeam': _merge_entity(group, 'awayTeam'),
        'competition': _merge_entity(group, 'competition'),
        'score': _score(group),
        'season': _first_value(group, 'season', provider_first=True),
        'stage': _first_value(group, 'stage', provider_first=True),
        'round': _first_value(group, 'round', provider_first=True),
        'matchday': _first_value(group, 'matchday', provider_first=True),
        'venue': _first_value(group, 'venue'),
        'referees': _first_value(group, 'referees'),
        'aggregate': _first_value(group, 'aggregate'),
        'sourceUpdatedAt': max(
            (fixture.get('sourceUpdatedAt') for fixture in group if _instant(fixture.get('sourceUpdatedAt'))),
            key=lambda value: _instant(value),
            default=None,
        ),
    }
    merged['sources'] = sorted(provider_ids, key=lambda source: SOURCE_ORDER.get(source, 99))
    merged['canonicalFixtureId'] = _canonical_id(group, merged)
    optional = ('season', 'stage', 'round', 'matchday', 'venue', 'referees', 'aggregate')
    merged['dataQuality'] = {
        'missingFields': [field for field in optional if merged.get(field) is None],
    }
    return merged


def merge_fixtures(fixtures):
    groups = []
    for fixture in sorted(
        (deepcopy(item) for item in fixtures),
        key=lambda item: (_instant(item.get('utcDate')) or datetime.max.replace(tzinfo=timezone.utc), _provider(item)),
    ):
        group = next(
            (candidate for candidate in groups if fixtures_refer_to_same_event(candidate[0], fixture)),
            None,
        )
        if group is None:
            groups.append([fixture])
        else:
            group.append(fixture)
    return [_merge_group(group) for group in groups]
