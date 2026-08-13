"""Apply verified official broadcast observations to fixture records."""

from soccer_scanner.services.broadcast_adapter import OfficialBroadcastAdapter


class BroadcastCoverageService:
    def __init__(self, source_registry):
        self.adapter = OfficialBroadcastAdapter(source_registry)

    def enrich(self, matches, listings):
        """Return copied fixtures, verified links, and observation metrics."""
        fixtures = [{**match, 'streaming': list(match.get('streaming') or [])}
                    for match in (matches or [])]
        observed = self.adapter.observe(listings, fixtures)
        by_id = {match.get('canonicalFixtureId'): match for match in fixtures}
        for record in observed['records']:
            if record.get('status') != 'verified' or not record.get('fixtureKey'):
                continue
            fixture = by_id.get(record['fixtureKey'])
            if fixture is None:
                continue
            streaming = fixture['streaming']
            identity = (record['sourceId'], record['displayName'], record['region'])
            if not any((item.get('sourceId'), item.get('displayName'), item.get('region')) == identity
                       for item in streaming):
                streaming.append({
                    'id': None,
                    'displayName': record['displayName'],
                    'officialUrl': record['officialUrl'],
                    'region': record['region'],
                    'regionKnown': record['regionKnown'],
                    'source': record['source'],
                    'sourceId': record['sourceId'],
                    'observedAt': record['observedAt'],
                })
        return {'matches': fixtures, 'records': observed['records'], 'metrics': observed['metrics']}
