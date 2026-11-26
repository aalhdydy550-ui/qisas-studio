#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الجلب العام (lib.fetch_public) — جولة الأنماط (W1).

زوج موجب/سالب لكل سلوك: فحص robots.txt قبل الجلب، ورفض
المضيف خارج قائمة السماح، وإعادة المحاولة عند 429 بحد 3
محاولات، ولا إعادة عند 404. بلا أي شبكة حية — الجلب
وجلب robots.txt محاكاة.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import fetch_public as fp
from lib import retry_policy as rp

ALLOW = ("example.com", "example.org")
URL = "https://example.com/page"
ROBOTS_ALLOW = "User-agent: *\nAllow: /\n"
ROBOTS_DISALLOW = "User-agent: *\nDisallow: /page\n"


def _robots(text):
    def fetch(robots_url, headers, timeout):
        return text
    return fetch


def _fetcher(results):
    """results: قائمة (status, headers, body) أو استثناءات."""
    calls = []

    def fetch(url, headers, timeout):
        calls.append(url)
        item = results[min(len(calls) - 1, len(results) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    fetch.calls = calls
    return fetch


class TestAllowlist(unittest.TestCase):
    def test_allowed_host_fetched(self):
        fetch = _fetcher([(200, {}, b"hello")])
        res = fp.fetch_public(URL, allowlist=ALLOW,
                              robots_fetcher=_robots(ROBOTS_ALLOW),
                              fetcher=fetch, robots_cache={})
        self.assertEqual(res["status"], 200)
        self.assertEqual(res["body"], b"hello")
        self.assertEqual(fetch.calls, [URL])

    def test_host_outside_allowlist_refused_without_fetch(self):
        fetch = _fetcher([(200, {}, b"hello")])
        with self.assertRaises(fp.AllowlistBlockedError):
            fp.fetch_public("https://evil.example/x",
                            allowlist=ALLOW,
                            robots_fetcher=_robots(ROBOTS_ALLOW),
                            fetcher=fetch, robots_cache={})
        self.assertEqual(fetch.calls, [])

    def test_empty_allowlist_refuses_everything(self):
        fetch = _fetcher([(200, {}, b"hello")])
        with self.assertRaises(fp.AllowlistBlockedError):
            fp.fetch_public(URL, allowlist=(),
                            robots_fetcher=_robots(ROBOTS_ALLOW),
                            fetcher=fetch, robots_cache={})
        self.assertEqual(fetch.calls, [])

    def test_invalid_url_refused(self):
        with self.assertRaises(fp.FetchBlockedError):
            fp.fetch_public("notaurl", allowlist=ALLOW,
                            robots_cache={})


class TestRobots(unittest.TestCase):
    def test_disallowed_path_refused_and_logged(self):
        fetch = _fetcher([(200, {}, b"hello")])
        seen = []
        with self.assertRaises(fp.RobotsBlockedError) as ctx:
            fp.fetch_public(URL, allowlist=ALLOW,
                            robots_fetcher=_robots(ROBOTS_DISALLOW),
                            fetcher=fetch, robots_cache={},
                            logger=seen.append)
        self.assertIn("robots.txt", str(ctx.exception))
        self.assertEqual(fetch.calls, [])
        self.assertTrue(any("robots.txt" in m for m in seen))

    def test_allowed_path_fetched(self):
        fetch = _fetcher([(200, {}, b"ok")])
        res = fp.fetch_public(URL, allowlist=ALLOW,
                              robots_fetcher=_robots(ROBOTS_ALLOW),
                              fetcher=fetch, robots_cache={})
        self.assertEqual(res["body"], b"ok")

    def test_missing_robots_txt_is_fail_open(self):
        fetch = _fetcher([(200, {}, b"ok")])

        def no_robots(url, headers, timeout):
            return None  # 404 أو تعذّر — ليس منعًا

        res = fp.fetch_public(URL, allowlist=ALLOW,
                              robots_fetcher=no_robots,
                              fetcher=fetch, robots_cache={})
        self.assertEqual(res["body"], b"ok")

    def test_robots_fetched_once_per_host(self):
        fetch = _fetcher([(200, {}, b"ok")])
        robots_calls = []

        def robots(url, headers, timeout):
            robots_calls.append(url)
            return ROBOTS_ALLOW

        cache = {}
        for _ in range(2):
            fp.fetch_public(URL, allowlist=ALLOW,
                            robots_fetcher=robots,
                            fetcher=fetch, robots_cache=cache)
        self.assertEqual(len(robots_calls), 1)


class TestRetry(unittest.TestCase):
    def test_retry_on_429_then_success(self):
        fetch = _fetcher([rp.HttpStatusError(429, {}, "slow"),
                          (200, {}, b"ok")])
        policy = rp.RetryPolicy(max_attempts=3, base_delay=0.0,
                                jitter=False)
        res = fp.fetch_public(URL, allowlist=ALLOW,
                              robots_fetcher=_robots(ROBOTS_ALLOW),
                              fetcher=fetch, robots_cache={},
                              policy=policy)
        self.assertEqual(res["body"], b"ok")
        self.assertEqual(len(fetch.calls), 2)

    def test_429_exhausts_three_attempts(self):
        fetch = _fetcher([rp.HttpStatusError(429, {}, "slow")])
        policy = rp.RetryPolicy(max_attempts=3, base_delay=0.0,
                                jitter=False)
        with self.assertRaises(rp.HttpStatusError) as ctx:
            fp.fetch_public(URL, allowlist=ALLOW,
                            robots_fetcher=_robots(ROBOTS_ALLOW),
                            fetcher=fetch, robots_cache={},
                            policy=policy)
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(len(fetch.calls), 3)

    def test_no_retry_on_404(self):
        fetch = _fetcher([rp.HttpStatusError(404, {}, "gone")])
        policy = rp.RetryPolicy(max_attempts=3, base_delay=0.0,
                                jitter=False)
        with self.assertRaises(rp.HttpStatusError):
            fp.fetch_public(URL, allowlist=ALLOW,
                            robots_fetcher=_robots(ROBOTS_ALLOW),
                            fetcher=fetch, robots_cache={},
                            policy=policy)
        self.assertEqual(len(fetch.calls), 1)

    def test_retry_after_too_long_propagates(self):
        fetch = _fetcher([rp.HttpStatusError(
            429, {"Retry-After": "300"}, "slow")])
        policy = rp.RetryPolicy(max_attempts=3, base_delay=0.0,
                                jitter=False)
        with self.assertRaises(rp.RetryAfterTooLong):
            fp.fetch_public(URL, allowlist=ALLOW,
                            robots_fetcher=_robots(ROBOTS_ALLOW),
                            fetcher=fetch, robots_cache={},
                            policy=policy)
        self.assertEqual(len(fetch.calls), 1)

    def test_transport_retried(self):
        fetch = _fetcher([rp.TransportError("قطع"),
                          (200, {}, b"ok")])
        policy = rp.RetryPolicy(max_attempts=3, base_delay=0.0,
                                jitter=False)
        res = fp.fetch_public(URL, allowlist=ALLOW,
                              robots_fetcher=_robots(ROBOTS_ALLOW),
                              fetcher=fetch, robots_cache={},
                              policy=policy)
        self.assertEqual(res["body"], b"ok")
        self.assertEqual(len(fetch.calls), 2)


if __name__ == "__main__":
    unittest.main()
