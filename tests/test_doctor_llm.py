#!/usr/bin/env python3
"""اختبارات فحوصات LLM في doctor — جولة v0.1.38.

أربع فحوصات في قسم منفصل (CLI + خادم OmniRoute + ملف
Gemini + حي Gemini)؛ وفحوصات doctor الأساسية تبقى 26.
الفحص الحي يُحاكى (بلا شبكة) عبر مساعد وهمي.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import doctor as doctor_lib


class TestRunLlmChecks(unittest.TestCase):
    def test_four_checks(self):
        checks = doctor_lib.run_llm_checks()
        self.assertEqual(len(checks), 4)
        names = [c["name"] for c in checks]
        self.assertTrue(any("OmniRoute CLI" in n for n in names))
        self.assertTrue(any("خادم OmniRoute" in n for n in names))
        self.assertTrue(any("مساعد Gemini" in n for n in names))
        for c in checks:
            self.assertIn(c["level"], ("error", "warn"))
            self.assertIn("ok", c)
            self.assertIn("detail", c)

    def test_main_checks_still_26(self):
        checks = doctor_lib.run_checks({})
        self.assertEqual(len(checks), 26)

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
