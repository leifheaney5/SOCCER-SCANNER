import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

import requests


def transport_types():
    try:
        from soccer_scanner.providers.http import (
            ProviderHttpClient,
            ProviderRequestError,
            RequestBudget,
        )
    except ModuleNotFoundError as error:
        raise AssertionError('provider HTTP boundary is not implemented') from error
    return ProviderHttpClient, ProviderRequestError, RequestBudget


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, raw_body=None):
        self.status_code = status
        self.headers = {'Content-Type': 'application/json', **(headers or {})}
        self.content = raw_body if raw_body is not None else json.dumps(
            payload if payload is not None else {},
        ).encode('utf-8')

    def iter_content(self, chunk_size=65_536):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]

    def close(self):
        return None


class ProviderHttpClientTest(unittest.TestCase):
    def client(self, effects, **overrides):
        ProviderHttpClient, _, _ = transport_types()
        session = Mock()
        session.get.side_effect = effects
        sleep = Mock()
        client = ProviderHttpClient(
            'https://provider.example/v1',
            session=session,
            timeout=(1, 2),
            max_retries=2,
            max_json_bytes=128,
            retry_after_max=5,
            sleep=sleep,
            random_source=lambda: 0,
            **overrides,
        )
        return client, session, sleep

    def test_timeout_is_retried_and_observed(self):
        client, session, sleep = self.client([
            requests.Timeout('slow'),
            FakeResponse(payload={'events': []}),
        ])

        payload, observation = client.get_json('scoreboard')

        self.assertEqual(payload, {'events': []})
        self.assertEqual(observation.requestCount, 2)
        self.assertEqual(observation.timeoutCount, 1)
        self.assertEqual(observation.rateLimitCount, 0)
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once()

    def test_rate_limit_honors_bounded_retry_after(self):
        client, _, sleep = self.client([
            FakeResponse(status=429, headers={'Retry-After': '120'}),
            FakeResponse(payload={'matches': []}),
        ])

        _, observation = client.get_json('matches')

        self.assertEqual(observation.rateLimitCount, 1)
        sleep.assert_called_once_with(5)

    def test_rate_limit_honors_http_date_retry_after(self):
        client, _, sleep = self.client([
            FakeResponse(
                status=429,
                headers={'Retry-After': 'Mon, 03 Aug 2026 20:00:10 GMT'},
            ),
            FakeResponse(payload={'matches': []}),
        ], wall_clock=lambda: datetime(2026, 8, 3, 20, 0, tzinfo=timezone.utc))

        client.get_json('matches')

        sleep.assert_called_once_with(5)

    def test_non_transient_four_hundred_is_not_retried(self):
        client, session, sleep = self.client([FakeResponse(status=404)])
        _, ProviderRequestError, _ = transport_types()

        with self.assertRaises(ProviderRequestError) as raised:
            client.get_json('missing')

        self.assertEqual(raised.exception.category, 'http_4xx')
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(session.get.call_count, 1)
        sleep.assert_not_called()

    def test_invalid_content_type_is_rejected(self):
        client, _, _ = self.client([
            FakeResponse(headers={'Content-Type': 'text/html'}, raw_body=b'<html></html>'),
        ])
        _, ProviderRequestError, _ = transport_types()

        with self.assertRaises(ProviderRequestError) as raised:
            client.get_json('scoreboard')

        self.assertEqual(raised.exception.category, 'invalid_content_type')

    def test_oversized_content_length_is_rejected(self):
        client, _, _ = self.client([
            FakeResponse(headers={'Content-Length': '9999'}),
        ])
        _, ProviderRequestError, _ = transport_types()

        with self.assertRaises(ProviderRequestError) as raised:
            client.get_json('scoreboard')

        self.assertEqual(raised.exception.category, 'response_too_large')

    def test_response_body_is_streamed_under_the_size_limit(self):
        client, session, _ = self.client([
            FakeResponse(raw_body=b'{' + (b'x' * 256) + b'}'),
        ])
        _, ProviderRequestError, _ = transport_types()

        with self.assertRaises(ProviderRequestError) as raised:
            client.get_json('scoreboard')

        self.assertEqual(raised.exception.category, 'response_too_large')
        self.assertTrue(session.get.call_args.kwargs['stream'])

    def test_malformed_json_is_rejected_without_body_leakage(self):
        client, _, _ = self.client([FakeResponse(raw_body=b'{not json')])
        _, ProviderRequestError, _ = transport_types()

        with self.assertRaises(ProviderRequestError) as raised:
            client.get_json('scoreboard')

        self.assertEqual(raised.exception.category, 'invalid_json')
        self.assertNotIn('not json', str(raised.exception))

    def test_exhausted_budget_prevents_an_outbound_request(self):
        client, session, _ = self.client([])
        _, ProviderRequestError, RequestBudget = transport_types()
        budget = RequestBudget(total_seconds=0)

        with self.assertRaises(ProviderRequestError) as raised:
            client.get_json('scoreboard', budget=budget)

        self.assertEqual(raised.exception.category, 'budget_exhausted')
        session.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
