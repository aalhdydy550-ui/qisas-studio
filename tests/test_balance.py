#!/usr/bin/env python3
"""اختبارات توقع رصيد Veo (lib.balance).

تعمل بـ `python3 -m unittest discover -s tests -v`.
حسابات بحتة بتواريخ ثابتة — بلا شبكة وبلا ملفات.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import balance

TODAY = datetime.date(2026, 11, 22)


class TestForecast(unittest.TestCase):
    def test_current_balance_six_days(self):
        out = balance.forecast(750, "2026-12-13", 100, 140,
                               today=TODAY)
        self.assertEqual(out["balance_units"], 750)
        self.assertAlmostEqual(out["days_avg"], 6.2, places=1)
        self.assertAlmostEqual(out["days_worst"], 5.4, places=1)
        self.assertAlmostEqual(out["days_best"], 7.5, places=1)
        self.assertEqual(out["depletion_avg"], "2026-11-28")
        self.assertEqual(out["depletion_worst"], "2026-11-27")
        self.assertEqual(out["depletion_best"], "2026-11-29")
        self.assertEqual(out["days_to_renew"], 21)
        self.assertIn("OpenMontage", out["recommendation"])
        self.assertTrue(out["recorded_not_live"])

    def test_balance_covers_until_renew(self):
        out = balance.forecast(3000, "2026-12-13", 100, 140,
                               today=TODAY)
        self.assertIn("يكفي حتى موعد التجديد", out["recommendation"])

    def test_zero_balance(self):
        out = balance.forecast(0, "2026-12-13", 100, 140,
                               today=TODAY)
        self.assertEqual(out["days_avg"], 0.0)
        self.assertEqual(out["depletion_avg"], "2026-11-22")

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            balance.forecast(-5, "2026-12-13", 100, 140, today=TODAY)
        with self.assertRaises(ValueError):
            balance.forecast(750, "2026-12-13", 0, 140, today=TODAY)
        with self.assertRaises(ValueError):
            balance.forecast(750, "2026-12-13", 150, 140, today=TODAY)
        with self.assertRaises(ValueError):
            balance.forecast(750, "13-12-2026", 100, 140, today=TODAY)

    def test_huge_balance_rejected_cleanly(self):
        # اختبار انحدار (اختراق 2026-11-22): رصيد هائل كان
        # يُسقط الأمر بتتبع OverflowError بدل رسالة عربية.
        with self.assertRaises(ValueError):
            balance.forecast(10 ** 30, "2026-12-13", 100, 140,
                             today=TODAY)

    def test_string_numbers_coerced(self):
        # قيم مقتبسة في config.yaml ("750") تُقبل بدل الانهيار
        # بخطأ نوع.
        out = balance.forecast("750", "2026-12-13", "100", "140",
                               today=TODAY)
        self.assertEqual(out["days_avg"], 6.2)

    def test_non_string_renew_rejected(self):
        with self.assertRaises(ValueError):
            balance.forecast(750, 20261213, 100, 140, today=TODAY)

    def test_format_states_recorded_not_live(self):
        out = balance.forecast(750, "2026-12-13", 100, 140,
                               today=TODAY)
        text = balance.format_forecast(out)
        self.assertIn("750", text)
        self.assertIn("2026-11-28", text)
        self.assertIn("مسجَّل", text)
        self.assertIn("وليس حيًا من API", text)


if __name__ == "__main__":
    unittest.main()
