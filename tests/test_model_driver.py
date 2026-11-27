#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سجل محركات النماذج (lib/model_driver) — بند 9.

بلا شبكة حقيقية: استجابات المزوّدين محاكاة بنصوص
وأكواد HTTP، والمحركات الحية تُفحص بلا استدعاء.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import model_driver as md


class _FakeDriver(md.Driver):
    """محرك وهمي يسجّل الاستدعاءات ويرجع ردًا ثابتًا."""

    def __init__(self, name, reply="رد وهمي", fail=None):
        self.name = name
        self.reply = reply
        self.fail = fail
        self.calls = []

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        self.calls.append(prompt)
        if self.fail is not None:
            raise self.fail
        return self.reply

    def models(self):
        return ["fake-model"]

    def health(self):
        return {"available": True, "model": "fake-model"}


class TestClassify(unittest.TestCase):
    def test_each_code_from_simulated_response(self):
        cases = [
            ("أمر omniroute غير موجود في PATH", None, "missing_cli"),
            ("HTTP 401: invalid api key", 401,
             "invalid_credentials"),
            ("invalid api key", None, "invalid_credentials"),
            ("inactive subscription", None,
             "inactive_subscription"),
            ("insufficient funds", None, "insufficient_funds"),
            ("HTTP 402", 402, "insufficient_funds"),
            ("429 Too Many Requests", 429,
             "quota_or_region_restriction"),
            ("rate limit exceeded", None,
             "quota_or_region_restriction"),
            ("quota exceeded", None,
             "quota_or_region_restriction"),
            ("HTTP 503 Service Unavailable", 503,
             "upstream_outage"),
            ("model not found", None, "model_catalog_outage"),
            ("HTTP 404", 404, "model_catalog_outage"),
            ("turn not started", None, "turn_not_started"),
            ("turn usage limit refused", None,
             "turn_usage_limit_refused"),
        ]
        for text, status, expected in cases:
            with self.subTest(text=text, status=status):
                self.assertEqual(
                    md.classify_provider_error(text, status=status),
                    expected)

    def test_unknown_text_is_unknown(self):
        self.assertEqual(
            md.classify_provider_error("شيء غريب تمامًا"),
            "unknown")

    def test_status_wins_over_text(self):
        self.assertEqual(
            md.classify_provider_error("rate limit", status=401),
            "invalid_credentials")
        self.assertEqual(
            md.classify_provider_error("invalid api key",
                                       status=500),
            "upstream_outage")

    def test_provider_error_carries_code_and_arabic(self):
        err = md.ProviderError(
            "quota_or_region_restriction", "تفصيل",
            resets_at="2026-11-28T00:00:00", scope="model")
        self.assertEqual(err.code, "quota_or_region_restriction")
        self.assertIn("حصة", str(err))
        self.assertIn("تفصيل", str(err))
        self.assertEqual(err.resets_at, "2026-11-28T00:00:00")
        self.assertEqual(err.scope, "model")

    def test_provider_error_unknown_code_becomes_unknown(self):
        err = md.ProviderError("not_a_real_code")
        self.assertEqual(err.code, "unknown")

    def test_every_code_has_message_and_handling(self):
        for code in md.ERROR_CODES:
            self.assertIn(code, md.ERROR_MESSAGES_AR)
            self.assertTrue(md.ERROR_MESSAGES_AR[code])
            self.assertIn(md.handling_for(code),
                          ("retry", "switch_provider", "stop"))


class TestRegistry(unittest.TestCase):
    def setUp(self):
        md.clear_registry()

    def tearDown(self):
        md.clear_registry()
        md.register_builtin_drivers()

    def test_register_and_get(self):
        driver = _FakeDriver("fake")
        md.register("fake", driver)
        self.assertIs(md.get_driver("fake"), driver)
        self.assertEqual(md.list_drivers(), ["fake"])

    def test_unknown_driver_is_unavailable_without_raising(self):
        driver = md.get_driver("no-such-driver")
        self.assertIsInstance(driver, md.UnknownDriver)
        health = driver.health()
        self.assertEqual(health,
                         {"available": False,
                          "reason": "unknown_driver"})
        self.assertEqual(driver.models(), [])
        with self.assertRaises(md.ProviderError) as ctx:
            driver.send("مرحبًا")
        self.assertEqual(ctx.exception.code, "unknown_driver")

    def test_register_rejects_bad_driver(self):
        with self.assertRaises(ValueError):
            md.register("bad", object())
        with self.assertRaises(ValueError):
            md.register("  ", _FakeDriver("x"))

    def test_builtin_drivers_registered(self):
        md.register_builtin_drivers()
        names = md.list_drivers()
        for expected in ("gemini", "gemini-flash-lite",
                         "openrouter-free", "ollama", "omniroute"):
            self.assertIn(expected, names)

    def test_builtin_gemini_models(self):
        md.register_builtin_drivers()
        self.assertIn("gemini-3-flash-preview",
                      md.get_driver("gemini").models())
        self.assertIn("gemini-3.1-flash-lite",
                      md.get_driver("gemini-flash-lite").models())
        self.assertIn("openrouter/free",
                      md.get_driver("openrouter-free").models())

    def test_builtin_health_never_raises(self):
        md.register_builtin_drivers()
        health = md.driver_health_all()
        self.assertEqual(set(health), set(md.list_drivers()))
        for name, entry in health.items():
            self.assertIn("available", entry, name)
            self.assertIsInstance(entry["available"], bool)

    def test_failover_on_quota_returns_another_driver(self):
        md.register("gemini", _FakeDriver("gemini"))
        md.register("openrouter-free",
                    _FakeDriver("openrouter-free"))
        nxt = md.failover_driver(
            "gemini", "quota_or_region_restriction")
        self.assertEqual(nxt, "openrouter-free")

    def test_failover_none_when_rule_is_stop(self):
        md.register("gemini", _FakeDriver("gemini"))
        md.register("openrouter-free",
                    _FakeDriver("openrouter-free"))
        self.assertIsNone(md.failover_driver(
            "gemini", "invalid_credentials"))
        self.assertIsNone(md.failover_driver(
            "gemini", "insufficient_funds"))

    def test_failover_none_when_no_other_driver(self):
        md.register("only", _FakeDriver("only"))
        self.assertIsNone(md.failover_driver(
            "only", "quota_or_region_restriction"))

    def test_failover_retry_rule_returns_none(self):
        md.register("a", _FakeDriver("a"))
        md.register("b", _FakeDriver("b"))
        self.assertIsNone(md.failover_driver("a", "upstream_outage"))


class TestDriverErrors(unittest.TestCase):
    def test_fake_driver_send_and_models(self):
        driver = _FakeDriver("fake", reply="أهلًا")
        self.assertEqual(driver.send("مرحبًا"), "أهلًا")
        self.assertEqual(driver.models(), ["fake-model"])
        self.assertTrue(driver.health()["available"])

    def test_gemini_driver_translates_provider_error(self):
        # بلا شبكة: محاكاة خطأ 429 من المساعد الآمن.
        from unittest import mock
        from lib import omniroute_client
        md.clear_registry()
        try:
            md.register_builtin_drivers()
            driver = md.get_driver("gemini")
            with mock.patch.object(
                    omniroute_client, "chat_gemini",
                    side_effect=omniroute_client.OmniRouteError(
                        "HTTP 429: quota exceeded")):
                with self.assertRaises(md.ProviderError) as ctx:
                    driver.send("مرحبًا")
            self.assertEqual(ctx.exception.code,
                             "quota_or_region_restriction")
            self.assertEqual(md.handling_for(ctx.exception.code),
                             "switch_provider")
        finally:
            md.clear_registry()
            md.register_builtin_drivers()

    def test_ollama_driver_translates_missing_server(self):
        from unittest import mock
        from lib import omniroute_client
        md.clear_registry()
        try:
            md.register_builtin_drivers()
            driver = md.get_driver("ollama")
            with mock.patch.object(
                    omniroute_client, "chat_ollama",
                    side_effect=omniroute_client.OmniRouteError(
                        "خادم Ollama غير متاح")):
                with self.assertRaises(md.ProviderError) as ctx:
                    driver.send("مرحبًا")
            self.assertIn(ctx.exception.code, md.ERROR_CODES)
        finally:
            md.clear_registry()
            md.register_builtin_drivers()


if __name__ == "__main__":
    unittest.main()
