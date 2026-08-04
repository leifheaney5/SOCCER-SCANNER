import unittest

from soccer_scanner.build_info import load_build_info


class BuildInfoTest(unittest.TestCase):
    def test_development_uses_repository_version_when_sha_is_unknown(self):
        build = load_build_info({})

        self.assertEqual(build.as_public_dict(), {
            'version': '1.0.0',
            'commitSha': 'unknown',
            'buildTimestamp': None,
            'environment': 'development',
            'assetVersion': '1.0.0',
        })

    def test_explicit_build_values_take_precedence_over_railway_values(self):
        build = load_build_info({
            'APP_VERSION': '2.1.0',
            'APP_ENVIRONMENT': 'staging',
            'RAILWAY_ENVIRONMENT_NAME': 'production',
            'GIT_COMMIT_SHA': 'ABCDEF0123456789ABCDEF0123456789ABCDEF01',
            'RAILWAY_GIT_COMMIT_SHA': '1111111111111111111111111111111111111111',
            'BUILD_TIMESTAMP': '2026-08-03T20:00:00Z',
            'RAILWAY_DEPLOYMENT_CREATED_AT': '2026-08-03T19:00:00Z',
        })

        self.assertEqual(build.version, '2.1.0')
        self.assertEqual(build.environment, 'staging')
        self.assertEqual(
            build.commit_sha,
            'abcdef0123456789abcdef0123456789abcdef01',
        )
        self.assertEqual(build.asset_version, 'abcdef012345')
        self.assertEqual(build.build_timestamp, '2026-08-03T20:00:00Z')

    def test_railway_production_requires_a_commit_sha(self):
        with self.assertRaisesRegex(RuntimeError, 'commit SHA'):
            load_build_info({'RAILWAY_ENVIRONMENT_NAME': 'production'})

    def test_malformed_sha_is_rejected_in_every_environment(self):
        with self.assertRaisesRegex(RuntimeError, 'malformed'):
            load_build_info({
                'APP_ENVIRONMENT': 'test',
                'GIT_COMMIT_SHA': 'not-a-revision',
            })


if __name__ == '__main__':
    unittest.main()
