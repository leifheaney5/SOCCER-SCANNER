import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from soccer_scanner.observability import MetricsRegistry


def cache_types():
    try:
        from soccer_scanner.services.cache_backend import (
            MemoryCacheBackend,
            RedisCacheBackend,
            ResilientCacheBackend,
        )
    except ModuleNotFoundError as error:
        raise AssertionError('shared cache boundary is not implemented') from error
    return MemoryCacheBackend, RedisCacheBackend, ResilientCacheBackend


class FakeClock:
    def __init__(self, initial=1_000.0):
        self.value = initial

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def set(self, key, value, nx=False, ex=None):
        with self.lock:
            if nx and key in self.data:
                return False
            self.data[key] = value.encode() if isinstance(value, str) else value
            return True

    def setex(self, key, seconds, value):
        return self.set(key, value)

    def eval(self, script, number_of_keys, key, token):
        with self.lock:
            current = self.data.get(key)
            encoded_token = token.encode() if isinstance(token, str) else token
            if current == encoded_token:
                del self.data[key]
                return 1
            return 0

    def ping(self):
        return True


class FailingRedis:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ConnectionError('redis unavailable')
        return fail


class MemoryCacheBackendTest(unittest.TestCase):
    def setUp(self):
        MemoryCacheBackend, _, _ = cache_types()
        self.clock = FakeClock()
        self.metrics = MetricsRegistry()
        self.cache = MemoryCacheBackend(
            default_ttl_seconds=10,
            default_stale_ttl_seconds=20,
            max_entries=2,
            max_key_length=32,
            max_value_bytes=128,
            clock=self.clock,
            metrics=self.metrics,
        )

    def test_reports_fresh_stale_and_miss(self):
        self.cache.set('fixtures', {'matches': [1]})

        fresh = self.cache.get('fixtures', allow_stale=True)
        self.clock.advance(11)
        stale = self.cache.get('fixtures', allow_stale=True)
        hidden_stale = self.cache.get('fixtures', allow_stale=False)
        self.clock.advance(20)
        missing = self.cache.get('fixtures', allow_stale=True)

        self.assertEqual((fresh.status, fresh.value), ('fresh', {'matches': [1]}))
        self.assertEqual(stale.status, 'stale')
        self.assertEqual(hidden_stale.status, 'miss')
        self.assertEqual(missing.status, 'miss')

    def test_evicts_lru_and_rejects_unbounded_inputs(self):
        self.cache.set('first', 1)
        self.cache.set('second', 2)
        self.cache.get('first')
        self.cache.set('third', 3)

        self.assertEqual(self.cache.get('second').status, 'miss')
        self.assertEqual(self.cache.get('first').value, 1)
        with self.assertRaises(ValueError):
            self.cache.set('x' * 33, 1)
        with self.assertRaises(ValueError):
            self.cache.set('large', {'value': 'x' * 200})
        self.assertEqual(self.metrics.snapshot()['counters']['cache.eviction'], 1)

    def test_concurrent_identical_loads_call_loader_once(self):
        calls = 0
        calls_lock = threading.Lock()

        def loader():
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.03)
            return {'matches': [1]}

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(
                lambda _: self.cache.get_or_load('same-key', loader),
                range(8),
            ))

        self.assertEqual(calls, 1)
        self.assertTrue(all(result.value == {'matches': [1]} for result in results))
        self.assertEqual(sum(result.status == 'filled' for result in results), 1)

    def test_loader_failure_is_not_cached(self):
        def loader():
            raise RuntimeError('provider unavailable')

        with self.assertRaises(RuntimeError):
            self.cache.get_or_load('failure', loader)

        self.assertEqual(self.cache.get('failure').status, 'miss')


class RedisCacheBackendTest(unittest.TestCase):
    def test_two_backends_share_data_and_distributed_single_flight(self):
        _, RedisCacheBackend, _ = cache_types()
        redis = FakeRedis()
        first = RedisCacheBackend(
            redis,
            namespace='test',
            default_ttl_seconds=10,
            default_stale_ttl_seconds=20,
            lock_wait_seconds=1,
            lock_poll_seconds=0.005,
        )
        second = RedisCacheBackend(
            redis,
            namespace='test',
            default_ttl_seconds=10,
            default_stale_ttl_seconds=20,
            lock_wait_seconds=1,
            lock_poll_seconds=0.005,
        )
        calls = 0
        calls_lock = threading.Lock()

        def loader():
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.03)
            return {'matches': [1]}

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(first.get_or_load, 'shared-key', loader),
                executor.submit(second.get_or_load, 'shared-key', loader),
            ]
            results = [future.result() for future in futures]

        self.assertEqual(calls, 1)
        self.assertEqual([result.value for result in results], [
            {'matches': [1]},
            {'matches': [1]},
        ])
        self.assertEqual(second.health()['status'], 'ready')

    def test_unavailable_redis_falls_back_without_duplicate_loader(self):
        MemoryCacheBackend, RedisCacheBackend, ResilientCacheBackend = cache_types()
        primary = RedisCacheBackend(FailingRedis(), namespace='test')
        fallback = MemoryCacheBackend(default_ttl_seconds=10)
        cache = ResilientCacheBackend(primary, fallback)
        calls = 0

        def loader():
            nonlocal calls
            calls += 1
            return {'matches': [1]}

        first = cache.get_or_load('fixtures', loader)
        second = cache.get_or_load('fixtures', loader)

        self.assertEqual(calls, 1)
        self.assertEqual(first.value, {'matches': [1]})
        self.assertEqual(second.status, 'fresh')
        self.assertEqual(cache.health(), {
            'backend': 'redis',
            'shared': False,
            'status': 'degraded',
            'fallback': 'memory',
        })


if __name__ == '__main__':
    unittest.main()
