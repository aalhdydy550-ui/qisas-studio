#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات كلمات اليوم الطازجة — جولة v0.1.61 (W6).

الأرقام المرجعية من بيانات الاستوديو المقاسة (أمثلة لا
بيانات حية): «قصص واقعية» نمو +92.6%، و«قصص غموض»
نمو +84.8% (مستبعدة رغم نموها). باقي البيانات تركيبية
لأغراض الاختبار فقط، وكل الاختبارات تمرّر today صريحًا
للحتمية.
"""
import json
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import fresh_keywords
from lib.fresh_keywords import (
    STATUS_CANDIDATE,
    STATUS_EXCLUDED,
    TRENDING_LABEL,
    format_report,
    fresh_keywords as fresh,
    is_horror_keyword,
    load_trends_json,
    to_json,
)

TODAY = "2026-11-26"


def _trend(keyword, growth_pct=None, volume=None, day="2026-11-26",
           source="vidIQ"):
    """مدخل ترند — الكلمة والتاريخ إلزاميان، والباقي اختياري."""
    entry = {"keyword": keyword, "date": day, "source": source}
    if growth_pct is not None:
        entry["growth_pct"] = growth_pct
    if volume is not None:
        entry["volume"] = volume
    return entry


class TestHappyPath(unittest.TestCase):
    def test_happy_path_explicit_today(self):
        result = fresh([
            _trend("قصص واقعية", 92.6, 100_000),
            _trend("قصص الصدقة", 40.0, 10_000),
        ], today=TODAY)
        self.assertEqual(result["today"], TODAY)
        self.assertEqual(result["days"], 7)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["fresh_count"], 2)
        self.assertEqual(result["stale"], [])
        first = result["keywords"][0]
        self.assertEqual(first["keyword"], "قصص واقعية")
        # النمو: 70×92.6/200 = 32.4؛ الحجم: 30×log10(100001)/log10(1000001) = 25.0
        self.assertEqual(first["score"], 57.4)
        self.assertEqual(first["growth_text"], "+92.6%")
        self.assertEqual(first["status"], STATUS_CANDIDATE)
        second = result["keywords"][1]
        # النمو: 70×40/200 = 14.0؛ الحجم: 30×log10(10001)/log10(1000001) = 20.0
        self.assertEqual(second["score"], 34.0)

    def test_today_as_date_object(self):
        result = fresh([_trend("قصص واقعية", 92.6, 100_000)],
                       today=date(2026, 11, 26))
        self.assertEqual(result["today"], "2026-11-26")
        self.assertEqual(result["total"], 1)

    def test_days_boundary_exactly_fresh(self):
        result = fresh([
            _trend("على الحد", 10.0, day="2026-11-19"),
            _trend("أقدم بيوم", 10.0, day="2026-11-18"),
        ], days=7, today=TODAY)
        self.assertEqual([e["keyword"] for e in result["keywords"]],
                         ["على الحد"])
        self.assertEqual(len(result["stale"]), 1)
        self.assertEqual(result["stale"][0]["keyword"], "أقدم بيوم")

    def test_score_caps_at_100(self):
        result = fresh([_trend("انفجار", 300.0, 10_000_000)], today=TODAY)
        self.assertEqual(result["keywords"][0]["score"], 100.0)

    def test_negative_growth_counts_as_zero(self):
        result = fresh([_trend("هابطة", -20.0, 0)], today=TODAY)
        entry = result["keywords"][0]
        self.assertEqual(entry["score"], 0.0)
        self.assertEqual(entry["growth_text"], "-20.0%")
        self.assertFalse(entry["trending_today"])


class TestStaleAndUnknown(unittest.TestCase):
    def test_old_entry_in_stale_with_reason(self):
        result = fresh([
            _trend("قصص واقعية", 92.6, day="2026-11-26"),
            _trend("قديمة", 80.0, day="2026-11-10"),
        ], days=7, today=TODAY)
        self.assertEqual(len(result["keywords"]), 1)
        self.assertEqual(len(result["stale"]), 1)
        stale = result["stale"][0]
        self.assertEqual(stale["keyword"], "قديمة")
        self.assertEqual(stale["age_days"], 16)
        self.assertIn("أقدم من 7 أيام", stale["reason"])
        self.assertIn("16", stale["reason"])

    def test_unknown_growth_unmeasured(self):
        result = fresh([
            _trend("بلا نمو", volume=1_000_000),
            _trend("مقاسة", 0.0, volume=1_000_000),
        ], today=TODAY)
        entries = {e["keyword"]: e for e in result["keywords"]}
        unknown = entries["بلا نمو"]
        self.assertIsNone(unknown["growth_pct"])
        self.assertEqual(unknown["growth_text"], "غير مقاس")
        self.assertEqual(unknown["score"], 30.0)
        self.assertIn("غير مقاس", unknown["reason"])
        self.assertFalse(unknown["trending_today"])
        # تساوي الدرجة (30.0): المقاسة قبل غير المقاسة.
        self.assertEqual(result["keywords"][0]["keyword"], "مقاسة")
        self.assertEqual(result["keywords"][1]["keyword"], "بلا نمو")

    def test_unknown_volume_unmeasured(self):
        result = fresh([_trend("بلا حجم", 100.0)], today=TODAY)
        entry = result["keywords"][0]
        self.assertIsNone(entry["volume"])
        self.assertEqual(entry["score"], 35.0)
        self.assertIn("غير مقاس", entry["reason"])

    def test_sort_by_growth_then_keyword(self):
        result = fresh([
            _trend("باء", 60.0, 10_000),
            _trend("ألف", 60.0, 10_000),
            _trend("جيم", 80.0, 10_000),
        ], today=TODAY)
        self.assertEqual([e["keyword"] for e in result["keywords"]],
                         ["جيم", "ألف", "باء"])


class TestTrendingAndHorror(unittest.TestCase):
    def test_trending_today_at_50_pct(self):
        result = fresh([
            _trend("عند الحد", 50.0),
            _trend("تحت الحد", 49.9),
            _trend("فوق الحد", 120.0),
        ], today=TODAY)
        flags = {e["keyword"]: e["trending_today"]
                 for e in result["keywords"]}
        self.assertTrue(flags["عند الحد"])
        self.assertFalse(flags["تحت الحد"])
        self.assertTrue(flags["فوق الحد"])
        labels = {e["keyword"]: e["label"] for e in result["keywords"]}
        self.assertEqual(labels["عند الحد"], TRENDING_LABEL)
        self.assertEqual(labels["تحت الحد"], "")

    def test_horror_keyword_excluded(self):
        self.assertTrue(is_horror_keyword("قصص رعب"))
        self.assertTrue(is_horror_keyword("قصص غموض"))
        self.assertFalse(is_horror_keyword("قصص واقعية"))
        self.assertFalse(is_horror_keyword("قصص الجنة"))
        result = fresh([
            _trend("قصص غموض", 84.8, 500_000),
            _trend("قصص واقعية", 92.6, 100_000),
        ], today=TODAY)
        mystery = [e for e in result["keywords"]
                   if e["keyword"] == "قصص غموض"][0]
        self.assertEqual(mystery["status"], STATUS_EXCLUDED)
        # النمو: 70×84.8/200 = 29.7؛ الحجم: 30×log10(500001)/log10(1000001) = 28.5
        self.assertEqual(mystery["score"], 58.2)
        self.assertEqual(result["excluded"], ["قصص غموض"])
        self.assertEqual([e["keyword"] for e in result["suggestions"]],
                         ["قصص واقعية"])


class TestValidation(unittest.TestCase):
    def test_empty_list(self):
        with self.assertRaises(ValueError) as ctx:
            fresh([], today=TODAY)
        self.assertIn("فارغة", str(ctx.exception))

    def test_empty_keyword(self):
        with self.assertRaises(ValueError):
            fresh([_trend("   ", 10.0)], today=TODAY)
        with self.assertRaises(ValueError):
            fresh([{"date": "2026-11-26"}], today=TODAY)

    def test_invalid_dates(self):
        for bad in ("2026-13-01", "2026-02-30", "26/11/2026",
                    "2026-11-26T10:00", "", 20261126):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    fresh([_trend("كلمة", 10.0, day=bad)], today=TODAY)

    def test_invalid_today(self):
        with self.assertRaises(ValueError):
            fresh([_trend("كلمة", 10.0)], today="أمس")
        with self.assertRaises(ValueError):
            fresh([_trend("كلمة", 10.0)], today="2026-02-30")

    def test_missing_date(self):
        with self.assertRaises(ValueError):
            fresh([{"keyword": "بلا تاريخ", "growth_pct": 10.0}],
                  today=TODAY)

    def test_bad_numbers(self):
        with self.assertRaises(ValueError):
            fresh([_trend("كلمة", "كثير")], today=TODAY)
        with self.assertRaises(ValueError):
            fresh([_trend("كلمة", 10.0, volume=-5)], today=TODAY)
        with self.assertRaises(ValueError):
            fresh([_trend("كلمة", 10.0)], days=0, today=TODAY)

    def test_load_trends_json_errors(self):
        with self.assertRaises(ValueError):
            load_trends_json("{not json")
        with self.assertRaises(ValueError):
            load_trends_json('{"keyword": "كلمة"}')
        with self.assertRaises(ValueError):
            load_trends_json("[]")
        loaded = load_trends_json(
            '[{"keyword": "قصص واقعية", "growth_pct": 92.6, '
            '"date": "2026-11-26"}]')
        self.assertEqual(loaded[0]["keyword"], "قصص واقعية")
        self.assertEqual(loaded[0]["date"], date(2026, 11, 26))


class TestOutput(unittest.TestCase):
    def test_to_json_round_trip(self):
        result = fresh([_trend("قصص واقعية", 92.6, 100_000)],
                       today=TODAY)
        text = to_json(result)
        self.assertTrue(text.endswith("\n"))
        # عربي بلا ASCII هارب.
        self.assertIn("قصص واقعية", text)
        self.assertNotIn("\\u", text)
        parsed = json.loads(text)
        self.assertEqual(parsed["keywords"][0]["score"], 57.4)
        self.assertEqual(json.loads(to_json(result))["today"], TODAY)

    def test_format_report_arabic(self):
        result = fresh([
            _trend("قصص واقعية", 92.6, 100_000),
            _trend("بلا نمو", volume=1_000),
            _trend("قصص غموض", 84.8, 500_000),
            _trend("قديمة", 80.0, day="2026-11-10"),
        ], today=TODAY)
        report = format_report(result)
        self.assertIn("كلمات اليوم الطازجة", report)
        self.assertIn("رائج اليوم", report)
        self.assertIn("غير مقاس", report)
        self.assertIn("مستبعد", report)
        self.assertIn("قديمة", report)
        self.assertIn("لا أرقام مخترعة", report)
        self.assertIn("لا يُقترح أبدًا", report)

    def test_reference_examples_in_docstring_and_result(self):
        self.assertIn("قصص واقعية", fresh_keywords.__doc__)
        self.assertIn("+92.6%", fresh_keywords.__doc__)
        self.assertIn("قصص غموض", fresh_keywords.__doc__)
        self.assertIn("+84.8%", fresh_keywords.__doc__)
        result = fresh([_trend("قصص واقعية", 92.6)], today=TODAY)
        examples = result["reference"]["examples"]
        self.assertEqual(examples[0]["growth_pct"], 92.6)
        self.assertEqual(examples[1]["keyword"], "قصص غموض")


if __name__ == "__main__":
    unittest.main()
