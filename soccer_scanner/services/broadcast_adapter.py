"""Safe matching for official fixture-level broadcast listings."""

from urllib.parse import urlparse

from soccer_scanner.services.broadcast_sources import match_source_listing


def _host_matches(host, domains):
    host = str(host or '').lower().removeprefix('www.')
    return any(host == domain or host.endswith('.' + domain) for domain in domains)


class OfficialBroadcastAdapter:
    """Match already-fetched official listings without inventing coverage."""

    def __init__(self, source_registry):
        self.source_registry = source_registry

    def observe(self, listings, matches):
        """Normalize a batch and return records plus explicit coverage metrics."""
        records = []
        metrics = {
            'observed': 0,
            'matched': 0,
            'verifiedLinks': 0,
            'regionKnown': 0,
            'stale': 0,
            'unmatched': 0,
            'ambiguous': 0,
        }
        for listing in listings or []:
            metrics['observed'] += 1
            record = self.match_listing(listing, matches)
            if record is None:
                metrics['unmatched'] += 1
                continue
            records.append(record)
            if record.get('fixtureKey'):
                metrics['matched'] += 1
            if record.get('officialUrl'):
                metrics['verifiedLinks'] += 1
            if record.get('regionKnown'):
                metrics['regionKnown'] += 1
            if record.get('status') == 'ambiguous':
                metrics['ambiguous'] += 1
            if record.get('status') == 'unmatched':
                metrics['unmatched'] += 1
        return {'records': records, 'metrics': metrics}

    def match_listing(self, listing, matches):
        if not isinstance(listing, dict):
            return None
        source_id = listing.get('sourceId')
        source = self.source_registry.get(source_id)
        if source is None:
            return None

        candidates = [
            match for match in (matches or [])
            if match_source_listing(listing, match)
        ]
        base = {
            'fixtureKey': candidates[0].get('canonicalFixtureId') if len(candidates) == 1 else None,
            'displayName': str(listing.get('displayName') or '').strip() or 'Official broadcast',
            'region': str(listing.get('region') or 'Region unknown').strip(),
            'regionKnown': bool(str(listing.get('region') or '').strip()),
            'officialUrl': None,
            'source': source.get('provider'),
            'sourceId': source_id,
            'observedAt': listing.get('observedAt'),
            'status': 'unlinked',
        }
        if len(candidates) > 1:
            base['status'] = 'ambiguous'
            base['fixtureKey'] = None
            return base
        if not candidates:
            base['status'] = 'unmatched'
            return base

        parsed = urlparse(str(listing.get('officialUrl') or ''))
        domains = source.get('allowedDomains') or []
        if parsed.scheme == 'https' and parsed.netloc and _host_matches(parsed.hostname, domains):
            base['officialUrl'] = listing['officialUrl']
            base['status'] = 'verified'
        return base
