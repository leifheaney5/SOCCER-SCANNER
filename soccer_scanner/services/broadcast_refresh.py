"""Scheduled, stale-safe storage for source-backed broadcast observations."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone


OBSERVATION_CACHE_KEY = 'broadcast_refresh_v1'
OBSERVATION_TTL_SECONDS = 2 * 60 * 60
OBSERVATION_STALE_SECONDS = 35 * 24 * 60 * 60
ROLLING_WINDOW_DAYS = 30


def _instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


class BroadcastObservationStore:
    """Persist a bounded observation snapshot in the shared fixture cache."""

    def __init__(self, cache):
        self.cache = cache

    def read(self):
        lookup = self.cache.get(OBSERVATION_CACHE_KEY, allow_stale=True)
        if lookup.status not in {'fresh', 'stale'} or not isinstance(lookup.value, dict):
            return None
        snapshot = deepcopy(lookup.value)
        snapshot['storageStatus'] = lookup.status
        return snapshot

    def write(self, snapshot, *, updated_at, age_seconds=0):
        value = deepcopy(snapshot)
        value['updatedAt'] = updated_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        self.cache.set(
            OBSERVATION_CACHE_KEY,
            value,
            ttl_seconds=max(0, OBSERVATION_TTL_SECONDS - age_seconds),
            stale_ttl_seconds=max(
                0,
                OBSERVATION_TTL_SECONDS + OBSERVATION_STALE_SECONDS
                - max(age_seconds, OBSERVATION_TTL_SECONDS),
            ),
        )
        return value


class BroadcastRefreshService:
    """Refresh today's fixture observations without coupling fixture requests."""

    def __init__(self, store, fixtures_loader, *, source_registry, now=None):
        self.store = store
        self.fixtures_loader = fixtures_loader
        self.source_registry = source_registry
        self.now = now or (lambda: datetime.now(timezone.utc))

    def refresh(self, requested_date):
        observed_at = self.now().astimezone(timezone.utc)
        try:
            previous = self.store.read() or {
                'observations': [], 'fixtures': [], 'coverage': {}, 'sources': {},
            }
        except Exception:
            return {'status': 'unavailable', 'coverage': {}, 'updatedAt': None}
        try:
            payload = self.fixtures_loader(requested_date)
            if not isinstance(payload, dict) or payload.get('state') not in {'success', 'partial', 'empty_confirmed'}:
                raise RuntimeError('Fixture source did not return a complete refresh payload.')
            espn_status = (payload.get('providers') or {}).get('espn', {}).get('status')
            if espn_status and espn_status not in {'success', 'empty_confirmed'}:
                raise RuntimeError('The official ESPN fixture source did not complete its refresh.')
            if payload.get('state') == 'partial' and espn_status not in {'success', 'empty_confirmed'}:
                raise RuntimeError('The official ESPN fixture source did not complete its refresh.')
            matches = payload.get('matches')
            if not isinstance(matches, list):
                raise RuntimeError('Fixture source returned an invalid match collection.')
            observations, fixtures, metrics = self._normalize(matches, observed_at)
            cutoff = observed_at - timedelta(days=ROLLING_WINDOW_DAYS)
            refreshed_fixture_ids = {item['fixtureKey'] for item in fixtures}
            retained = [
                item for item in previous.get('observations', [])
                if (_instant(item.get('fixtureDate')) or observed_at) >= cutoff
                and not (
                    item.get('sourceId') == 'espn-broadcasts'
                    and item.get('fixtureKey') in refreshed_fixture_ids
                )
            ]
            by_identity = {
                (
                    item.get('fixtureKey'), item.get('sourceId'), item.get('displayName'),
                    item.get('region'), item.get('type'),
                ): item
                for item in retained
            }
            for item in observations:
                identity = (
                    item['fixtureKey'], item['sourceId'], item['displayName'],
                    item['region'], item.get('type'),
                )
                by_identity[identity] = item
            retained_fixtures = {
                item['fixtureKey']: item
                for item in previous.get('fixtures', [])
                if (_instant(item.get('utcDate')) or observed_at) >= cutoff
            }
            retained_fixtures.update({item['fixtureKey']: item for item in fixtures})
            snapshot = {
                'observations': list(by_identity.values()),
                'fixtures': list(retained_fixtures.values()),
                'coverage': metrics,
                'rollingCoverage': self._rolling_coverage(
                    list(retained_fixtures.values()),
                    list(by_identity.values()),
                ),
                'sources': {'espn-broadcasts': {'status': 'fresh', 'updatedAt': observed_at.isoformat()}},
                'refreshStatus': 'success',
            }
            snapshot = self.store.write(snapshot, updated_at=observed_at)
            return {'status': 'success', 'coverage': metrics, 'updatedAt': snapshot['updatedAt']}
        except Exception:
            previous['refreshStatus'] = 'stale' if previous.get('updatedAt') else 'unavailable'
            previous['sources'] = {
                **previous.get('sources', {}),
                'espn-broadcasts': {'status': 'stale'},
            }
            if previous.get('updatedAt'):
                try:
                    previous_at = _instant(previous['updatedAt']) or observed_at
                    age_seconds = max(0, (observed_at - previous_at).total_seconds())
                    self.store.write(
                        previous,
                        updated_at=previous_at,
                        age_seconds=age_seconds,
                    )
                except Exception:
                    pass
            return {
                'status': previous['refreshStatus'],
                'coverage': previous.get('coverage', {}),
                'updatedAt': previous.get('updatedAt'),
            }

    def apply_to_payload(self, payload):
        """Add cached listings and explicit coverage states without failing fixtures."""
        try:
            snapshot = self.store.read()
            if not snapshot:
                snapshot = {'observations': [], 'fixtures': [], 'coverage': {}, 'sources': {}}
            now = self.now().astimezone(timezone.utc)
            updated_at = _instant(snapshot.get('updatedAt'))
            stale = (
                snapshot.get('storageStatus') == 'stale'
                or snapshot.get('refreshStatus') == 'stale'
                or updated_at is None
                or now - updated_at > timedelta(seconds=OBSERVATION_TTL_SECONDS)
            )
            for fixture in payload.get('matches', []):
                fixture_id = fixture.get('canonicalFixtureId')
                rows = [
                    item for item in snapshot.get('observations', [])
                    if item.get('fixtureKey') == fixture_id
                ]
                current = list(fixture.get('whereToWatch') or [])
                current_stale = payload.get('state') == 'stale'
                region_states = {}
                for item in current:
                    if not isinstance(item, dict):
                        continue
                    region = str(item.get('region') or '').strip()
                    if not region:
                        continue
                    item_status = 'stale' if current_stale or item.get('status') == 'stale' else 'available'
                    item['status'] = item_status
                    region_states[region] = item_status
                seen = {
                    (item.get('sourceId'), item.get('id'), item.get('displayName'), item.get('region'), item.get('type'))
                    for item in current if isinstance(item, dict)
                }
                for row in rows:
                    if row.get('status') != 'available':
                        continue
                    row_stale = stale or row.get('status') == 'stale'
                    item = {
                        'id': row.get('id'),
                        'displayName': row.get('displayName'),
                        'type': row.get('type'),
                        'region': row.get('region'),
                        'officialUrl': row.get('officialUrl'),
                        'logoPath': row.get('logoPath'),
                        'source': row.get('source'),
                        'sourceId': row.get('sourceId'),
                        'observedAt': row.get('observedAt'),
                        'status': 'stale' if row_stale else 'available',
                    }
                    identity = (item['sourceId'], item['id'], item['displayName'], item['region'], item['type'])
                    if item['displayName'] and item['region'] and identity not in seen:
                        current.append(item)
                        seen.add(identity)
                fixture['whereToWatch'] = current
                streaming = [
                    item for item in (fixture.get('streaming') or [])
                    if isinstance(item, dict)
                ]
                streaming.extend(
                    item for item in current
                    if str(item.get('type') or '').upper() == 'STREAMING'
                )
                compatibility_streaming = {}
                for item in streaming:
                    identity = (
                        item.get('id'), item.get('displayName') or item.get('name'),
                        item.get('region'),
                    )
                    compatibility_streaming[identity] = item
                fixture['streaming'] = list(compatibility_streaming.values())

                known_regions = {
                    str(item.get('region') or '').strip()
                    for item in snapshot.get('observations', [])
                    if str(item.get('region') or '').strip()
                }
                known_regions.update(
                    str(row.get('region') or '').strip() for row in rows
                )
                for region in known_regions:
                    if region and region not in region_states:
                        region_states[region] = 'unverified'
                for row in rows:
                    region = str(row.get('region') or '').strip()
                    if not region:
                        continue
                    row_stale = stale or row.get('status') == 'stale'
                    candidate = 'stale' if row_stale else row.get('status')
                    if candidate not in {'available', 'confirmed_none', 'stale'}:
                        continue
                    if row.get('status') == 'confirmed_none' and not self._confirmation_is_eligible(row):
                        continue
                    existing = region_states.get(region)
                    priority = {'unverified': 0, 'confirmed_none': 1, 'stale': 2, 'available': 3}
                    if existing is None or priority.get(candidate, 0) > priority.get(existing, 0):
                        region_states[region] = candidate
                region_items = [
                    {'region': region, 'status': status}
                    for region, status in sorted(region_states.items())
                ]
                state_values = {item['status'] for item in region_items}
                overall = (
                    'available' if 'available' in state_values
                    else 'stale' if 'stale' in state_values
                    else 'confirmed_none' if region_items and state_values == {'confirmed_none'}
                    else 'unverified'
                )
                fixture['broadcastCoverage'] = {
                    'status': overall,
                    'regions': region_items,
                    'sourceUpdatedAt': snapshot.get('updatedAt'),
                }
            payload['broadcastSourceFreshness'] = {
                'status': 'stale' if stale and snapshot.get('updatedAt') else (
                    'fresh' if snapshot.get('updatedAt') else 'unverified'
                ),
                'updatedAt': snapshot.get('updatedAt'),
            }
            payload['broadcastCoverageReport'] = {
                'windowDays': ROLLING_WINDOW_DAYS,
                'thresholdPercent': 90,
                'competitions': snapshot.get('rollingCoverage', []),
                'regions': sorted({
                    item.get('region') for item in snapshot.get('observations', [])
                    if item.get('region') and item.get('region') != 'Region unknown'
                }),
            }
        except Exception:
            # Broadcast storage is an optional enrichment; it never delays or
            # changes the fixture provider outcome.
            for fixture in payload.get('matches', []):
                options = fixture.get('whereToWatch') or []
                state = 'stale' if payload.get('state') == 'stale' else 'available'
                regions = sorted({
                    str(item.get('region') or '').strip()
                    for item in options
                    if isinstance(item, dict) and str(item.get('region') or '').strip()
                })
                fixture['broadcastCoverage'] = {
                    'status': state if regions else 'unverified',
                    'regions': [{'region': region, 'status': state} for region in regions],
                    'sourceUpdatedAt': fixture.get('sourceUpdatedAt'),
                }
                for option in options:
                    if isinstance(option, dict):
                        option.setdefault('status', state)
            payload['broadcastSourceFreshness'] = {'status': 'unverified', 'updatedAt': None}
            payload['broadcastCoverageReport'] = {
                'windowDays': ROLLING_WINDOW_DAYS,
                'thresholdPercent': 90,
                'competitions': [],
                'regions': [],
            }
        return payload

    def _confirmation_is_eligible(self, row):
        """Require source-certified completeness before exposing a no-listing result."""
        source_id = row.get('sourceId')
        competition_id = str(row.get('competitionId') or '')
        region = str(row.get('region') or '').strip()
        if not source_id or not competition_id or not region:
            return False
        source = next((
            item for item in self.source_registry.refreshable_sources()
            if item.get('id') == source_id
        ), None)
        if source is None:
            return False
        feed = source.get('feed', {})
        return (
            feed.get('completeTerritoryCoverage') is True
            and str(feed.get('competitionId') or '') == competition_id
            and region in feed.get('completeTerritories', [])
        )

    def _rolling_coverage(self, fixtures, observations):
        grouped = {}
        regions = sorted({
            item.get('region') for item in observations
            if item.get('region') and item.get('region') != 'Region unknown'
        })
        for fixture in fixtures:
            competition_id = fixture.get('competitionId') or fixture.get('competition')
            if not competition_id:
                continue
            grouped.setdefault(str(competition_id), {
                'competitionId': str(competition_id),
                'competition': fixture.get('competition'),
                'fixturesObserved': set(),
                'regions': {},
            })['fixturesObserved'].add(fixture['fixtureKey'])
        for row in observations:
            competition_id = row.get('competitionId') or row.get('competition')
            if not competition_id or row.get('region') not in regions:
                continue
            group = grouped.get(str(competition_id))
            if group is None:
                continue
            group['regions'].setdefault(row['region'], set()).add(row['fixtureKey'])

        eligible_pairs = set()
        for source in self.source_registry.refreshable_sources():
            feed = source.get('feed', {})
            if feed.get('completeTerritoryCoverage') is not True:
                continue
            competition_id = str(feed.get('competitionId') or '')
            eligible_pairs.update(
                (competition_id, region)
                for region in feed.get('completeTerritories', [])
                if competition_id
            )
        reports = []
        for group in grouped.values():
            denominator = len(group['fixturesObserved'])
            for region in regions:
                listed = len(group['regions'].get(region, set()))
                percent = round(100 * listed / denominator, 1) if denominator else 0
                pair = (group['competitionId'], region)
                reports.append({
                    'competitionId': group['competitionId'],
                    'competition': group['competition'],
                    'region': region,
                    'fixturesObserved': denominator,
                    'verifiedFixtures': listed,
                    'verifiedPercent': percent,
                    'thresholdPercent': 90,
                    'sourceConfirmedComplete': pair in eligible_pairs,
                    'covered': pair in eligible_pairs and percent >= 90,
                })
        return reports

    def _normalize(self, matches, observed_at):
        sources = self.source_registry.refreshable_sources()
        source = next((item for item in sources if item.get('id') == 'espn-broadcasts'), None)
        if not source:
            return [], [], {
                'observed': 0, 'matched': 0, 'fixtureMatchRatePercent': None,
                'verifiedLinks': 0, 'regionKnown': 0, 'stale': 0,
                'unmatched': 0, 'ambiguous': 0, 'confirmedNone': 0,
                'confirmedCoveragePercent': 0, 'coverageThresholdPercent': 90,
            }
        observations = []
        fixtures = []
        for match in matches:
            if not isinstance(match, dict) or not match.get('canonicalFixtureId'):
                continue
            competition = match.get('competition') or {}
            fixtures.append({
                'fixtureKey': match['canonicalFixtureId'],
                'utcDate': match.get('utcDate'),
                'competition': competition.get('name'),
                'competitionId': competition.get('canonicalId'),
            })
            for listing in match.get('whereToWatch') or []:
                if not isinstance(listing, dict):
                    continue
                if listing.get('sourceId') not in {None, 'espn-broadcasts'}:
                    continue
                region = str(listing.get('region') or '').strip()
                name = str(listing.get('displayName') or '').strip()
                updated = listing.get('observedAt') or match.get('sourceUpdatedAt')
                if not name or not region or not _instant(updated):
                    continue
                observations.append({
                    'fixtureKey': match['canonicalFixtureId'],
                    'fixtureDate': match.get('utcDate'),
                    'competition': competition.get('name'),
                    'competitionId': competition.get('canonicalId'),
                    'displayName': name,
                    'id': listing.get('id'),
                    'type': listing.get('type'),
                    'region': region,
                    'officialUrl': listing.get('officialUrl'),
                    'logoPath': listing.get('logoPath'),
                    'sourceId': 'espn-broadcasts',
                    'source': source.get('provider'),
                    'observedAt': _instant(updated).isoformat().replace('+00:00', 'Z'),
                    'status': 'available',
                })
        return observations, fixtures, {
            'observed': len(observations),
            'matched': len(observations),
            'fixtureMatchRatePercent': 100 if observations else None,
            'verifiedLinks': sum(bool(item.get('officialUrl')) for item in observations),
            'regionKnown': len(observations),
            'stale': 0,
            'unmatched': 0,
            'ambiguous': 0,
            'fixtureCount': len(fixtures),
            # No currently active source declares per-region schedule completeness,
            # so zero-listing fixtures stay unverified and never enter this numerator.
            'confirmedNone': 0,
            'confirmedCoveragePercent': 0,
            'coverageThresholdPercent': 90,
        }
