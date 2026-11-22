#!/usr/bin/env python3
"""اختبارات الجولة 6 — عمر رصيد Veo (بند 5).

`updated_at` يُسجَّل ISO مع المنطقة الزمنية عند كل تحديث،
وعمر الرقم يُعرض دائمًا؛ وبلا تاريخ = «غير معروف العمر»؛
وأقدم من 24 ساعة = قديم.

حسابات بحتة بتواريخ ثابتة — بلا شبكة وبلا ملفات.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import balance

TODAY = datetime.date(2026, 11, 22)
NOW = datetime.datetime(2026, 11, 22, 12, 0,
                        tzinfo=datetime.timezone.utc)


def _iso(hours_ago):
    return (NOW - datetime.timedelta(hours=hours_ago)).isoformat()


class TestBalanceAge(unittest.TestCase):
    def test_unknown_age_without_updated_at(self):
        label, hours, stale = balance.balance_age(None, now=NOW)
        self.assertEqual(label, "غير معروف العمر")
        self.assertIsNone(hours)
        self.assertFalse(stale)

    def test_unknown_age_with_invalid_value(self):
        self.assertEqual(balance.age_label("not-a-date", now=NOW),
                         "غير معروف العمر")
        self.assertFalse(balance.is_balance_stale("not-a-date",
                                                  now=NOW))

    def test_datetime_object_accepted(self):
        # PyYAML يحوّل الطابع غير المقتبس في config.yaml إلى
        # datetime — يُقبل كما هو.
        dt = NOW - datetime.timedelta(hours=30)
        self.assertTrue(balance.is_balance_stale(dt, now=NOW))
        self.assertEqual(balance.age_label(dt, now=NOW),
                         "منذ يوم واحد")

    def test_age_labels_arabic(self):
        self.assertEqual(balance.age_label(_iso(0.5), now=NOW),
                         "منذ أقل من ساعة")
        self.assertEqual(balance.age_label(_iso(1), now=NOW),
                         "منذ ساعة واحدة")
        self.assertEqual(balance.age_label(_iso(2), now=NOW),
                         "منذ ساعتين")
        self.assertEqual(balance.age_label(_iso(3), now=NOW),
                         "منذ 3 ساعات")
        self.assertEqual(balance.age_label(_iso(25), now=NOW),
                         "منذ يوم واحد")
        self.assertEqual(balance.age_label(_iso(49), now=NOW),
                         "منذ يومين")
        self.assertEqual(balance.age_label(_iso(72), now=NOW),
                         "منذ 3 أيام")

    def test_stale_after_24_hours(self):
        self.assertTrue(balance.is_balance_stale(_iso(30), now=NOW))
        self.assertTrue(balance.is_balance_stale(_iso(25), now=NOW))

    def test_not_stale_within_24_hours(self):
        self.assertFalse(balance.is_balance_stale(_iso(1), now=NOW))
        self.assertFalse(balance.is_balance_stale(_iso(23), now=NOW))
        self.assertFalse(balance.is_balance_stale(None, now=NOW))

    def test_now_iso_has_timezone(self):
        stamp = balance.now_iso(NOW)
        self.assertIn("+00:00", stamp)
        parsed = balance.parse_updated_at(stamp)
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed.tzinfo)


class TestRecordBalanceUpdate(unittest.TestCase):
    def test_stamp_sets_updated_at_iso(self):
        veo = {"balance_units": 680, "renews": "2026-12-13"}
        updated = balance.record_balance_update(veo, 660, now=NOW)
        self.assertEqual(updated["balance_units"], 660)
        self.assertEqual(updated["updated_at"], NOW.isoformat())
        self.assertEqual(updated["renews"], "2026-12-13")
        # الأصلي بلا تعديل.
        self.assertNotIn("updated_at", veo)
        self.assertEqual(veo["balance_units"], 680)

    def test_stamp_without_new_balance_keeps_units(self):
        veo = {"balance_units": 680}
        updated = balance.record_balance_update(veo, now=NOW)
        self.assertEqual(updated["balance_units"], 680)
        self.assertEqual(updated["updated_at"], NOW.isoformat())


class TestForecastAgeDisplay(unittest.TestCase):
    def test_forecast_carries_age_and_stale(self):
        out = balance.forecast(680, "2026-12-13", 100, 140,
                               today=TODAY, updated_at=_iso(30),
                               now=NOW)
        self.assertEqual(out["age_label"], "منذ يوم واحد")
        self.assertTrue(out["stale"])
        self.assertEqual(out["updated_at"], _iso(30))

    def test_forecast_without_updated_at_is_unknown(self):
        out = balance.forecast(680, "2026-12-13", 100, 140,
                               today=TODAY)
        self.assertEqual(out["age_label"], "غير معروف العمر")
        self.assertFalse(out["stale"])

    def test_format_always_shows_age(self):
        fresh = balance.forecast(680, "2026-12-13", 100, 140,
                                 today=TODAY, updated_at=_iso(1),
                                 now=NOW)
        text = balance.format_forecast(fresh)
        self.assertIn("عمر الرقم: منذ ساعة واحدة", text)
        self.assertNotIn("قديم", text)

    def test_format_unknown_age(self):
        out = balance.forecast(680, "2026-12-13", 100, 140,
                               today=TODAY)
        text = balance.format_forecast(out)
        self.assertIn("عمر الرقم: غير معروف العمر", text)

    def test_format_stale_warns(self):
        stale = balance.forecast(680, "2026-12-13", 100, 140,
                                 today=TODAY, updated_at=_iso(30),
                                 now=NOW)
        text = balance.format_forecast(stale)
        self.assertIn("عمر الرقم: منذ يوم واحد", text)
        self.assertIn("قديم", text)
        self.assertIn("أكثر من 24 ساعة", text)


if __name__ == "__main__":
    unittest.main()
