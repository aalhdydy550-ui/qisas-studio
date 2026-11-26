#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات فحص مقروئية الكابشن — بلا نشر وبلا شبكة."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_readability


def _dlg(start, end, text, style="Default"):
    return f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}"


def _ass(*lines):
    header = (
        "[Script Info]\n"
        "Title: test\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    return header + "\n".join(lines) + "\n"


# أعداد الحروف محسوبة يدويًا (شاملة المسافات):
# «قصة قصيرة» = 9، «قصة قصيرة جدا» = 13، «هذا نص عربي طويل» = 16،
# «هذا نص عربي هنا» = 15، «هذا نص عربي طويلا» = 17.
class TestAnalyzeAssText(unittest.TestCase):
    def test_clean_phrase(self):
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:01.00", "0:00:03.00", "قصة قصيرة")))
        self.assertEqual(report["total"], 1)
        self.assertEqual(len(report["flashing"]), 0)
        self.assertEqual(len(report["borderline"]), 0)
        phrase = report["phrases"][0]
        self.assertEqual(phrase["text"], "قصة قصيرة")
        self.assertAlmostEqual(phrase["cps"], 4.5)
        self.assertAlmostEqual(phrase["cps_no_spaces"], 4.0)
        self.assertAlmostEqual(phrase["start"], 1.0)
        self.assertAlmostEqual(phrase["end"], 3.0)
        self.assertAlmostEqual(report["max_cps"], 4.5)
        self.assertAlmostEqual(report["median_cps"], 4.5)

    def test_flashing_phrase(self):
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:01.00", "0:00:01.50", "قصة قصيرة جدا")))
        self.assertEqual(report["total"], 1)
        self.assertEqual(len(report["flashing"]), 1)
        self.assertEqual(len(report["borderline"]), 0)
        self.assertAlmostEqual(report["phrases"][0]["cps"], 26.0)
        self.assertAlmostEqual(report["max_cps"], 26.0)

    def test_borderline_phrase(self):
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:01.00", "0:00:02.00", "هذا نص عربي طويل")))
        self.assertEqual(report["total"], 1)
        self.assertEqual(len(report["flashing"]), 0)
        self.assertEqual(len(report["borderline"]), 1)
        self.assertAlmostEqual(report["phrases"][0]["cps"], 16.0)

    def test_exactly_15_cps_is_clean_not_borderline(self):
        # 15.0 بالضبط سليمة: الحدّية تبدأ فوق 15 (مطابق لسكربت المرجع).
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:01.00", "0:00:02.00", "هذا نص عربي هنا")))
        self.assertAlmostEqual(report["phrases"][0]["cps"], 15.0)
        self.assertEqual(len(report["flashing"]), 0)
        self.assertEqual(len(report["borderline"]), 0)

    def test_exactly_17_cps_is_borderline_not_flashing(self):
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:01.00", "0:00:02.00", "هذا نص عربي طويلا")))
        self.assertAlmostEqual(report["phrases"][0]["cps"], 17.0)
        self.assertEqual(len(report["flashing"]), 0)
        self.assertEqual(len(report["borderline"]), 1)

    def test_override_tags_stripped_before_counting(self):
        report = caption_readability.analyze_ass_text(_ass(
            _dlg("0:00:01.00", "0:00:03.00",
                 "{\\pos(100,200)}قصة قصيرة"),
            _dlg("0:00:03.00", "0:00:05.00",
                 "{\\i1}قصة{\\i0} قصيرة"),
        ))
        self.assertEqual(report["total"], 2)
        for phrase in report["phrases"]:
            self.assertEqual(phrase["text"], "قصة قصيرة")
            self.assertAlmostEqual(phrase["cps"], 4.5)

    def test_line_break_is_a_space_not_two_chars(self):
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:01.00", "0:00:03.00", "قصة\\Nقصيرة")))
        self.assertEqual(report["phrases"][0]["text"], "قصة قصيرة")
        self.assertAlmostEqual(report["phrases"][0]["cps"], 4.5)

    def test_corrupt_lines_skipped_silently(self):
        report = caption_readability.analyze_ass_text(_ass(
            "Dialogue: garbage",
            "Dialogue: 0,not-a-time,0:00:02.00,Default,,0,0,0,,نص",
            "Dialogue: 0,0:00:01.00",
            "Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,تعليق",
            "سطر عشوائي بلا معنى",
            _dlg("0:00:01.00", "0:00:03.00", "قصة قصيرة"),
        ))
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["phrases"][0]["text"], "قصة قصيرة")

    def test_zero_negative_duration_and_empty_text_skipped(self):
        report = caption_readability.analyze_ass_text(_ass(
            _dlg("0:00:01.00", "0:00:01.00", "قصة قصيرة"),
            _dlg("0:00:03.00", "0:00:01.00", "قصة قصيرة"),
            _dlg("0:00:01.00", "0:00:03.00", ""),
            _dlg("0:00:01.00", "0:00:03.00", "{\\i1}"),
            _dlg("0:00:05.00", "0:00:07.00", "قصة قصيرة"),
        ))
        self.assertEqual(report["total"], 1)
        self.assertAlmostEqual(report["phrases"][0]["start"], 5.0)

    def test_empty_file_report(self):
        report = caption_readability.analyze_ass_text(
            "[Script Info]\nTitle: test\n")
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["phrases"], [])
        self.assertEqual(report["flashing"], [])
        self.assertEqual(report["borderline"], [])
        self.assertEqual(report["max_cps"], 0.0)
        self.assertEqual(report["median_cps"], 0.0)

    def test_arabic_rtl_text_preserved(self):
        text = "قال الرجل لزوجته: اصبري يا أم أحمد"
        report = caption_readability.analyze_ass_text(
            _ass(_dlg("0:00:00.00", "0:00:04.00", text)))
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["phrases"][0]["text"], text)
        self.assertAlmostEqual(
            report["phrases"][0]["cps"], len(text) / 4.0)

    def test_median_and_max(self):
        report = caption_readability.analyze_ass_text(_ass(
            _dlg("0:00:01.00", "0:00:03.00", "قصة قصيرة"),
            _dlg("0:00:03.00", "0:00:04.00", "هذا نص عربي طويل"),
            _dlg("0:00:04.00", "0:00:04.50", "قصة قصيرة جدا"),
        ))
        self.assertEqual(report["total"], 3)
        self.assertAlmostEqual(report["max_cps"], 26.0)
        self.assertAlmostEqual(report["median_cps"], 16.0)

    def test_median_even_count(self):
        report = caption_readability.analyze_ass_text(_ass(
            _dlg("0:00:01.00", "0:00:03.00", "قصة قصيرة"),
            _dlg("0:00:03.00", "0:00:05.00", "هذا نص عربي طويل"),
            _dlg("0:00:05.00", "0:00:06.00", "هذا نص عربي طويل"),
            _dlg("0:00:06.00", "0:00:06.50", "قصة قصيرة جدا"),
        ))
        # السرعات 4.5 و8.0 و16.0 و26.0 — الوسيط (8.0+16.0)/2.
        self.assertAlmostEqual(report["median_cps"], 12.0)


class TestAnalyzeAssFile(unittest.TestCase):
    def test_file_round_trip(self):
        content = _ass(
            _dlg("0:00:01.00", "0:00:03.00", "قصة قصيرة"),
            _dlg("0:00:03.00", "0:00:03.50", "قصة قصيرة جدا"),
        )
        with tempfile.NamedTemporaryFile(
                "w", suffix=".ass", encoding="utf-8",
                delete=False) as f:
            f.write(content)
            path = f.name
        try:
            report = caption_readability.analyze_ass_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(report["total"], 2)
        self.assertEqual(len(report["flashing"]), 1)
        self.assertEqual(report["flashing"][0]["text"], "قصة قصيرة جدا")

    def test_file_without_phrases(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".ass", encoding="utf-8",
                delete=False) as f:
            f.write("[Script Info]\nTitle: empty\n")
            path = f.name
        try:
            report = caption_readability.analyze_ass_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["max_cps"], 0.0)


class TestFormatReport(unittest.TestCase):
    def test_summary_and_flashing_lines(self):
        report = caption_readability.analyze_ass_text(_ass(
            _dlg("0:00:01.00", "0:00:03.00", "قصة قصيرة"),
            _dlg("0:00:03.00", "0:00:03.50", "قصة قصيرة جدا"),
        ))
        out = caption_readability.format_report(report)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("2 عبارة", lines[0])
        self.assertIn("وامضة", lines[0])
        self.assertIn("قصة قصيرة جدا", lines[1])
        self.assertIn("26.0", lines[1])
        self.assertIn("0:00:03.00", lines[1])
        self.assertIn("0:00:03.50", lines[1])

    def test_empty_report_is_one_line(self):
        report = caption_readability.analyze_ass_text("")
        out = caption_readability.format_report(report)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("0 عبارة", out)

    def test_threshold_constants(self):
        self.assertEqual(caption_readability.FLASH_CPS, 17.0)
        self.assertEqual(caption_readability.BORDERLINE_CPS, 15.0)


if __name__ == "__main__":
    unittest.main()
