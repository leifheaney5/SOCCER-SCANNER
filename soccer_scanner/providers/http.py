"""Bounded HTTP/JSON transport shared by provider adapters."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import random
import time
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter


@dataclass(frozen=True)
class HttpObservation:
    requestCount: int
    timeoutCount: int
    rateLimitCount: int
    durationMs: int


class ProviderRequestError(RuntimeError):
    def __init__(
        self,
        category,
        *,
        retryable=False,
        status_code=None,
        retry_after_seconds=None,
        observation=None,
    ):
        super().__init__(f'Provider request failed ({category}).')
        self.category = category
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.observation = observation


class RequestBudget:
    def __init__(self, total_seconds, *, clock=time.monotonic):
        self.total_seconds = max(0.0, float(total_seconds))
        self._clock = clock
        self._started = clock()

    def remaining(self):
        return max(0.0, self.total_seconds - (self._clock() - self._started))


class ProviderHttpClient:
    def __init__(
        self,
        base_url,
        *,
        session=None,
        timeout=(3.05, 8),
        max_retries=2,
        max_json_bytes=1_000_000,
        retry_after_max=30,
        pool_connections=8,
        pool_maxsize=16,
        sleep=time.sleep,
        clock=time.monotonic,
        wall_clock=None,
        random_source=random.random,
    ):
        self.base_url = base_url.rstrip('/') + '/'
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.max_json_bytes = max(1, int(max_json_bytes))
        self.retry_after_max = max(0, int(retry_after_max))
        self.sleep = sleep
        self.clock = clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.random_source = random_source
        self.session = session or requests.Session()
        if session is None:
            adapter = HTTPAdapter(
                pool_connections=pool_connections,
                pool_maxsize=pool_maxsize,
                max_retries=0,
                pool_block=True,
            )
            self.session.mount('https://', adapter)
            self.session.mount('http://', adapter)
        self.session.headers.update({'Accept': 'application/json'})

    def get_json(self, path, *, params=None, budget=None):
        started = self.clock()
        request_count = 0
        timeout_count = 0
        rate_limit_count = 0
        last_retry_after = None

        for attempt in range(self.max_retries + 1):
            if budget is not None and budget.remaining() <= 0:
                raise self._error(
                    'budget_exhausted',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                )

            request_count += 1
            try:
                response = self.session.get(
                    urljoin(self.base_url, str(path).lstrip('/')),
                    params=params,
                    timeout=self._bounded_timeout(budget),
                    stream=True,
                )
            except requests.Timeout:
                timeout_count += 1
                if attempt < self.max_retries:
                    self._wait_before_retry(attempt, budget)
                    continue
                raise self._error(
                    'timeout',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                    retryable=True,
                )
            except requests.ConnectionError:
                if attempt < self.max_retries:
                    self._wait_before_retry(attempt, budget)
                    continue
                raise self._error(
                    'connection',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                    retryable=True,
                )
            except requests.RequestException:
                raise self._error(
                    'request_error',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                )

            if response.status_code == 429:
                rate_limit_count += 1
                last_retry_after = self._retry_after(response)
                if attempt < self.max_retries:
                    self._close_response(response)
                    self._sleep_with_budget(last_retry_after, budget)
                    continue
                self._close_response(response)
                raise self._error(
                    'rate_limited',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                    retryable=True,
                    status_code=429,
                    retry_after_seconds=last_retry_after,
                )

            if 500 <= response.status_code <= 599:
                if attempt < self.max_retries:
                    self._close_response(response)
                    self._wait_before_retry(attempt, budget)
                    continue
                self._close_response(response)
                raise self._error(
                    'http_5xx',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                    retryable=True,
                    status_code=response.status_code,
                )

            if response.status_code >= 400:
                self._close_response(response)
                raise self._error(
                    'http_4xx',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                    status_code=response.status_code,
                )

            try:
                body = self._read_response(
                    response, started, request_count, timeout_count, rate_limit_count,
                )
            finally:
                self._close_response(response)
            try:
                payload = json.loads(body.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise self._error(
                    'invalid_json',
                    started,
                    request_count,
                    timeout_count,
                    rate_limit_count,
                )
            observation = HttpObservation(
                requestCount=request_count,
                timeoutCount=timeout_count,
                rateLimitCount=rate_limit_count,
                durationMs=max(0, round((self.clock() - started) * 1000)),
            )
            return payload, observation

        raise self._error(
            'request_error',
            started,
            request_count,
            timeout_count,
            rate_limit_count,
            retry_after_seconds=last_retry_after,
        )

    def _bounded_timeout(self, budget):
        if budget is None:
            return self.timeout
        remaining = budget.remaining()
        return tuple(max(0.001, min(float(value), remaining)) for value in self.timeout)

    def _retry_after(self, response):
        raw_value = response.headers.get('Retry-After', '')
        try:
            seconds = max(0, int(raw_value))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(raw_value))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = max(0, math.ceil((retry_at - self.wall_clock()).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                seconds = 1
        return min(seconds, self.retry_after_max)

    def _wait_before_retry(self, attempt, budget):
        delay = min(
            self.retry_after_max,
            (0.25 * (2 ** attempt)) + (0.1 * self.random_source()),
        )
        self._sleep_with_budget(delay, budget)

    def _sleep_with_budget(self, delay, budget):
        if budget is not None:
            delay = min(delay, budget.remaining())
        if delay > 0:
            self.sleep(delay)

    def _read_response(self, response, started, requests_count, timeouts, rate_limits):
        content_type = str(response.headers.get('Content-Type', '')).lower()
        if 'application/json' not in content_type and '+json' not in content_type:
            raise self._error(
                'invalid_content_type', started, requests_count, timeouts, rate_limits,
            )
        content_length = response.headers.get('Content-Length')
        try:
            declared_length = int(content_length) if content_length is not None else None
        except (TypeError, ValueError):
            declared_length = None
        if declared_length is not None and declared_length > self.max_json_bytes:
            raise self._error(
                'response_too_large', started, requests_count, timeouts, rate_limits,
            )
        chunks = []
        total_bytes = 0
        for chunk in response.iter_content(chunk_size=65_536):
            if not chunk:
                continue
            total_bytes += len(chunk)
            if total_bytes > self.max_json_bytes:
                raise self._error(
                    'response_too_large', started, requests_count, timeouts, rate_limits,
                )
            chunks.append(chunk)
        return b''.join(chunks)

    @staticmethod
    def _close_response(response):
        close = getattr(response, 'close', None)
        if callable(close):
            close()

    def _error(
        self,
        category,
        started,
        requests_count,
        timeouts,
        rate_limits,
        **details,
    ):
        observation = HttpObservation(
            requestCount=requests_count,
            timeoutCount=timeouts,
            rateLimitCount=rate_limits,
            durationMs=max(0, round((self.clock() - started) * 1000)),
        )
        return ProviderRequestError(category, observation=observation, **details)
