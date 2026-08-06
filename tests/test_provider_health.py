import json
import unittest

from soccer_scanner.services.provider_health import ProviderHealthRegistry


class FakeClock:
    def __init__(self, value=1_770_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class ProviderHealthRegistryTest(unittest.TestCase):
    def test_reports_unknown_before_any_observation(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        snapshot = registry.snapshot()

        self.assertEqual(snapshot['status'], 'unknown')
        self.assertEqual(snapshot['providers'], [])
        self.assertIsNone(snapshot['lastSuccessAt'])

    def test_all_healthy_providers_report_ok(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'ok')

        self.assertEqual(registry.snapshot()['status'], 'ok')

    def test_one_failing_provider_degrades_rather_than_fails(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable', detail='connect timeout')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'degraded')

    def test_every_provider_failing_reports_unavailable(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'unavailable')
        registry.record('football-data', 'unavailable')

        self.assertEqual(registry.snapshot()['status'], 'unavailable')

    def test_disabled_providers_do_not_count_against_health(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        self.assertEqual(registry.snapshot()['status'], 'ok')

    def test_last_success_is_retained_after_a_later_failure(self):
        clock = FakeClock()
        registry = ProviderHealthRegistry(clock=clock)

        registry.record('espn', 'ok')
        clock.advance(120)
        registry.record('espn', 'unavailable', detail='HTTP 503')

        provider = registry.snapshot()['providers'][0]
        self.assertEqual(provider['status'], 'unavailable')
        self.assertEqual(provider['detail'], 'HTTP 503')
        # The success timestamp must survive so staleness is measurable.
        self.assertIsNotNone(provider['lastSuccessAt'])
        self.assertNotEqual(provider['lastSuccessAt'], provider['lastObservedAt'])

    def test_timestamps_are_iso8601_utc(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')

        provider = registry.snapshot()['providers'][0]
        self.assertTrue(provider['lastSuccessAt'].endswith('+00:00'))
        self.assertIn('T', provider['lastSuccessAt'])

    def test_a_lone_configured_provider_is_flagged(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'disabled')

        # One usable provider means no fallback exists.
        self.assertTrue(registry.snapshot()['singleProvider'])

    def test_two_usable_providers_are_not_flagged_as_single(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable')

        self.assertFalse(registry.snapshot()['singleProvider'])

    def test_providers_are_reported_in_a_stable_order(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        registry.record('zebra', 'ok')
        registry.record('alpha', 'ok')

        names = [item['name'] for item in registry.snapshot()['providers']]
        self.assertEqual(names, ['alpha', 'zebra'])

    def test_unknown_status_values_are_rejected(self):
        registry = ProviderHealthRegistry(clock=FakeClock())

        with self.assertRaises(ValueError):
            registry.record('espn', 'exploded')


class FakeRedisHash:
    """Minimal hash + expiry stand-in shared by several 'workers'.

    ``eval`` is a faithful-enough stand-in for
    ``RedisProviderHealthRegistry._RECORD_SCRIPT``: it performs the same
    read-merge-write the real Lua script performs server-side (carry
    ``lastSuccessAt`` forward unless the new status is ``ok``, then overwrite
    the field and refresh the key's TTL), so tests that go through
    ``record()`` exercise the same merge semantics production does, not just
    a bare ``hset``.
    """

    def __init__(self):
        self.hashes = {}
        self.expiries = {}

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def expire(self, key, seconds):
        self.expiries[key] = seconds
        return True

    def eval(self, script, numkeys, key, field, status, detail_json, now, ttl):
        # Security note: this `eval` is the redis-py client method that sends
        # a Redis `EVAL <script> ...` command to a server -- it never invokes
        # Python's `eval()` builtin or executes arbitrary Python. `script` is
        # accepted (matching the real client's signature) but intentionally
        # ignored here: the fake reimplements the fixed Lua literal's
        # read-merge-write semantics directly in Python instead of running Lua.
        existing_raw = self.hashes.get(key, {}).get(field)
        last_success = None
        if existing_raw:
            try:
                existing = json.loads(existing_raw)
            except (TypeError, ValueError):
                existing = None
            if isinstance(existing, dict):
                last_success = existing.get('lastSuccessAt')
        now = float(now)
        if status == 'ok':
            last_success = now
        payload = {
            'status': status,
            'detail': json.loads(detail_json),
            'lastObservedAt': now,
            'lastSuccessAt': last_success,
        }
        self.hashes.setdefault(key, {})[field] = json.dumps(payload)
        self.expiries[key] = int(ttl)
        return 1


class RedisProviderHealthRegistryTest(unittest.TestCase):
    def registry(self, client, **kwargs):
        from soccer_scanner.services.provider_health import RedisProviderHealthRegistry
        return RedisProviderHealthRegistry(client, namespace='test', **kwargs)

    def test_state_written_by_one_worker_is_visible_to_another(self):
        client = FakeRedisHash()
        worker_one = self.registry(client)
        worker_two = self.registry(client)

        worker_one.record('espn', 'ok')

        # This is the whole point: a second gunicorn worker must not report
        # 'unknown' just because it did not personally serve the request.
        snapshot = worker_two.snapshot()
        self.assertEqual(snapshot['status'], 'ok')
        self.assertEqual([item['name'] for item in snapshot['providers']], ['espn'])

    def test_aggregate_rules_match_the_in_memory_registry(self):
        client = FakeRedisHash()
        registry = self.registry(client)

        registry.record('espn', 'ok')
        registry.record('football-data', 'unavailable', detail='timeout')

        snapshot = registry.snapshot()
        self.assertEqual(snapshot['status'], 'degraded')
        self.assertFalse(snapshot['singleProvider'])
        recorded = {item['name']: item for item in snapshot['providers']}
        self.assertEqual(recorded['football-data']['detail'], 'timeout')

    def test_last_success_survives_a_later_failure_across_workers(self):
        client = FakeRedisHash()
        clock = FakeClock()
        writer = self.registry(client, clock=clock)

        writer.record('espn', 'ok')
        clock.advance(120)
        writer.record('espn', 'unavailable', detail='HTTP 503')

        # A second worker shares real wall-clock time with the first in
        # production, so the reader gets the same fake clock here too --
        # this test is about lastSuccessAt survival, not TTL ageing.
        provider = self.registry(client, clock=clock).snapshot()['providers'][0]
        self.assertEqual(provider['status'], 'unavailable')
        self.assertIsNotNone(provider['lastSuccessAt'])
        self.assertNotEqual(provider['lastSuccessAt'], provider['lastObservedAt'])

    def test_an_entry_is_given_a_bounded_lifetime(self):
        client = FakeRedisHash()
        self.registry(client, ttl_seconds=900).record('espn', 'ok')

        # Without an expiry a dead provider's last state would persist forever.
        self.assertTrue(any(value == 900 for value in client.expiries.values()))

    def test_a_stale_entry_ages_out_even_while_a_neighbour_keeps_recording(self):
        client = FakeRedisHash()
        clock = FakeClock()
        registry = self.registry(client, ttl_seconds=900, clock=clock)

        registry.record('espn', 'ok')
        clock.advance(901)
        # football-data recording refreshes the hash's own key-level TTL,
        # which is exactly the trap: that must not keep espn's now-stale
        # entry alive just because some other provider is still traffic-bearing.
        registry.record('football-data', 'ok')

        names = [item['name'] for item in registry.snapshot()['providers']]
        self.assertNotIn('espn', names)
        self.assertIn('football-data', names)

    def test_redis_failure_degrades_to_the_in_memory_registry(self):
        class BrokenRedis:
            def hset(self, *args, **kwargs):
                raise RuntimeError('redis down')

            def hgetall(self, *args, **kwargs):
                raise RuntimeError('redis down')

            def expire(self, *args, **kwargs):
                raise RuntimeError('redis down')

            def eval(self, *args, **kwargs):
                raise RuntimeError('redis down')

        registry = self.registry(BrokenRedis())

        registry.record('espn', 'ok')

        # Availability is preserved and the degradation is observable.
        self.assertEqual(registry.snapshot()['status'], 'ok')
        self.assertTrue(registry.degraded)

    def test_a_corrupt_entry_is_ignored_rather_than_raising(self):
        client = FakeRedisHash()
        client.hset('test:provider-health', 'espn', 'not-json')
        registry = self.registry(client)

        # A malformed entry must not take down the health endpoint.
        self.assertEqual(registry.snapshot()['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
