import unittest
from datetime import date
from unittest.mock import Mock

from soccer_scanner import create_app


def limiter_type():
    try:
        from soccer_scanner.services.rate_limit import MemoryRateLimiter
    except ModuleNotFoundError as error:
        raise AssertionError('rate limiter is not implemented') from error
    return MemoryRateLimiter


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class RateLimitTest(unittest.TestCase):
    def test_fixed_window_allows_limit_then_returns_retry_after(self):
        MemoryRateLimiter = limiter_type()
        clock = FakeClock()
        limiter = MemoryRateLimiter(limit=2, window_seconds=60, max_keys=10, clock=clock)

        self.assertTrue(limiter.check('fixture:127.0.0.1').allowed)
        self.assertTrue(limiter.check('fixture:127.0.0.1').allowed)
        denied = limiter.check('fixture:127.0.0.1')
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.retryAfterSeconds, 60)
        clock.advance(60)
        self.assertTrue(limiter.check('fixture:127.0.0.1').allowed)

    def test_fixture_api_returns_stable_rate_limit_envelope(self):
        app = create_app({
            'TESTING': True,
            'RATE_LIMIT_MAX_REQUESTS': 1,
            'RATE_LIMIT_WINDOW_SECONDS': 60,
        })
        app.extensions['fixture_service'].fixtures_for_date = Mock(return_value={
            'matches': [],
            'date': date(2026, 8, 3).isoformat(),
        })
        client = app.test_client()

        first = client.get('/api/matches-today?date=2026-08-03')
        denied = client.get('/api/matches-today?date=2026-08-03')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(denied.status_code, 429)
        self.assertEqual(denied.json['error']['code'], 'rate_limited')
        self.assertTrue(denied.json['error']['retryable'])
        self.assertEqual(denied.json['error']['retryAfterSeconds'], 60)
        self.assertEqual(denied.headers['Retry-After'], '60')
        self.assertIn('requestId', denied.json['error'])


class FakeRedis:
    """Minimal atomic-eval stand-in shared by several 'workers'."""

    def __init__(self):
        self.counters = {}
        self.expiries = {}
        self.eval_calls = 0

    def eval(self, script, numkeys, *args):
        self.eval_calls += 1
        key = args[0]
        window_ms = int(args[numkeys])
        current = self.counters.get(key, 0) + 1
        self.counters[key] = current
        if current == 1:
            self.expiries[key] = window_ms
        return [current, self.expiries.get(key, window_ms)]


class RedisRateLimiterTest(unittest.TestCase):
    def limiter(self, client, **kwargs):
        from soccer_scanner.services.rate_limit import RedisRateLimiter
        return RedisRateLimiter(client, namespace='test', **kwargs)

    def test_counter_is_shared_across_independent_workers(self):
        client = FakeRedis()
        worker_one = self.limiter(client)
        worker_two = self.limiter(client)

        # Two processes, one shared budget of three requests.
        self.assertTrue(worker_one.check('fixtures:1.2.3.4', limit=3, window_seconds=60).allowed)
        self.assertTrue(worker_two.check('fixtures:1.2.3.4', limit=3, window_seconds=60).allowed)
        self.assertTrue(worker_one.check('fixtures:1.2.3.4', limit=3, window_seconds=60).allowed)
        denied = worker_two.check('fixtures:1.2.3.4', limit=3, window_seconds=60)

        self.assertFalse(denied.allowed)
        self.assertEqual(denied.remaining, 0)
        self.assertGreaterEqual(denied.retryAfterSeconds, 1)

    def test_each_check_is_a_single_atomic_round_trip(self):
        client = FakeRedis()
        limiter = self.limiter(client)

        limiter.check('fixtures:1.2.3.4', limit=5, window_seconds=60)

        # A read-then-write sequence would race between workers.
        self.assertEqual(client.eval_calls, 1)

    def test_distinct_keys_and_policies_do_not_share_a_budget(self):
        client = FakeRedis()
        limiter = self.limiter(client)

        limiter.check('fixtures:1.2.3.4', limit=1, window_seconds=60)
        other_client = limiter.check('fixtures:5.6.7.8', limit=1, window_seconds=60)
        other_policy = limiter.check('search:1.2.3.4', limit=1, window_seconds=60)

        self.assertTrue(other_client.allowed)
        self.assertTrue(other_policy.allowed)

    def test_redis_failure_degrades_to_a_bounded_local_limiter(self):
        class BrokenRedis:
            def eval(self, *args, **kwargs):
                raise RuntimeError('redis unavailable')

        limiter = self.limiter(BrokenRedis())

        decision = limiter.check('fixtures:1.2.3.4', limit=2, window_seconds=60)

        # Availability is preserved, but the degradation must be observable.
        self.assertTrue(decision.allowed)
        self.assertTrue(limiter.degraded)


class RateLimitPolicyTest(unittest.TestCase):
    def test_distinct_policies_exist_for_each_protected_surface(self):
        from soccer_scanner.services.rate_limit import RATE_LIMIT_POLICIES

        for name in (
            'fixtures', 'calendar_range', 'search', 'team_analysis',
            'authentication', 'account_export', 'device_registration',
            'notifications', 'operations', 'default',
        ):
            self.assertIn(name, RATE_LIMIT_POLICIES, name)
            policy = RATE_LIMIT_POLICIES[name]
            self.assertGreater(policy.limit, 0, name)
            self.assertGreater(policy.window_seconds, 0, name)

    def test_expensive_surfaces_are_stricter_than_plain_fixture_reads(self):
        from soccer_scanner.services.rate_limit import RATE_LIMIT_POLICIES

        self.assertLess(
            RATE_LIMIT_POLICIES['team_analysis'].limit,
            RATE_LIMIT_POLICIES['fixtures'].limit,
        )
        self.assertLess(
            RATE_LIMIT_POLICIES['authentication'].limit,
            RATE_LIMIT_POLICIES['fixtures'].limit,
        )


class RateLimitHeadersTest(unittest.TestCase):
    def test_successful_responses_advertise_the_remaining_budget(self):
        app = create_app({
            'TESTING': True,
            'RATE_LIMIT_MAX_REQUESTS': 5,
            'RATE_LIMIT_WINDOW_SECONDS': 60,
        })
        app.extensions['fixture_service'].fixtures_for_date = Mock(return_value={
            'matches': [],
            'date': date(2026, 8, 3).isoformat(),
        })

        response = app.test_client().get('/api/matches-today?date=2026-08-03')

        self.assertEqual(response.status_code, 200)
        self.assertIn('RateLimit-Limit', response.headers)
        self.assertIn('RateLimit-Remaining', response.headers)
        self.assertIn('RateLimit-Reset', response.headers)


class ReadinessAndOperationsExposureTest(unittest.TestCase):
    def test_readiness_reports_whether_rate_limiting_is_shared(self):
        app = create_app({'TESTING': True})

        payload = app.test_client().get('/health/ready').json

        self.assertIn('rateLimit', payload)
        self.assertIn('shared', payload['rateLimit'])
        self.assertIn('status', payload['rateLimit'])

    def test_metrics_requires_an_operations_token_when_one_is_configured(self):
        app = create_app({'TESTING': True, 'OPS_ADMIN_TOKEN': 'secret-token'})
        client = app.test_client()

        unauthorized = client.get('/health/metrics')
        wrong = client.get('/health/metrics', headers={'X-Ops-Token': 'nope'})
        authorized = client.get('/health/metrics', headers={'X-Ops-Token': 'secret-token'})

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(authorized.status_code, 200)

    def test_metrics_stays_open_when_no_token_is_configured(self):
        app = create_app({'TESTING': True, 'OPS_ADMIN_TOKEN': None})

        self.assertEqual(app.test_client().get('/health/metrics').status_code, 200)


if __name__ == '__main__':
    unittest.main()
