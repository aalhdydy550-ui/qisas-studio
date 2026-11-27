#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات منطقة التسجيل Africa/Cairo — جولة v0.1.63، بند 35
(عقد ع19).

القاعدة: كل الأوقات المعروضة والجداول بمنطقة Africa/Cairo
(لا UTC). هذه الاختبارات تحرس مساعدات تنسيق الوقت الموجودة
فعلًا في المشروع (لا مساعدات جديدة): صياغة الجدولة في
`lib/publish.py`، وطوابع «الآن» في `lib/job_registry.py` و
`lib/manifest.py` و`lib/balance.py`، وثوابت أول تشغيل في
`lib/license.py`. بلا شبكة وبلا ملفات — تواريخ ثابتة فقط.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import balance as balance_lib
from lib import job_registry
from lib import license as lic
from lib import manifest as manifest_lib
from lib import publish

CAIRO = ZoneInfo("Africa/Cairo")

# 08:00 صباح 27 نوفمبر 2026 بتوقيت القاهرة (شتاءً: +02:00).
MORNING_EPOCH = int(datetime(2026, 11, 27, 8, 0,
                             tzinfo=CAIRO).timestamp())


class TestDisplayedTimestampsCarryCairo(unittest.TestCase):
    """كل طابع زمني معروض يحمل Africa/Cairo صراحةً."""

    def test_format_schedule_carries_cairo(self):
        self.assertEqual(
            publish.format_schedule(MORNING_EPOCH),
            "2026-11-27 08:00 Africa/Cairo")

    def test_format_schedule_never_says_utc(self):
        self.assertNotIn("UTC", publish.format_schedule(MORNING_EPOCH))

    def test_parse_schedule_round_trip_in_cairo(self):
        epoch = publish.parse_schedule("2026-11-27 08:00", now=0)
        self.assertEqual(epoch, MORNING_EPOCH)
        self.assertEqual(publish.format_schedule(epoch),
                         "2026-11-27 08:00 Africa/Cairo")

    def test_parse_schedule_error_names_cairo(self):
        with self.assertRaises(publish.PublishError) as ctx:
            publish.parse_schedule("27/11/2026 08:00", now=0)
        self.assertIn("Africa/Cairo", str(ctx.exception))

    def test_parse_schedule_uses_cairo_not_system_time(self):
        # 08:00 قاهرة شتاءً = 06:00 UTC — لا 08:00 UTC.
        epoch = publish.parse_schedule("2026-11-27 08:00", now=0)
        as_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)
        self.assertEqual((as_utc.hour, as_utc.minute), (6, 0))

    def test_now_cairo_iso_helpers_are_cairo_aware(self):
        for module in (job_registry, manifest_lib):
            stamp = module.now_cairo_iso()
            parsed = datetime.fromisoformat(stamp)
            self.assertIsNotNone(parsed.tzinfo, module.__name__)
            # الإزاحة تساوي إزاحة القاهرة في اللحظة نفسها.
            self.assertEqual(
                parsed.utcoffset(),
                datetime.now(tz=CAIRO).utcoffset(),
                module.__name__)

    def test_balance_now_iso_cairo_pins_winter_offset(self):
        stamp = balance_lib.now_iso_cairo(
            now=datetime(2026, 11, 27, 8, 0))
        self.assertIn("08:00", stamp)
        self.assertTrue(stamp.endswith("+02:00"), stamp)

    def test_balance_now_iso_cairo_pins_summer_offset(self):
        stamp = balance_lib.now_iso_cairo(
            now=datetime(2026, 7, 15, 8, 0))
        self.assertTrue(stamp.endswith("+03:00"), stamp)


class TestCairoOffsets(unittest.TestCase):
    """إزاحتا القاهرة (شتاءً +02:00 وصيفًا +03:00) عبر ZoneInfo —
    لا قيمة مكتوبة يدويًا."""

    def test_winter_offset_is_plus_two(self):
        noon = datetime(2026, 1, 15, 12, 0, tzinfo=CAIRO)
        self.assertEqual(noon.utcoffset(), timedelta(hours=2))

    def test_summer_offset_is_plus_three(self):
        noon = datetime(2026, 7, 15, 12, 0, tzinfo=CAIRO)
        self.assertEqual(noon.utcoffset(), timedelta(hours=3))

    def test_november_morning_is_winter(self):
        morning = datetime(2026, 11, 27, 8, 0, tzinfo=CAIRO)
        self.assertEqual(morning.utcoffset(), timedelta(hours=2))


class TestMorningBriefTime(unittest.TestCase):
    """موعد الصباح 08:00 Africa/Cairo (بند 34 — عقد ع19)."""

    def test_first_run_constants(self):
        self.assertEqual(lic.FIRST_RUN_TIMEZONE, "Africa/Cairo")
        self.assertEqual(lic.FIRST_RUN_MORNING_TIME, "08:00")

    def test_morning_brief_08_cairo_is_06_utc_in_winter(self):
        morning = datetime(2026, 11, 27, 8, 0, tzinfo=CAIRO)
        as_utc = morning.astimezone(timezone.utc)
        self.assertEqual((as_utc.hour, as_utc.minute), (6, 0))
        self.assertEqual(as_utc.tzinfo, timezone.utc)

    def test_cairo_timezone_name_is_stable(self):
        self.assertEqual(CAIRO.key, "Africa/Cairo")
        self.assertEqual(publish.CAIRO_TZ_NAME, "Africa/Cairo")
        self.assertEqual(job_registry.CAIRO.key, "Africa/Cairo")
        self.assertEqual(manifest_lib.CAIRO.key, "Africa/Cairo")


if __name__ == "__main__":
    unittest.main()
