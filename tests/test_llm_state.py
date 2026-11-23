#!/usr/bin/env python3
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


if __name__ == "__main__":
    unittest.main()
