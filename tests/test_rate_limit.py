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


if __name__ == '__main__':
    unittest.main()
