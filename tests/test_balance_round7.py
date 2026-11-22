#!/usr/bin/env python3
"""اختبارات سقف Veo في balance (lib.balance) — الجولة 7.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في ملفات config مؤقتة — لا يُمس config.yaml
الحقيقي ولا أي رصيد Veo فعلي.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import balance as balance_lib

CFG_TEXT = """publish:
  page_id: "1048148471706586"

veo:
  balance_units: 680
  renews: "2026-12-13"
"""


def _config(tmpdir, text=CFG_TEXT):
    path = os.path.join(tmpdir, "config.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class TestCheckCap(unittest.TestCase):
    def test_no_cap_ok(self):
        ok, reason = balance_lib.check_cap(120, {"balance_units": 680})
        self.assertTrue(ok)
        self.assertIn("ضمن", reason)

    def test_no_cap_no_balance_honest_message(self):
        # انحدار (الجولة 9): بلا سقف مضبوط ولا رصيد مسجَّل لم
        # يُفحص شيء أصلًا — فالرسالة القديمة «ضمن السقف
        # والرصيد» كانت تدّعي فحصًا لم يحدث.
        ok, reason = balance_lib.check_cap(120, {})
        self.assertTrue(ok)
        self.assertIn("لم يُفحص", reason)
        self.assertNotIn("ضمن السقف والرصيد", reason)

    def test_under_cap_ok(self):
        ok, _ = balance_lib.check_cap(
            120, {"balance_units": 680, "cap_units": 200})
        self.assertTrue(ok)

    def test_exact_cap_ok(self):
        ok, _ = balance_lib.check_cap(
            120, {"balance_units": 680, "cap_units": 120})
        self.assertTrue(ok)

    def test_over_cap_refused(self):
        ok, reason = balance_lib.check_cap(
            120, {"balance_units": 680, "cap_units": 100})
        self.assertFalse(ok)
        self.assertIn("يتجاوز سقف", reason)
        self.assertIn("100", reason)

    def test_over_balance_refused(self):
        ok, reason = balance_lib.check_cap(
            120, {"balance_units": 100, "cap_units": 200})
        self.assertFalse(ok)
        self.assertIn("الرصيد", reason)

    def test_invalid_cap(self):
        with self.assertRaises(ValueError):
            balance_lib.check_cap(
                120, {"balance_units": 680, "cap_units": "abc"})
        with self.assertRaises(ValueError):
            balance_lib.check_cap(
                120, {"balance_units": 680, "cap_units": 0})


class TestSaveVeoValue(unittest.TestCase):
    def test_save_cap(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            balance_lib.save_veo_value("cap_units", 200, path)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("cap_units: 200", text)
            self.assertIn("balance_units: 680", text)

    def test_update_cap(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            balance_lib.save_veo_value("cap_units", 200, path)
            balance_lib.save_veo_value("cap_units", 150, path)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("cap_units: 150", text)
            self.assertEqual(text.count("cap_units:"), 1)

    def test_remove_cap(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            balance_lib.save_veo_value("cap_units", 200, path)
            balance_lib.remove_veo_key("cap_units", path)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("cap_units", text)
            self.assertIn("balance_units: 680", text)

    def test_remove_missing_key_ok(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            balance_lib.remove_veo_key("cap_units", path)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("balance_units: 680", text)

    def test_bad_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            with self.assertRaises(ValueError):
                balance_lib.save_veo_value(
                    "balance; rm -rf /", 1, path)


class TestForecastCap(unittest.TestCase):
    def test_forecast_with_cap(self):
        result = balance_lib.forecast(
            680, "2026-12-13", 120, 120, cap_units=200)
        self.assertEqual(result["cap_units"], 200)
        text = balance_lib.format_forecast(result)
        self.assertIn("سقف الإنفاق", text)
        self.assertIn("200", text)

    def test_forecast_without_cap(self):
        result = balance_lib.forecast(680, "2026-12-13", 120, 120)
        self.assertIsNone(result["cap_units"])
        text = balance_lib.format_forecast(result)
        self.assertNotIn("سقف الإنفاق", text)


if __name__ == "__main__":
    unittest.main()
