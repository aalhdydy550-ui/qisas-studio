#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات قارئ تصدير الاحتفاظ — CSV تركيبية مسماة كذلك، بلا شبكة."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import retention_read
from lib.retention_read import RetentionError, format_report, read_retention


def synthetic_csv(points, time_fmt="seconds", retention_fmt="percent",
                  header=("Time (seconds)", "Audience retention")):
    """بناء CSV تركيبي من قائمة [(ثوانٍ، احتفاظ %)] — للاختبار فقط."""
    lines = []
    if header is not None:
        lines.append(",".join(header))
    for t, v in points:
        if time_fmt == "mm:ss":
            t_text = "%d:%02d" % (int(t) // 60, int(t) % 60)
        else:
            t_text = str(t)
        if retention_fmt == "percent_sign":
            v_text = "%s%%" % v
        elif retention_fmt == "fraction":
            v_text = str(v / 100.0)
        else:
            v_text = str(v)
        lines.append("%s,%s" % (t_text, v_text))
    return "\n".join(lines) + "\n"


# منحنى سليم: تسرب هوك 12%، بلا منحدرات، وسط مسطح.
HEALTHY_POINTS = [(0, 100), (5, 97), (10, 95), (15, 93), (20, 91),
                  (25, 90), (30, 88), (35, 87), (40, 86), (45, 85),
                  (50, 84), (55, 83), (60, 82)]
# تسرب هوك غير صحي: 100 -> 55 عند الثانية 30، بلا قفزات حادة.
BAD_HOOK_POINTS = [(0, 100), (5, 92), (10, 84), (15, 76), (20, 68),
                   (25, 61), (30, 55), (35, 54), (40, 53), (45, 52),
                   (50, 51), (55, 50), (60, 50)]
# منحدر واحد عند الثانية 45 (86 -> 71)، والهوك سليم (12% عند 30).
CLIFF_POINTS = [(0, 100), (5, 97), (10, 95), (15, 93), (20, 91),
                (25, 90), (30, 88), (35, 87), (40, 86), (45, 71),
                (50, 70), (55, 69), (60, 68)]
# انزلاق: وسط (20-40) ينزف 90 -> 66 بلا قفزات، والهوك سليم (22%).
SLIDE_POINTS = [(0, 100), (5, 98), (10, 96), (15, 94), (20, 90),
                (25, 84), (30, 78), (35, 72), (40, 66), (45, 65),
                (50, 64), (55, 63), (60, 62)]

SRT_TRANSCRIPT = """1
00:00:00,000 --> 00:00:10,000
كان يا ما كان في قرية بعيدة

2
00:00:10,000 --> 00:00:19,000
عاش رجل فقير يعمل في السوق

3
00:00:19,000 --> 00:00:28,000
سار الرجل في السوق يبحث عن رزقه

4
00:00:28,000 --> 00:00:40,000
عاد إلى بيته متعبًا وجلس يستريح

5
00:00:40,000 --> 00:00:50,000
وفي يوم جاءه ضيف غريب يطلب الماء
"""

ASS_TRANSCRIPT = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:10.00,Default,,0,0,0,,كان يا ما كان في قرية بعيدة
Dialogue: 0,0:00:10.00,0:00:19.00,Default,,0,0,0,,عاش رجل فقير يعمل في السوق
Dialogue: 0,0:00:19.00,0:00:28.00,Default,,0,0,0,,سار الرجل في السوق يبحث عن رزقه
Dialogue: 0,0:00:28.00,0:00:40.00,Default,,0,0,0,,عاد إلى بيته متعبًا وجلس يستريح
Dialogue: 0,0:00:40.00,0:00:50.00,Default,,0,0,0,,وفي يوم جاءه ضيف غريب يطلب الماء
"""


class TestHookLeak(unittest.TestCase):
    def test_healthy_hook_leak(self):
        res = read_retention(synthetic_csv(HEALTHY_POINTS))
        self.assertAlmostEqual(res["hook_leak_pct"], 12.0)
        self.assertTrue(res["healthy"])
        self.assertEqual(res["verdict"], "سليم")

    def test_unhealthy_hook_leak(self):
        res = read_retention(synthetic_csv(BAD_HOOK_POINTS))
        self.assertAlmostEqual(res["hook_leak_pct"], 45.0)
        self.assertFalse(res["healthy"])
        self.assertEqual(res["verdict"], "تسرب الهوك")
        self.assertIn("أول 15 ثانية", res["fix"])

    def test_hook_leak_boundary_25_is_unhealthy(self):
        points = [(0, 100), (10, 90), (20, 80), (30, 75), (40, 74),
                  (50, 73), (60, 72)]
        res = read_retention(synthetic_csv(points))
        self.assertAlmostEqual(res["hook_leak_pct"], 25.0)
        self.assertFalse(res["healthy"])


class TestCliffs(unittest.TestCase):
    def test_single_cliff_with_srt_transcript(self):
        res = read_retention(synthetic_csv(CLIFF_POINTS),
                             transcript_text=SRT_TRANSCRIPT)
        self.assertEqual(len(res["cliffs"]), 1)
        cliff = res["cliffs"][0]
        self.assertAlmostEqual(cliff["at_seconds"], 45.0)
        self.assertAlmostEqual(cliff["drop"], 15.0)
        self.assertIn("ضيف غريب", cliff["said"])
        self.assertEqual(res["verdict"], "منحدر")
        self.assertIn("الثانية 45", res["fix"])
        self.assertIn("ضيف غريب", res["fix"])

    def test_single_cliff_with_ass_transcript(self):
        res = read_retention(synthetic_csv(CLIFF_POINTS),
                             transcript_text=ASS_TRANSCRIPT)
        self.assertEqual(len(res["cliffs"]), 1)
        self.assertIn("ضيف غريب", res["cliffs"][0]["said"])

    def test_cliff_without_transcript_has_no_said(self):
        res = read_retention(synthetic_csv(CLIFF_POINTS))
        self.assertEqual(len(res["cliffs"]), 1)
        self.assertNotIn("said", res["cliffs"][0])

    def test_small_steps_are_not_cliffs(self):
        res = read_retention(synthetic_csv(BAD_HOOK_POINTS))
        self.assertEqual(res["cliffs"], [])


class TestSlide(unittest.TestCase):
    def test_slide_verdict(self):
        res = read_retention(synthetic_csv(SLIDE_POINTS))
        self.assertLess(res["slide"], 0)
        self.assertGreaterEqual(res["slide_total_pct"], 8.0)
        self.assertEqual(res["verdict"], "انزلاق")
        self.assertIn("قصّ", res["fix"])

    def test_flat_middle_is_not_slide(self):
        res = read_retention(synthetic_csv(HEALTHY_POINTS))
        self.assertLess(res["slide_total_pct"], 8.0)
        self.assertNotEqual(res["verdict"], "انزلاق")


class TestHealthyVideo(unittest.TestCase):
    def test_healthy_video_packaging_note(self):
        res = read_retention(synthetic_csv(HEALTHY_POINTS))
        self.assertTrue(res["healthy"])
        self.assertEqual(res["verdict"], "سليم")
        self.assertIsNotNone(res["packaging_note"])
        self.assertIn("التغليف", res["packaging_note"])
        self.assertIn("العنوان", res["packaging_note"])
        self.assertIsNone(read_retention(
            synthetic_csv(BAD_HOOK_POINTS))["packaging_note"])


class TestCsvFormats(unittest.TestCase):
    def test_mmss_time_and_percent_sign(self):
        csv_text = synthetic_csv(HEALTHY_POINTS, time_fmt="mm:ss",
                                 retention_fmt="percent_sign")
        res = read_retention(csv_text)
        self.assertAlmostEqual(res["hook_leak_pct"], 12.0)
        self.assertTrue(res["healthy"])

    def test_fraction_retention(self):
        csv_text = synthetic_csv(HEALTHY_POINTS, retention_fmt="fraction")
        res = read_retention(csv_text)
        self.assertAlmostEqual(res["hook_leak_pct"], 12.0)

    def test_headerless_two_columns(self):
        csv_text = synthetic_csv(HEALTHY_POINTS, header=None)
        res = read_retention(csv_text)
        self.assertAlmostEqual(res["hook_leak_pct"], 12.0)

    def test_arabic_header_names(self):
        csv_text = synthetic_csv(
            HEALTHY_POINTS, header=("الوقت", "احتفاظ الجمهور"))
        res = read_retention(csv_text)
        self.assertAlmostEqual(res["hook_leak_pct"], 12.0)

    def test_semicolon_delimiter(self):
        csv_text = synthetic_csv(HEALTHY_POINTS).replace(",", ";")
        res = read_retention(csv_text)
        self.assertAlmostEqual(res["hook_leak_pct"], 12.0)

    def test_csv_from_file_path(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv",
                                         delete=False,
                                         encoding="utf-8") as fh:
            fh.write(synthetic_csv(HEALTHY_POINTS))
            path = fh.name
        try:
            res = read_retention(path)
            self.assertAlmostEqual(res["hook_leak_pct"], 12.0)
        finally:
            os.unlink(path)

    def test_explicit_duration(self):
        res = read_retention(synthetic_csv(SLIDE_POINTS), duration=60)
        self.assertEqual(res["duration_seconds"], 60)
        self.assertEqual(res["verdict"], "انزلاق")


class TestErrors(unittest.TestCase):
    def test_missing_file_arabic_error(self):
        with self.assertRaises(RetentionError) as ctx:
            read_retention("/tmp/no-such-retention-export-xyz.csv")
        self.assertIn("غير موجود", str(ctx.exception))

    def test_empty_csv_arabic_error(self):
        with self.assertRaises(RetentionError) as ctx:
            read_retention("")
        self.assertIn("فارغ", str(ctx.exception))

    def test_no_valid_columns_arabic_error(self):
        with self.assertRaises(RetentionError) as ctx:
            read_retention("اسم,مدينة\nأحمد,القاهرة\nمحمد,الجيزة\n")
        self.assertIn("أعمدة صالحة", str(ctx.exception))

    def test_single_point_arabic_error(self):
        with self.assertRaises(RetentionError):
            read_retention("Time (seconds),Audience retention\n0,100\n")


class TestFormatReport(unittest.TestCase):
    def test_report_healthy_arabic(self):
        res = read_retention(synthetic_csv(HEALTHY_POINTS))
        report = format_report(res)
        self.assertIn("تسرب الهوك", report)
        self.assertIn("صحي", report)
        self.assertIn("سليم", report)
        self.assertIn("التغليف", report)

    def test_report_cliff_arabic_with_said(self):
        res = read_retention(synthetic_csv(CLIFF_POINTS),
                             transcript_text=SRT_TRANSCRIPT)
        report = format_report(res)
        self.assertIn("المنحدرات", report)
        self.assertIn("ضيف غريب", report)
        self.assertIn("منحدر", report)


if __name__ == "__main__":
    unittest.main()
