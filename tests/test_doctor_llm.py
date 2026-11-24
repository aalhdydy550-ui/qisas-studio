#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات فحوصات LLM في doctor — جولة v0.1.38 + v0.1.39 + v0.1.40 + v0.1.41.

ست فحوصات في قسم منفصل (CLI + خادم OmniRoute + ملف
Gemini + حي Gemini + Groq + Ollama المحلي)؛ وفحوصات doctor الأساسية تبقى 27.
الفحص الحي يُحاكى (بلا شبكة) عبر مساعد وهمي.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import doctor as doctor_lib


class TestRunLlmChecks(unittest.TestCase):
    def test_six_checks(self):
        checks = doctor_lib.run_llm_checks()
        self.assertEqual(len(checks), 6)
        names = [c["name"] for c in checks]
        self.assertTrue(any("OmniRoute CLI" in n for n in names))
        self.assertTrue(any("خادم OmniRoute" in n for n in names))
        self.assertTrue(any("مساعد Gemini" in n for n in names))
        self.assertTrue(any("Groq" in n for n in names))
        self.assertTrue(any("Ollama" in n for n in names))
        for c in checks:
            self.assertIn(c["level"], ("error", "warn"))
            self.assertIn("ok", c)
            self.assertIn("detail", c)

    def test_groq_check_warns_without_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = doctor_lib._groq_check()
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")
        self.assertIn("GROQ_API_KEY", result["detail"])

    def test_groq_check_ok_with_key(self):
        with mock.patch.dict(os.environ,
                             {"GROQ_API_KEY": "gsk_fake"}):
            result = doctor_lib._groq_check()
        self.assertTrue(result["ok"])
        self.assertEqual(result["level"], "warn")

    def test_main_checks_still_27(self):
        checks = doctor_lib.run_checks({})
        self.assertEqual(len(checks), 27)

    def test_gemini_live_check_with_fake_helper(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            helper = os.path.join(td, "gemini.py")
            with open(helper, "w", encoding="utf-8") as fh:
                fh.write("print('{\"models\": []}')\n")
            with mock.patch.object(doctor_lib, "GEMINI_HELPER",
                                   helper):
                result = doctor_lib._gemini_live_check(timeout=30)
        self.assertTrue(result["ok"])
        self.assertEqual(result["level"], "warn")

    def test_gemini_live_check_failing_helper(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            helper = os.path.join(td, "gemini.py")
            with open(helper, "w", encoding="utf-8") as fh:
                fh.write("import sys\nsys.exit(1)\n")
            with mock.patch.object(doctor_lib, "GEMINI_HELPER",
                                   helper):
                result = doctor_lib._gemini_live_check(timeout=30)
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")

    def test_gemini_live_check_missing_helper(self):
        with mock.patch.object(doctor_lib, "GEMINI_HELPER",
                               "/tmp/no-such-gemini-helper.py"):
            result = doctor_lib._gemini_live_check(timeout=5)
        self.assertFalse(result["ok"])
        self.assertIn("غير موجود", result["detail"])


if __name__ == "__main__":
    unittest.main()
