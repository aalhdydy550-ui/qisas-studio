#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات محلّل الكلمات المفتاحية — جولة v0.1.61 (W1).

الأرقام الحقيقية هنا من مرجع المعايرة في
``lib/keyword_analyze.py`` (بيانات vidIQ المقاسة 2026-11-26):
«قصص» حجم ~483,574 ومنافسة 59؛ «قصص واقعية» 39,618 ونمو
+92.6% ومنافسة 40؛ «قصص اطفال» 75,888 ومنافسة 32. باقي
البيانات تركيبية لأغراض الاختبار فقط.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import keyword_analyze
from lib.keyword_analyze import (
    CALIBRATION_EXAMPLES,
    COMPETITION_HIGH,
    COMPETITION_LOW,
    COMPETITION_MEDIUM,
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MEDIUM,
    UNMEASURED,
    VERDICT_AVOID,
    VERDICT_CAREFUL,
    VERDICT_TARGET,
    VERDICT_UNKNOWN,
    analyze_keyword,
    analyze_keywords,
    format_report,
    load_keyword_json,
    load_keywords_json,
    to_json,
)


def _serp(matches, total=10, authority=50):
    """نتائج SERP تركيبية: أول matches بمطابقة عنوان وسلطة ثابتة."""
    return [
        {"domain": f"example{i}.com", "title_match": i < matches,
         "authority": authority}
        for i in range(total)
    ]


class TestHappyPath(unittest.TestCase):
    def test_full_metrics(self):
        # منافسة 59 + قوة SERP (6/10 × 50 = 30.0)
        # → صعوبة 0.6×59 + 0.4×30 = 47.4
        result = analyze_keyword("قصص", {
            "volume": 483574, "competition": 59, "growth_pct": 5.0,
            "serp": _serp(6),
        })
        self.assertEqual(result["keyword"], "قصص")
        self.assertEqual(result["volume"], 483574)
        self.assertEqual(result["serp_strength"], 30.0)
        self.assertEqual(result["title_match_count"], 6)
        self.assertEqual(result["serp_count"], 10)
        self.assertEqual(result["avg_authority"], 50)
        self.assertTrue(result["serp_measured"])
        self.assertEqual(result["difficulty"], 47.4)
        self.assertEqual(result["difficulty_label"], DIFFICULTY_MEDIUM)
        self.assertEqual(result["competition_label"], COMPETITION_MEDIUM)
        self.assertEqual(result["verdict"], VERDICT_CAREFUL)
        self.assertIn("47.4", result["reason"])
        self.assertIn("59", result["reason"])

    def test_calibration_examples_vidiq(self):
        # أمثلة المعايرة (بلا SERP → جزء SERP صفر):
        # قصص: 0.6×59=35.4؛ واقعية: 0.6×40=24.0؛ اطفال: 0.6×32=19.2
        expected = [
            ("قصص", 35.4, DIFFICULTY_MEDIUM, VERDICT_TARGET),
            ("قصص واقعية", 24.0, DIFFICULTY_EASY, VERDICT_TARGET),
            ("قصص اطفال", 19.2, DIFFICULTY_EASY, VERDICT_TARGET),
        ]
        for example, (keyword, difficulty, label, verdict) in zip(
                CALIBRATION_EXAMPLES, expected):
            with self.subTest(keyword=keyword):
                result = analyze_keyword(example["keyword"], {
                    "volume": example["volume"],
                    "competition": example["competition"],
                    "growth_pct": example.get("growth_pct"),
                })
                self.assertEqual(result["difficulty"], difficulty)
                self.assertEqual(result["difficulty_label"], label)
                self.assertEqual(result["verdict"], verdict)
                self.assertFalse(result["serp_measured"])
        growth = analyze_keyword("قصص واقعية", {
            "volume": 39618, "growth_pct": 92.6, "competition": 40})
        self.assertEqual(growth["growth_pct"], 92.6)
        self.assertIn("+92.6%", growth["reason"])


class TestBoundaries(unittest.TestCase):
    def test_difficulty_easy_medium_boundary(self):
        # منافسة 50 بلا SERP → صعوبة 30.0 → متوسطة (لا سهلة)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 50})["difficulty_label"],
            DIFFICULTY_MEDIUM)
        # منافسة 49 بلا SERP → صعوبة 29.4 → سهلة
        self.assertEqual(
            analyze_keyword("أ", {"competition": 49})["difficulty_label"],
            DIFFICULTY_EASY)

    def test_difficulty_hard_boundary(self):
        # منافسة 100 + قوة SERP ‏100 → صعوبة 100 → صعبة وتجنّب
        result = analyze_keyword("أ", {
            "competition": 100, "serp": _serp(10, authority=100)})
        self.assertEqual(result["difficulty"], 100.0)
        self.assertEqual(result["difficulty_label"], DIFFICULTY_HARD)
        self.assertEqual(result["verdict"], VERDICT_AVOID)

    def test_verdict_boundaries(self):
        # صعوبة 39.9 → استهدف؛ 40.0 → نافس بحذر (بلا SERP)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 66.5})["verdict"],
            VERDICT_TARGET)  # 0.6×66.5 = 39.9
        careful = analyze_keyword("أ", {"competition": 66.7})
        self.assertEqual(careful["difficulty"], 40.0)
        self.assertEqual(careful["verdict"], VERDICT_CAREFUL)
        # صعوبة 64.8 → نافس بحذر؛ 65.0 → تجنب (منافسة 100 + SERP ‏25)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 100,
                                 "serp": _serp(5, authority=50)})["difficulty"],
            70.0)
        avoid = analyze_keyword("أ", {"competition": 100,
                                      "serp": _serp(5, authority=50)})
        self.assertEqual(avoid["verdict"], VERDICT_AVOID)

    def test_verdict_avoid_by_competition_alone(self):
        # منافسة 80 بلا SERP → صعوبة 48 فقط لكن الحكم تجنّب
        result = analyze_keyword("أ", {"competition": 80})
        self.assertEqual(result["difficulty"], 48.0)
        self.assertEqual(result["verdict"], VERDICT_AVOID)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 79})["verdict"],
            VERDICT_CAREFUL)

    def test_competition_labels(self):
        self.assertEqual(
            analyze_keyword("أ", {"competition": 34})["competition_label"],
            COMPETITION_LOW)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 35})["competition_label"],
            COMPETITION_MEDIUM)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 64})["competition_label"],
            COMPETITION_MEDIUM)
        self.assertEqual(
            analyze_keyword("أ", {"competition": 65})["competition_label"],
            COMPETITION_HIGH)


class TestUnmeasured(unittest.TestCase):
    def test_no_competition(self):
        result = analyze_keyword("قصص", {"volume": 1000})
        self.assertIsNone(result["difficulty"])
        self.assertEqual(result["difficulty_label"], UNMEASURED)
        self.assertEqual(result["competition_label"], UNMEASURED)
        self.assertEqual(result["verdict"], VERDICT_UNKNOWN)
        self.assertIn("غير مقاس", result["reason"])

    def test_no_serp(self):
        result = analyze_keyword("أ", {"competition": 50})
        self.assertEqual(result["difficulty"], 30.0)
        self.assertFalse(result["serp_measured"])
        self.assertIsNone(result["serp_strength"])
        self.assertIn("غير مقاس", result["reason"])

    def test_empty_serp(self):
        result = analyze_keyword("أ", {"competition": 50, "serp": []})
        self.assertEqual(result["difficulty"], 30.0)
        self.assertFalse(result["serp_measured"])
        self.assertEqual(result["serp_count"], 0)

    def test_serp_without_any_authority(self):
        serp = [{"domain": "a.com", "title_match": True},
                {"domain": "b.com", "title_match": False}]
        result = analyze_keyword("أ", {"competition": 50, "serp": serp})
        self.assertIsNone(result["serp_strength"])
        self.assertFalse(result["serp_measured"])
        self.assertEqual(result["difficulty"], 30.0)
        self.assertEqual(result["title_match_count"], 1)

    def test_serp_first_ten_only(self):
        # 12 نتيجة: أول 10 بلا مطابقة، وآخر نتيجتين بمطابقة
        # وسلطة 100 — يجب تجاهلهما تمامًا.
        serp = ([{"domain": f"a{i}.com", "title_match": False,
                  "authority": 50} for i in range(10)]
                + [{"domain": "b.com", "title_match": True, "authority": 100},
                   {"domain": "c.com", "title_match": True, "authority": 100}])
        result = analyze_keyword("أ", {"competition": 50, "serp": serp})
        self.assertEqual(result["serp_count"], 10)
        self.assertEqual(result["title_match_count"], 0)
        self.assertEqual(result["serp_strength"], 0.0)
        self.assertEqual(result["difficulty"], 30.0)


class TestBatch(unittest.TestCase):
    def test_batch_sorted_by_difficulty_then_volume(self):
        results = analyze_keywords([
            {"keyword": "صعبة", "metrics": {"competition": 90}},
            {"keyword": "كبيرة", "metrics": {"volume": 9000, "competition": 40}},
            {"keyword": "صغيرة", "metrics": {"volume": 100, "competition": 40}},
            {"keyword": "بلا منافسة", "metrics": {"volume": 999999}},
        ])
        self.assertEqual(
            [r["keyword"] for r in results],
            ["كبيرة", "صغيرة", "صعبة", "بلا منافسة"])
        self.assertEqual(results[0]["difficulty"], 24.0)
        self.assertEqual(results[2]["difficulty"], 54.0)
        self.assertIsNone(results[3]["difficulty"])

    def test_batch_empty(self):
        self.assertEqual(analyze_keywords([]), [])

    def test_batch_accepts_json_string(self):
        text = json.dumps([
            {"keyword": "أ", "metrics": {"competition": 10}},
            {"keyword": "ب", "metrics": {"competition": 90}},
        ], ensure_ascii=False)
        results = analyze_keywords(text)
        self.assertEqual([r["keyword"] for r in results], ["أ", "ب"])


class TestInvalidInputs(unittest.TestCase):
    def test_empty_keyword(self):
        for bad in ("", "   ", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    analyze_keyword(bad, {"competition": 10})

    def test_competition_out_of_range(self):
        for bad in (-1, 101, 150):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    analyze_keyword("أ", {"competition": bad})

    def test_negative_volume(self):
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"volume": -5, "competition": 10})

    def test_non_numeric_values(self):
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": "عالية"})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": True})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"volume": "كثير"})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"growth_pct": "سريع"})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": 10, "serp": "ليست قائمة"})

    def test_invalid_serp_entry(self):
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": 10, "serp": [
                {"domain": "a.com", "title_match": True, "authority": 150}]})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": 10, "serp": [
                {"domain": "  ", "title_match": True}]})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": 10, "serp": [
                {"domain": "a.com", "title_match": "نعم"}]})
        with self.assertRaises(ValueError):
            analyze_keyword("أ", {"competition": 10, "serp": ["a.com"]})

    def test_metrics_not_dict(self):
        with self.assertRaises(ValueError):
            analyze_keyword("أ", "ليست قاموسًا")

    def test_corrupt_json(self):
        with self.assertRaises(ValueError):
            load_keywords_json("{تالف")
        with self.assertRaises(ValueError):
            load_keywords_json('{"keyword": "أ"}')  # ليس قائمة
        with self.assertRaises(ValueError):
            load_keywords_json('[{"metrics": {}}]')  # بلا كلمة
        with self.assertRaises(ValueError):
            load_keyword_json("{تالف")
        with self.assertRaises(ValueError):
            load_keyword_json('[{"keyword": "أ"}]')  # ليس قاموسًا


class TestJsonAndReport(unittest.TestCase):
    def test_load_and_round_trip(self):
        entries = load_keywords_json(json.dumps([
            {"keyword": "قصص", "metrics": {"volume": 483574,
                                            "competition": 59}},
        ], ensure_ascii=False))
        self.assertEqual(entries[0]["keyword"], "قصص")
        self.assertEqual(entries[0]["metrics"]["competition"], 59)
        single = load_keyword_json(json.dumps(
            {"keyword": "قصص", "metrics": {"competition": 59}},
            ensure_ascii=False))
        self.assertEqual(single["keyword"], "قصص")
        result = analyze_keyword(single["keyword"], single["metrics"])
        text = to_json(result)
        self.assertTrue(text.endswith("\n"))
        self.assertIn("قصص", text)  # عربي بلا ASCII هارب
        self.assertNotIn("\\u", text)
        self.assertEqual(json.loads(text)["difficulty"], 35.4)

    def test_to_json_batch(self):
        results = analyze_keywords([
            {"keyword": "أ", "metrics": {"competition": 10}}])
        text = to_json(results)
        self.assertEqual(json.loads(text)[0]["keyword"], "أ")
        with self.assertRaises(ValueError):
            to_json("ليست نتيجة")

    def test_format_report_single_and_batch(self):
        single = analyze_keyword("قصص", {
            "volume": 483574, "competition": 59})
        report = format_report(single)
        self.assertIn("قصص", report)
        self.assertIn("35.4", report)
        self.assertIn("استهدف", report)
        self.assertIn("لا أرقام مخترعة", report)
        batch = analyze_keywords([
            {"keyword": "أ", "metrics": {"competition": 10}},
            {"keyword": "ب", "metrics": {"volume": 5}},
        ])
        batch_report = format_report(batch)
        self.assertIn("«أ»", batch_report)
        self.assertIn("«ب»", batch_report)
        self.assertIn("غير مقاس", batch_report)
        self.assertEqual(format_report([]).count("لا كلمات"), 1)
        with self.assertRaises(ValueError):
            format_report("ليست نتيجة")


if __name__ == "__main__":
    unittest.main()
