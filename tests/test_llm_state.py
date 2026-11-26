#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات حالة مزودي LLM — جولة v0.1.38.

التهدئة بعد 429 (10 دقائق) وانتهاؤها؛ والنجاح يمسحها؛
وخطأ غير الحصة بلا تهدئة؛ والعدادات اليومية تتراكم وتنقلب
بتغير التاريخ؛ وملف تالف ← حالة جديدة؛ وحفظ/تحميل ذهابًا
وإيابًا.
"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import llm_state as state_lib

PROVIDER = "ddgw/gpt-5.4-mini"


class TestCooldown(unittest.TestCase):
    def test_quota_sets_cooldown(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0)
        cooling, remaining = state_lib.cooling_down(
            state, PROVIDER, now=1000000.0 + 60)
        self.assertTrue(cooling)
        self.assertEqual(remaining, 540)

    def test_cooldown_expires(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0)
        cooling, _ = state_lib.cooling_down(
            state, PROVIDER,
            now=1000000.0 + state_lib.COOLDOWN_SECONDS + 1)
        self.assertFalse(cooling)

    def test_success_clears_cooldown(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0)
        state_lib.record_attempt(state, PROVIDER, True,
                                 now=1000000.0 + 10)
        cooling, _ = state_lib.cooling_down(
            state, PROVIDER, now=1000000.0 + 20)
        self.assertFalse(cooling)

    def test_non_quota_no_cooldown(self):
        state = state_lib.default_state()
        for kind in ("auth", "server", "network", "unknown"):
            state_lib.record_attempt(state, PROVIDER, False, kind,
                                     now=1000000.0)
            cooling, _ = state_lib.cooling_down(
                state, PROVIDER, now=1000000.0 + 1)
            self.assertFalse(cooling, kind)


class TestDailyCounters(unittest.TestCase):
    def test_counters_accumulate(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, True, now=1000000.0)
        state_lib.record_attempt(state, PROVIDER, True, now=1000001.0)
        state_lib.record_attempt(state, PROVIDER, False, "server",
                                 now=1000002.0)
        status = state_lib.provider_status(state, PROVIDER)
        self.assertEqual(status["calls_today"], 3)
        self.assertEqual(status["successes_today"], 2)
        self.assertEqual(status["failures_today"], 1)

    def test_daily_rollover(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, True, now=1000000.0)
        # اليوم التالي (86400 ثانية بعدها)
        state_lib.record_attempt(state, PROVIDER, True,
                                 now=1000000.0 + 86400)
        status = state_lib.provider_status(state, PROVIDER)
        self.assertEqual(status["calls_today"], 1)
        self.assertEqual(status["successes_today"], 1)


class TestPersistence(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            state = state_lib.default_state()
            state_lib.record_attempt(state, PROVIDER, False, "quota",
                                     now=1000000.0)
            path = state_lib.save_state(state, td)
            self.assertTrue(os.path.isfile(path))
            loaded = state_lib.load_state(td)
            self.assertEqual(
                loaded["providers"][PROVIDER]["last_error_kind"],
                "quota")
            cooling, _ = state_lib.cooling_down(
                loaded, PROVIDER, now=1000000.0 + 60)
            self.assertTrue(cooling)

    def test_corrupt_file_is_fresh_state(self):
        with tempfile.TemporaryDirectory() as td:
            path = state_lib.state_path(td)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            state = state_lib.load_state(td)
            self.assertEqual(state["providers"], {})

    def test_missing_file_is_fresh_state(self):
        with tempfile.TemporaryDirectory() as td:
            state = state_lib.load_state(td)
            self.assertEqual(state["version"], 1)

    def test_status_lines_arabic(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, True, now=1000000.0)
        # نفس يوم المحاولة (1970) — وإلا صفّر التدوير اليومي
        # العدادات قبل قراءتها (جولة v0.1.40)
        lines = state_lib.status_lines(state, [PROVIDER],
                                       now=1000000.0 + 10)
        self.assertTrue(any(PROVIDER in l for l in lines))
        self.assertTrue(any("سليم" in l for l in lines))

    def test_status_lines_rolls_over_yesterday(self):
        """انحدار (جولة v0.1.40): حالة بتاريخ الأمس ←
        status_lines تطبع تاريخ اليوم وعدادات صفرية، لا
        تاريخ الأمس وعداداته."""
        today = time.strftime("%Y-%m-%d")
        yesterday = time.strftime(
            "%Y-%m-%d", time.localtime(time.time() - 86400))
        self.assertNotEqual(today, yesterday)
        state = state_lib.default_state()
        state["daily"] = {"date": yesterday,
                          "calls": {PROVIDER: 7},
                          "successes": {PROVIDER: 5},
                          "failures": {PROVIDER: 2}}
        lines = state_lib.status_lines(state, [PROVIDER])
        self.assertIn(today, lines[0])
        self.assertNotIn(yesterday, lines[0])
        provider_line = [l for l in lines if PROVIDER in l][0]
        self.assertIn("مكالمات اليوم 0", provider_line)
        self.assertIn("ناجحة 0", provider_line)
        # التدوير في الذاكرة فقط — الحالة نفسها تحدّثت
        self.assertEqual(state["daily"]["date"], today)
        self.assertEqual(state["daily"]["calls"], {})


GEMINI = "gemini-3-flash-preview"  # RPM ‏10 / RPD ‏20 / TPM ‏250,000
GROQ = "openai/gpt-oss-120b"  # RPM ‏30 / RPD ‏1000 / TPM ‏8,000


class TestSlidingCounters(unittest.TestCase):
    def test_rpm_exceeded_blocks_call(self):
        state = state_lib.default_state()
        for i in range(10):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        allowed, reason, retry = state_lib.can_call(
            state, GEMINI, now=1000000.0 + 30)
        self.assertFalse(allowed)
        self.assertEqual(reason, "rpm")
        self.assertGreater(retry, 0)
        self.assertLessEqual(retry, 60)

    def test_rpm_slides_allows_after_window(self):
        state = state_lib.default_state()
        for i in range(10):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        # بعد 61 ثانية من أول مكالمة: النافذة انزلقت.
        allowed, reason, _ = state_lib.can_call(
            state, GEMINI, now=1000000.0 + 61)
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_tpm_exceeded_blocks_call(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, GROQ, True, tokens=7900,
                                 now=1000000.0)
        # تقدير 200 رمز إضافي يتجاوز 8,000.
        allowed, reason, _ = state_lib.can_call(
            state, GROQ, est_tokens=200, now=1000000.0 + 1)
        self.assertFalse(allowed)
        self.assertEqual(reason, "tpm")

    def test_tpm_at_limit_allows(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, GROQ, True, tokens=7900,
                                 now=1000000.0)
        allowed, _, _ = state_lib.can_call(
            state, GROQ, est_tokens=100, now=1000000.0 + 1)
        self.assertTrue(allowed)

    def test_rpd_exceeded_blocks_call(self):
        state = state_lib.default_state()
        for i in range(20):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i * 4000)
        allowed, reason, retry = state_lib.can_call(
            state, GEMINI, now=1000000.0 + 20 * 4000)
        self.assertFalse(allowed)
        self.assertEqual(reason, "rpd")
        self.assertGreater(retry, 0)

    def test_unknown_provider_only_cooldown_checked(self):
        state = state_lib.default_state()
        for i in range(50):
            state_lib.record_attempt(state, PROVIDER, True,
                                     now=1000000.0 + i)
        # ddgw بلا حدود معروفة: 50 مكالمة لا تحظر.
        allowed, reason, _ = state_lib.can_call(
            state, PROVIDER, now=1000000.0 + 60)
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_per_key_isolation(self):
        state = state_lib.default_state()
        for i in range(10):
            state_lib.record_attempt(state, GEMINI, True,
                                     key_id="key-a",
                                     now=1000000.0 + i)
        # مفتاح آخر مستقل: مسموح رغم امتلاء الأول.
        allowed, _, _ = state_lib.can_call(
            state, GEMINI, key_id="key-b", now=1000000.0 + 30)
        self.assertTrue(allowed)
        allowed, reason, _ = state_lib.can_call(
            state, GEMINI, key_id="key-a", now=1000000.0 + 30)
        self.assertFalse(allowed)
        self.assertEqual(reason, "rpm")

    def test_custom_limits_respected(self):
        state = state_lib.default_state()
        state_lib.set_limits(state, PROVIDER, {"rpm": 2})
        state_lib.record_attempt(state, PROVIDER, True,
                                 now=1000000.0)
        state_lib.record_attempt(state, PROVIDER, True,
                                 now=1000000.0 + 1)
        allowed, reason, _ = state_lib.can_call(
            state, PROVIDER, now=1000000.0 + 2)
        self.assertFalse(allowed)
        self.assertEqual(reason, "rpm")

    def test_get_limits_defaults(self):
        state = state_lib.default_state()
        limits = state_lib.get_limits(state, GEMINI)
        self.assertEqual(limits["rpm"], 10)
        self.assertEqual(limits["rpd"], 20)
        self.assertEqual(limits["tpm"], 250000)

    def test_set_limits_ignores_invalid(self):
        state = state_lib.default_state()
        state_lib.set_limits(state, PROVIDER,
                             {"rpm": -3, "bogus": 5, "tpm": "x"})
        self.assertEqual(state["limits"], {})


class TestQuotaCheck(unittest.TestCase):
    def test_cooldown_reason_from_can_call(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, GEMINI, False, "quota",
                                 now=1000000.0)
        allowed, reason, retry = state_lib.can_call(
            state, GEMINI, now=1000000.0 + 60)
        self.assertFalse(allowed)
        self.assertEqual(reason, "cooldown")
        self.assertEqual(retry, 540)

    def test_provider_status_quota_fields(self):
        state = state_lib.default_state()
        for i in range(10):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        status = state_lib.provider_status(state, GEMINI,
                                           now=1000000.0 + 30)
        self.assertFalse(status["quota_ok"])
        self.assertEqual(status["quota_reason"], "rpm")
        self.assertEqual(status["rpm_calls"], 10)
        self.assertEqual(status["limits"]["rpm"], 10)

    def test_status_lines_show_quota_block(self):
        state = state_lib.default_state()
        for i in range(10):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        lines = state_lib.status_lines(state, [GEMINI],
                                       now=1000000.0 + 30)
        provider_line = [l for l in lines if GEMINI in l][0]
        self.assertIn("تجاوز حد الحصة (rpm)", provider_line)


class TestProactiveCooldown(unittest.TestCase):
    def test_applies_at_threshold(self):
        state = state_lib.default_state()
        # 8 من 10 RPM = 80% = العتبة.
        for i in range(8):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        applied = state_lib.apply_proactive_cooldown(
            state, GEMINI, now=1000000.0 + 10)
        self.assertTrue(applied)
        cooling, remaining = state_lib.cooling_down(
            state, GEMINI, now=1000000.0 + 10)
        self.assertTrue(cooling)
        self.assertLessEqual(remaining, 60)

    def test_no_apply_below_threshold(self):
        state = state_lib.default_state()
        for i in range(5):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        applied = state_lib.apply_proactive_cooldown(
            state, GEMINI, now=1000000.0 + 10)
        self.assertFalse(applied)
        cooling, _ = state_lib.cooling_down(
            state, GEMINI, now=1000000.0 + 10)
        self.assertFalse(cooling)

    def test_no_apply_when_already_cooling(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, GEMINI, False, "quota",
                                 now=1000000.0)
        applied = state_lib.apply_proactive_cooldown(
            state, GEMINI, now=1000000.0 + 10)
        self.assertFalse(applied)

    def test_proactive_expires_quickly(self):
        state = state_lib.default_state()
        for i in range(8):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        state_lib.apply_proactive_cooldown(state, GEMINI,
                                           now=1000000.0 + 10)
        cooling, _ = state_lib.cooling_down(
            state, GEMINI, now=1000000.0 + 10 + 61)
        self.assertFalse(cooling)


class TestCooldownLadder(unittest.TestCase):
    def test_second_consecutive_quota_is_longer(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0)
        _, first = state_lib.cooling_down(
            state, PROVIDER, now=1000000.0)
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0 + 10)
        _, second = state_lib.cooling_down(
            state, PROVIDER, now=1000000.0 + 10)
        self.assertEqual(first, 600)
        self.assertEqual(second, 3600)

    def test_third_consecutive_quota_is_a_day(self):
        state = state_lib.default_state()
        for i in range(3):
            state_lib.record_attempt(state, PROVIDER, False, "quota",
                                     now=1000000.0 + i * 10)
        _, remaining = state_lib.cooling_down(
            state, PROVIDER, now=1000000.0 + 20)
        self.assertEqual(remaining, 86400)

    def test_non_quota_resets_ladder(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0)
        state_lib.record_attempt(state, PROVIDER, False, "server",
                                 now=1000000.0 + 10)
        state_lib.record_attempt(state, PROVIDER, False, "quota",
                                 now=1000000.0 + 20)
        _, remaining = state_lib.cooling_down(
            state, PROVIDER, now=1000000.0 + 20)
        self.assertEqual(remaining, 600)


class TestWindowRollover(unittest.TestCase):
    def test_yesterday_calls_do_not_count(self):
        state = state_lib.default_state()
        for i in range(10):
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0 + i)
        # بعد يوم كامل: النافذتان (دقيقة/يوم) فارغتان.
        allowed, reason, _ = state_lib.can_call(
            state, GEMINI, now=1000000.0 + 86400)
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_windows_pruned_on_save_load(self):
        with tempfile.TemporaryDirectory() as td:
            state = state_lib.default_state()
            state_lib.record_attempt(state, GEMINI, True,
                                     now=1000000.0)
            state_lib.save_state(state, td)
            loaded = state_lib.load_state(td)
            # النافذة محفوظة وتُقرأ سليمة.
            rpm, rpd, tpm, tpd = state_lib._window_counts(
                loaded, GEMINI, now=1000000.0 + 5)
            self.assertEqual(rpm, 1)
            self.assertEqual(rpd, 1)

    def test_corrupt_windows_are_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            path = state_lib.state_path(td)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "providers": {},
                           "daily": {"date": "2026-11-26",
                                     "calls": {}, "successes": {},
                                     "failures": {}},
                           "windows": {"bad": "not-a-dict",
                                       "also-bad": {"calls": "x",
                                                    "tokens": [[1]]}},
                           "limits": "not-a-dict"},
                          fh)
            state = state_lib.load_state(td)
            # مدخل غير dict يُحذف، ومدخل بقوائم تالفة يُطهَّر
            # إلى قوائم فارغة؛ وكلاهما صالح للاستخدام.
            self.assertNotIn("bad", state["windows"])
            self.assertEqual(state["windows"]["also-bad"],
                             {"calls": [], "tokens": []})
            self.assertEqual(state["limits"], {})
            allowed, _, _ = state_lib.can_call(
                state, GEMINI, now=1000000.0)
            self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
