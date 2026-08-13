import json
from pathlib import Path
import unittest
from urllib.parse import urlparse

from soccer_scanner.services.streaming import StreamingRegistry

REGISTRY_PATH = Path('soccer_scanner/data/streaming-services.json')


class StreamingRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = StreamingRegistry.from_file(REGISTRY_PATH)

    def test_resolves_a_known_service_by_exact_name(self):
        service = self.registry.resolve('Peacock')

        self.assertEqual(service['id'], 'peacock')
        self.assertEqual(service['displayName'], 'Peacock')

    def test_reports_registered_service_count(self):
        self.assertEqual(self.registry.service_count(), 8)

    def test_resolution_is_case_and_whitespace_insensitive(self):
        for raw in ('peacock', '  PEACOCK  ', 'Peacock Premium'):
            with self.subTest(raw=raw):
                self.assertEqual(self.registry.resolve(raw)['id'], 'peacock')

    def test_an_unknown_service_resolves_to_none(self):
        self.assertIsNone(self.registry.resolve('Some Unlicensed Stream'))
        self.assertIsNone(self.registry.resolve(''))
        self.assertIsNone(self.registry.resolve(None))

    def test_describe_preserves_a_supplied_region(self):
        described = self.registry.describe({
            'type': 'STREAMING', 'name': 'Peacock', 'region': 'US',
        })

        self.assertEqual(described['region'], 'US')
        self.assertTrue(described['regionKnown'])

    def test_describe_labels_an_absent_region_honestly(self):
        described = self.registry.describe({'type': 'STREAMING', 'name': 'DAZN'})

        # Never guess a region — say it is unknown.
        self.assertFalse(described['regionKnown'])
        self.assertEqual(described['region'], 'Region unknown')

    def test_an_unknown_service_still_describes_with_its_raw_name(self):
        described = self.registry.describe({
            'type': 'STREAMING', 'name': 'Local Broadcaster', 'region': 'BR',
        })

        self.assertIsNone(described['id'])
        self.assertEqual(described['displayName'], 'Local Broadcaster')
        self.assertIsNone(described['officialUrl'])
        self.assertEqual(described['region'], 'BR')

    def test_non_streaming_broadcasts_are_not_described(self):
        self.assertIsNone(self.registry.describe({'type': 'TV', 'name': 'Peacock'}))

    def test_removed_alias_falls_through_to_unknown_service(self):
        # CBS Sports Network was removed from paramount-plus aliases to preserve
        # the original name and prevent misrepresenting it as Paramount+.
        described = self.registry.describe({
            'type': 'STREAMING', 'name': 'CBS Sports Network', 'region': 'US',
        })

        self.assertIsNone(described['id'])
        self.assertEqual(described['displayName'], 'CBS Sports Network')
        self.assertIsNone(described['officialUrl'])
        self.assertEqual(described['region'], 'US')

    def test_describe_returns_source_key(self):
        described = self.registry.describe({
            'type': 'STREAMING', 'name': 'Peacock', 'region': 'US',
        })

        self.assertEqual(described['source'], 'espn')
        self.assertEqual(described['sourceId'], 'espn-broadcasts')

    def test_every_official_url_is_https_and_matches_a_declared_domain(self):
        for service in json.loads(REGISTRY_PATH.read_text())['services']:
            with self.subTest(service=service['id']):
                parsed = urlparse(service['officialUrl'])
                self.assertEqual(parsed.scheme, 'https')
                host = parsed.netloc.removeprefix('www.')
                self.assertTrue(
                    any(host == domain or host.endswith('.' + domain)
                        for domain in service['domains']),
                    f"{service['officialUrl']} is not on a declared domain",
                )

    def test_service_ids_and_aliases_are_unique(self):
        services = json.loads(REGISTRY_PATH.read_text())['services']
        ids = [service['id'] for service in services]
        self.assertEqual(len(ids), len(set(ids)))

        # Track all normalizations: displayNames and aliases are indexed together.
        seen = {}  # Maps normalized string to service id that claimed it

        for service in services:
            service_id = service['id']

            # displayName is indexed in the alias map
            display_normalized = service['displayName'].lower()
            self.assertNotIn(display_normalized, seen,
                f"displayName '{service['displayName']}' collides with existing mapping")
            seen[display_normalized] = service_id

            # Each alias is indexed in the alias map
            for alias in service['aliases']:
                normalized = alias.lower()
                # Allow an alias to match this service's own displayName (redundant but not harmful).
                if normalized != display_normalized:
                    self.assertNotIn(normalized, seen,
                        f"alias '{alias}' collides with existing mapping")
                seen[normalized] = service_id


if __name__ == '__main__':
    unittest.main()
