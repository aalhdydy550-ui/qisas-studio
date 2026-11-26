#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سياسة إعادة المحاولة الموحّدة (lib.retry_policy).

زوج موجب/سالب لكل سلوك: إعادة عند 429، ولا إعادة عند
400/401/403، واحترام Retry-After، ورفض النوم الطويل بإعادة
الجدولة، والميزانية الإجمالية، ومحوّلات ترويسات حدود المعدل.
بلا أي شبكة — كل النوم والساعة محاكاة.
"""
import os
import random
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import retry_policy as rp


class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _FakeSleep:
    def __init__(self, clock):
        self.calls = []
        self.clock = clock

    def __call__(self, seconds):
        self.calls.append(seconds)
        self.clock.advance(seconds)


def _http_error(status, retry_after=None):
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return rp.HttpStatusError(status, headers, "خطأ %s" % status)


class TestClassifyStatus(unittest.TestCase):
    def test_429_is_rate_limited(self):
        self.assertEqual(rp.classify_status(429), "rate_limited")

    def test_402_is_rate_limited(self):
        self.assertEqual(rp.classify_status(402), "rate_limited")

    def test_5xx_is_server(self):
        for code in (500, 502, 503, 504):
            self.assertEqual(rp.classify_status(code), "server", code)

    def test_400_401_403_are_logical(self):
        for code in (400, 401, 403, 404, 422):
            self.assertEqual(rp.classify_status(code), "logical", code)

    def test_no_status_is_transport(self):
        self.assertEqual(rp.classify_status(None), "transport")

    def test_urllib_errors_classified(self):
        kind, _ = rp.classify_exception(
            urllib.error.URLError("no route"))
        self.assertEqual(kind, "transport")
        kind, _ = rp.classify_exception(
            rp.TransportError("timeout"))
        self.assertEqual(kind, "transport")
        kind, _ = rp.classify_exception(_http_error(429, "5"))
        self.assertEqual(kind, "rate_limited")
        self.assertEqual(rp.classify_exception(ValueError("x")),
                         None)


class TestParseRetryAfter(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(
            rp.parse_retry_after({"Retry-After": "120"}), 120.0)
        self.assertEqual(
            rp.parse_retry_after({"retry-after": "0"}), 0.0)

    def test_missing_or_invalid_is_none(self):
        self.assertIsNone(rp.parse_retry_after({}))
        self.assertIsNone(rp.parse_retry_after(
            {"Retry-After": "قريبًا"}))
        self.assertIsNone(rp.parse_retry_after(
            {"Retry-After": "-5"}))

    def test_http_date(self):
        import time
        from email.utils import formatdate
        future = formatdate(time.time() + 90, usegmt=True)
        value = rp.parse_retry_after({"Retry-After": future})
        self.assertIsNotNone(value)
        self.assertGreater(value, 60)
        self.assertLessEqual(value, 120)


class TestDelayFor(unittest.TestCase):
    def test_exponential_without_jitter(self):
        policy = rp.RetryPolicy(max_attempts=5, base_delay=2.0,
                                jitter=False)
        self.assertEqual(policy.delay_for(0), 2.0)
        self.assertEqual(policy.delay_for(1), 4.0)
        self.assertEqual(policy.delay_for(2), 8.0)
        self.assertEqual(policy.delay_for(10), 30.0)  # سقف max_delay

    def test_retry_after_honored_and_capped(self):
        policy = rp.RetryPolicy(max_attempts=5, base_delay=1.0,
                                jitter=False)
        self.assertEqual(policy.delay_for(0, retry_after=5), 5.0)
        self.assertEqual(policy.delay_for(0, retry_after=999), 30.0)

    def test_jitter_within_bounds(self):
        rng = random.Random(7)
        policy = rp.RetryPolicy(max_attempts=5, base_delay=4.0,
                                rng=rng)
        for _ in range(20):
            delay = policy.delay_for(1)  # سقف 8 قبل الجيتر
            self.assertGreaterEqual(delay, 0.0)
            self.assertLessEqual(delay, 8.0)

    def test_max_attempts_validated(self):
        with self.assertRaises(ValueError):
            rp.RetryPolicy(max_attempts=0)
        with self.assertRaises(ValueError):
            rp.RetryPolicy(max_attempts=6)


class TestCallWithRetry(unittest.TestCase):
    def _run(self, failures, policy=None):
        clock = _FakeClock()
        sleep = _FakeSleep(clock)
        calls = []

        def fn():
            calls.append(1)
            if len(calls) <= len(failures):
                raise failures[len(calls) - 1]
            return "ok"

        result = rp.call_with_retry(fn, policy=policy, sleep=sleep,
                                    clock=clock)
        return result, calls, sleep

    def test_retry_on_429_then_success(self):
        result, calls, sleep = self._run(
            [_http_error(429), _http_error(429)])
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(sleep.calls), 2)

    def test_no_retry_on_400(self):
        clock = _FakeClock()
        sleep = _FakeSleep(clock)

        def fn():
            raise _http_error(400)

        with self.assertRaises(rp.HttpStatusError):
            rp.call_with_retry(fn, sleep=sleep, clock=clock)
        self.assertEqual(sleep.calls, [])

    def test_no_retry_on_401_and_403(self):
        for code in (401, 403):
            clock = _FakeClock()
            sleep = _FakeSleep(clock)
            calls = []

            def fn(code=code):
                calls.append(1)
                raise _http_error(code)

            with self.assertRaises(rp.HttpStatusError):
                rp.call_with_retry(fn, sleep=sleep, clock=clock)
            self.assertEqual(len(calls), 1, code)
            self.assertEqual(sleep.calls, [], code)

    def test_retry_on_transport_then_success(self):
        result, calls, sleep = self._run(
            [rp.TransportError("قطع الاتصال")])
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    def test_retry_on_503_then_success(self):
        result, calls, sleep = self._run([_http_error(503)])
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    def test_max_attempts_exhausted_reraises_last(self):
        clock = _FakeClock()
        sleep = _FakeSleep(clock)
        calls = []

        def fn():
            calls.append(1)
            raise _http_error(429)

        policy = rp.RetryPolicy(max_attempts=3, base_delay=0.0,
                                jitter=False)
        with self.assertRaises(rp.HttpStatusError) as ctx:
            rp.call_with_retry(fn, policy=policy, sleep=sleep,
                               clock=clock)
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(sleep.calls), 2)

    def test_retry_after_honored(self):
        clock = _FakeClock()
        sleep = _FakeSleep(clock)
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(429, "7")
            return "ok"

        policy = rp.RetryPolicy(max_attempts=3, base_delay=1.0,
                                jitter=False)
        result = rp.call_with_retry(fn, policy=policy, sleep=sleep,
                                    clock=clock)
        self.assertEqual(result, "ok")
        self.assertEqual(sleep.calls, [7.0])

    def test_retry_after_too_long_raises_without_sleep(self):
        clock = _FakeClock()
        sleep = _FakeSleep(clock)
        calls = []

        def fn():
            calls.append(1)
            raise _http_error(429, "300")

        with self.assertRaises(rp.RetryAfterTooLong) as ctx:
            rp.call_with_retry(fn, sleep=sleep, clock=clock)
        self.assertEqual(ctx.exception.retry_after, 300.0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sleep.calls, [])

    def test_total_budget_exceeded(self):
        clock = _FakeClock()
        sleep = _FakeSleep(clock)
        calls = []

        def fn():
            calls.append(1)
            raise _http_error(503)

        policy = rp.RetryPolicy(max_attempts=5, base_delay=20.0,
                                total_budget_seconds=15.0,
                                jitter=False)
        with self.assertRaises(rp.RetryBudgetExceeded):
            rp.call_with_retry(fn, policy=policy, sleep=sleep,
                               clock=clock)
        self.assertEqual(len(calls), 1)

    def test_on_retry_callback(self):
        seen = []
        clock = _FakeClock()
        sleep = _FakeSleep(clock)
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(429)
            return "ok"

        rp.call_with_retry(
            fn, policy=rp.RetryPolicy(max_attempts=3, base_delay=1.0,
                                      jitter=False),
            sleep=sleep, clock=clock,
            on_retry=lambda a, k, d, e: seen.append((a, k, d)))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], 1)
        self.assertEqual(seen[0][1], "rate_limited")


class TestRateLimitHeaders(unittest.TestCase):
    def test_groq_headers(self):
        info = rp.parse_rate_limit_headers("groq", {
            "x-ratelimit-remaining-requests": "12",
            "x-ratelimit-limit-requests": "30",
            "x-ratelimit-reset-requests": "45s",
        })
        self.assertEqual(info["remaining"], 12)
        self.assertEqual(info["limit"], 30)
        self.assertEqual(info["reset_in"], 45.0)

    def test_openrouter_headers(self):
        info = rp.parse_rate_limit_headers("openrouter", {
            "X-RateLimit-Remaining": "100",
            "X-RateLimit-Limit": "200",
        })
        self.assertEqual(info["remaining"], 100)
        self.assertEqual(info["limit"], 200)

    def test_gemini_retry_after(self):
        info = rp.parse_rate_limit_headers("gemini", {
            "Retry-After": "20",
        })
        self.assertEqual(info["retry_after"], 20.0)

    def test_facebook_app_usage(self):
        info = rp.parse_rate_limit_headers("facebook", {
            "x-app-usage": '{"call_count": 42, "total_time": 71}',
        })
        self.assertEqual(info["usage_percent"], 71)
        self.assertIsNone(info["remaining"])

    def test_unknown_provider_generic_scan(self):
        info = rp.parse_rate_limit_headers("acme", {
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Limit": "10",
        })
        self.assertEqual(info["remaining"], 5)
        self.assertEqual(info["limit"], 10)

    def test_format_log_line(self):
        line = rp.format_rate_limit_log("groq", {
            "remaining": 12, "limit": 30, "reset_in": 45.0,
            "retry_after": None, "usage_percent": None})
        self.assertIn("12/30", line)
        self.assertIn("45", line)
        self.assertEqual(rp.format_rate_limit_log("x", {}), "")

    def test_log_rate_limit_returns_info(self):
        seen = []
        info = rp.log_rate_limit("groq", {
            "x-ratelimit-remaining-requests": "3",
        }, logger=seen.append)
        self.assertEqual(info["remaining"], 3)
        self.assertEqual(len(seen), 1)


if __name__ == "__main__":
    unittest.main()
