#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات محلّل الصفحة Page Analyzer — جولة v0.1.61 (W5).

البيانات تركيبية لأغراض الاختبار فقط (عنوان ووصف ووسوم
من صياغتنا، بلا أي نسخ من GuinRank — الأداة مغلقة).
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import page_analyze
from lib.page_analyze import (
    analyze_page,
    format_report,
    grade_score,
    load_page_json,
    to_json,
)

TITLE = "قصة الرجل الذي أيقظ أولاده للصلاة | الجزء الأول"

DESCRIPTION = (
    "تخيل رجلًا يوقظ أولاده للصلاة كل فجر مهما كان التعب؟ "
    "هذه قصة مؤثرة عن رجل لم يترك صلاة الفجر يومًا، وكيف "
    "رزقه الله من حيث لا يحتسب جزاءً على حرصه على أولاده. "
    "شاهد القصة كاملة حتى النهاية، وانتظر الجزء الثاني "
    "قريبًا — اشترك في القناة وتابعنا ليصلك كل جديد."
)

TAGS = ["الصلاة", "أولاده", "الرجل", "قصة", "الجزء الأول"]


def _perfect_page(**overrides):
    """صفحة مثالية (100/100) مع تجاوزات اختيارية."""
    page = {
        "title": TITLE,
        "description": DESCRIPTION,
        "tags": list(TAGS),
        "url": "https://www.youtube.com/shorts/4C9LjipW99w",
        "duration": 50,
        "keyword": "الصلاة",
    }
    page.update(overrides)
    return page


def _check(result, name):
    """فحص واحد بالاسم من نتيجة التحليل."""
    for entry in result["checks"]:
        if entry["check"] == name:
            return entry
    raise AssertionError(f"فحص مفقود: {name}")


class TestPerfectPage(unittest.TestCase):
    def test_perfect_page_scores_100_excellent(self):
        result = analyze_page(_perfect_page())
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["grade"], "ممتاز")
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(len(result["checks"]), 10)
        self.assertTrue(all(c["status"] == "ناجح" for c in result["checks"]))
        self.assertTrue(result["keyword_measured"])
        self.assertTrue(result["duration_measured"])

    def test_title_length_is_within_range(self):
        self.assertTrue(30 <= len(TITLE) <= 70)
        self.assertTrue(150 <= len(DESCRIPTION) <= 400)

    def test_good_page_scores_75(self):
        description = (
            "تخيل رجلًا يوقظ أولاده للصلاة كل فجر مهما كان التعب؟ "
            "هذه قصة مؤثرة عن رجل لم يترك صلاة الفجر يومًا، وكيف "
            "رزقه الله من حيث لا يحتسب جزاءً على حرصه على أولاده. "
            "شاهد القصة كاملة حتى النهاية وشاركها مع من تحب."
        )
        result = analyze_page(_perfect_page(
            description=description, url="", duration=None))
        # -10 مدة غير مقاسة، -5 بلا رابط، -10 بلا دعوة لطيفة.
        self.assertEqual(result["score"], 75)
        self.assertEqual(result["grade"], "جيد")


class TestWeakPage(unittest.TestCase):
    def test_weak_page_score_and_sorted_suggestions(self):
        result = analyze_page({
            "title": "قصة قصيرة",
            "description": "رجل تصدق بماله.",
            "tags": ["سيارات", "طبخ"],
            "url": "",
            "duration": 120,
            "keyword": "الصدقة",
        })
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["grade"], "ضعيف")
        self.assertEqual(len(result["suggestions"]), 10)
        ranks = {"عالٍ": 0, "متوسط": 1, "منخفض": 2}
        order = [ranks[s["priority"]] for s in result["suggestions"]]
        self.assertEqual(order, sorted(order))
        self.assertEqual(result["suggestions"][0]["priority"], "عالٍ")
        for item in result["suggestions"]:
            self.assertIn("check", item)
            self.assertIn("issue", item)
            self.assertIn("suggestion", item)
            self.assertIn(item["priority"], ("عالٍ", "متوسط", "منخفض"))

    def test_long_title_suggests_shortening(self):
        result = analyze_page(_perfect_page(
            title="قصة الرجل الذي أيقظ أولاده للصلاة كل فجر "
                  "ولم يترك صلاة الفجر يومًا واحدًا في حياته أبدًا"))
        check = _check(result, "طول العنوان")
        self.assertEqual(check["score"], 0)
        self.assertEqual(check["status"], "فاشل")
        self.assertTrue(any(s["check"] == "طول العنوان"
                            for s in result["suggestions"]))

    def test_short_description_fails(self):
        result = analyze_page(_perfect_page(description="قصة قصيرة."))
        check = _check(result, "طول الوصف")
        self.assertEqual(check["score"], 0)
        self.assertEqual(check["status"], "فاشل")

    def test_partial_tag_relevance_is_proportional(self):
        result = analyze_page(_perfect_page(
            tags=["الصلاة", "أولاده", "سيارات", "طبخ"]))
        check = _check(result, "صلة الوسوم")
        self.assertEqual(check["score"], 7.5)
        self.assertEqual(check["status"], "فاشل")

    def test_invalid_url_fails(self):
        result = analyze_page(_perfect_page(url="ليس رابطًا"))
        check = _check(result, "الرابط")
        self.assertEqual(check["score"], 0)
        self.assertEqual(check["status"], "فاشل")


class TestUnmeasured(unittest.TestCase):
    def test_no_duration_is_unmeasured_not_failed_content(self):
        result = analyze_page(_perfect_page(duration=None))
        check = _check(result, "مدة الشورت")
        self.assertEqual(check["status"], "غير مقاس")
        self.assertEqual(check["score"], 0)
        self.assertFalse(result["duration_measured"])
        self.assertEqual(result["score"], 90)
        self.assertEqual(result["grade"], "ممتاز")
        suggestion = [s for s in result["suggestions"]
                      if s["check"] == "مدة الشورت"]
        self.assertEqual(len(suggestion), 1)
        self.assertEqual(suggestion[0]["priority"], "منخفض")

    def test_no_keyword_is_unmeasured(self):
        result = analyze_page(_perfect_page(keyword=""))
        self.assertFalse(result["keyword_measured"])
        for name in ("الكلمة المستهدفة في العنوان",
                     "الكلمة المستهدفة في بداية الوصف"):
            self.assertEqual(_check(result, name)["status"], "غير مقاس")
        # -15 عنوان، -10 وصف.
        self.assertEqual(result["score"], 75)
        self.assertEqual(result["grade"], "جيد")

    def test_duration_out_of_range_fails(self):
        result = analyze_page(_perfect_page(duration=30))
        check = _check(result, "مدة الشورت")
        self.assertEqual(check["score"], 0)
        self.assertEqual(check["status"], "فاشل")


class TestHookAndNormalization(unittest.TestCase):
    def test_hook_by_question_mark_only(self):
        description = (
            "هل تعرف ماذا فعل الرجل حين أيقظ أولاده للصلاة؟ "
            "هذه قصة مؤثرة عن رجل لم يترك صلاة الفجر يومًا، وكيف "
            "رزقه الله من حيث لا يحتسب جزاءً على حرصه على أولاده. "
            "شاهد القصة كاملة حتى النهاية، وانتظر الجزء الثاني "
            "قريبًا — اشترك في القناة وتابعنا ليصلك كل جديد."
        )
        result = analyze_page(_perfect_page(description=description))
        self.assertEqual(_check(result, "هوك أول سطر")["score"], 10)

    def test_keyword_matches_despite_hamza_and_diacritics(self):
        # الكلمة بالتشكيل والهمزة تطابق «أولاده» في العنوان.
        result = analyze_page(_perfect_page(keyword="أولَادِه"))
        self.assertEqual(
            _check(result, "الكلمة المستهدفة في العنوان")["score"], 15)

    def test_tatweel_is_ignored_in_matching(self):
        result = analyze_page(_perfect_page(keyword="الصــلاة"))
        self.assertEqual(
            _check(result, "الكلمة المستهدفة في العنوان")["score"], 15)


class TestInvalidInputs(unittest.TestCase):
    def test_empty_title_raises(self):
        with self.assertRaises(ValueError):
            analyze_page(_perfect_page(title="   "))

    def test_missing_title_raises(self):
        page = _perfect_page()
        del page["title"]
        with self.assertRaises(ValueError):
            analyze_page(page)

    def test_page_must_be_dict(self):
        with self.assertRaises(ValueError):
            analyze_page(["عنوان"])

    def test_tags_not_list_raises(self):
        with self.assertRaises(ValueError):
            analyze_page(_perfect_page(tags="الصلاة"))

    def test_tag_not_text_raises(self):
        with self.assertRaises(ValueError):
            analyze_page(_perfect_page(tags=["الصلاة", 7]))

    def test_negative_duration_raises(self):
        with self.assertRaises(ValueError):
            analyze_page(_perfect_page(duration=-5))

    def test_bool_duration_raises(self):
        with self.assertRaises(ValueError):
            analyze_page(_perfect_page(duration=True))

    def test_non_text_description_raises(self):
        with self.assertRaises(ValueError):
            analyze_page(_perfect_page(description=123))


class TestGradesAndIO(unittest.TestCase):
    def test_grade_boundaries(self):
        self.assertEqual(grade_score(100), "ممتاز")
        self.assertEqual(grade_score(85), "ممتاز")
        self.assertEqual(grade_score(84.9), "جيد")
        self.assertEqual(grade_score(70), "جيد")
        self.assertEqual(grade_score(69.9), "يحتاج تحسين")
        self.assertEqual(grade_score(50), "يحتاج تحسين")
        self.assertEqual(grade_score(49.9), "ضعيف")
        self.assertEqual(grade_score(0), "ضعيف")

    def test_load_page_json_and_to_json_roundtrip(self):
        text = json.dumps(_perfect_page(), ensure_ascii=False)
        loaded = load_page_json(text)
        self.assertEqual(loaded["title"], TITLE)
        result = analyze_page(loaded)
        dumped = to_json(result)
        self.assertTrue(dumped.endswith("\n"))
        # عربي بلا ASCII هارب.
        self.assertIn("ممتاز", dumped)
        self.assertNotIn("\\u", dumped)
        self.assertEqual(json.loads(dumped)["score"], 100)

    def test_load_page_json_rejects_bad_json(self):
        with self.assertRaises(ValueError):
            load_page_json("{تالف")
        with self.assertRaises(ValueError):
            load_page_json('["ليست قاموسًا"]')

    def test_analyze_accepts_json_string(self):
        text = json.dumps(_perfect_page(), ensure_ascii=False)
        self.assertEqual(analyze_page(text)["score"], 100)

    def test_format_report_contains_grade_and_suggestions(self):
        weak = analyze_page({
            "title": "قصة قصيرة",
            "description": "قصة رجل تصدق.",
            "tags": ["سيارات"],
            "url": "",
            "duration": None,
            "keyword": "الصدقة",
        })
        report = format_report(weak)
        self.assertIn("ضعيف", report)
        self.assertIn("غير مقاس", report)
        self.assertIn("الاقتراحات مرتبة بالأولوية", report)
        self.assertIn("تكامل", report)
        good = format_report(analyze_page(_perfect_page()))
        self.assertIn("ممتاز", good)
        self.assertIn("لا اقتراحات", good)

    def test_to_json_and_format_report_reject_non_dict(self):
        with self.assertRaises(ValueError):
            to_json(["ليست نتيجة"])
        with self.assertRaises(ValueError):
            format_report(["ليست نتيجة"])
        with self.assertRaises(ValueError):
            format_report({"score": 10})


if __name__ == "__main__":
    unittest.main()
