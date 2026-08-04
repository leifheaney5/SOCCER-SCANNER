import unittest

from soccer_scanner.domain.capabilities import (
    Capability,
    CapabilityStatus,
    build_capability_manifest,
)


class ProviderCapabilityTest(unittest.TestCase):
    def test_all_provider_gated_capabilities_have_typed_outcomes(self):
        manifest = build_capability_manifest(football_data_configured=False)

        self.assertEqual(set(manifest), {capability.value for capability in Capability})
        self.assertEqual(manifest['events']['status'], CapabilityStatus.NOT_SUPPORTED.value)
        self.assertEqual(manifest['lineups']['status'], CapabilityStatus.NOT_SUPPORTED.value)
        self.assertEqual(manifest['statistics']['status'], CapabilityStatus.NOT_SUPPORTED.value)
        self.assertEqual(manifest['broadcasts']['status'], CapabilityStatus.SUPPORTED.value)
        self.assertEqual(manifest['broadcasts']['provider'], 'espn')
        self.assertEqual(manifest['notifications']['status'], CapabilityStatus.NOT_SUPPORTED.value)
        self.assertEqual(manifest['squads']['status'], CapabilityStatus.UNAVAILABLE.value)
        self.assertEqual(manifest['standings']['status'], CapabilityStatus.UNAVAILABLE.value)
        self.assertTrue(all('data' not in result for result in manifest.values()))

    def test_configured_football_data_unlocks_only_declared_capabilities(self):
        manifest = build_capability_manifest(football_data_configured=True)

        self.assertEqual(manifest['squads']['status'], CapabilityStatus.SUPPORTED.value)
        self.assertEqual(manifest['standings']['status'], CapabilityStatus.SUPPORTED.value)
        self.assertEqual(manifest['squads']['provider'], 'football-data')
        self.assertEqual(manifest['events']['status'], CapabilityStatus.NOT_SUPPORTED.value)


if __name__ == '__main__':
    unittest.main()
