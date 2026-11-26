#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات السلطة الموضوعية لمكتبة القصص — جولة v0.1.61 (W7).

الأرقام المحسوبة يدويًا في اختبار المسار السعيد (مكتبة
HAPPY_LIBRARY من 13 قصة):
توبة ×2 (عمق 55)، أمانة ×1 (30)، صدقة ×3 (75)، صبر ×6
(100)، وباقي المواضيع الثمانية صفر — مجموع العمق 260،
متوسط العمق 260/12 = 21.666…، التغطية 4/12، السلطة =
0.5×21.666… + 0.5×33.333… = 27.5، الحكم «ضعيفة».
باقي البيانات تركيبية لأغراض الاختبار فقط.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import topical_authority
from lib.topical_authority import (
    DEFAULT_TOPIC_MAP,
    TOPIC_OTHER,
    VERDICT_MEDIUM,
    VERDICT_STRONG,
    VERDICT_WEAK,
    classify_title,
    depth_score,
    format_report,
    load_library_json,
    to_json,
    topical_authority,
)


def _story(title, topic=None):
    """قصة مدخل — عنوان وموضوع صريح اختياري."""
    story = {"title": title}
    if topic is not None:
        story["topic"] = topic
    return story


# مكتبة المسار السعيد: 13 قصة (2 توبة + 1 أمانة + 3 صدقة +
# 6 صبر + 1 أخرى بلا مطابقة).
HAPPY_LIBRARY = [
    _story("توبة كعب بن مالك"),
    _story("التائب الذي عاد إلى الله"),
    _story("النجار الأمين"),
    _story("فضل الصدقة"),
    _story("قصة المتصدق"),
    _story("الصدقة تدفع البلاء"),
    _story("صبر أيوب"),
    _story("الصبر مفتاح الفرج"),
    _story("صبرت المرأة على البلاء"),
    _story("قصة الصابر"),
    _story("الصبر على المرض"),
    _story("صبر الرجل الفقير"),
    _story("رحلة في الغابة"),
]


class TestDepthScore(unittest.TestCase):
    def test_depth_scale(self):
        self.assertEqual(depth_score(0), 0)
        self.assertEqual(depth_score(1), 30)
        self.assertEqual(depth_score(2), 55)
        self.assertEqual(depth_score(3), 75)
        self.assertEqual(depth_score(4), 90)
        self.assertEqual(depth_score(5), 90)
        self.assertEqual(depth_score(6), 100)
        self.assertEqual(depth_score(100), 100)

    def test_depth_invalid(self):
        for bad in (-1, 1.5, "3", True, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                depth_score(bad)


class TestClassifyTitle(unittest.TestCase):
    def test_auto_classification_keywords(self):
        cases = {
            "توبة كعب بن مالك": "توبة",
            "النجار الأمين": "أمانة",
            "فضل الصدقة": "صدقة",
            "بر الوالدين طريق الجنة": "بر الوالدين",
            "صبر أيوب": "صبر",
            "المظلوم عوضه الله": "ظلم وعوض",
            "الرجل الكريم": "كرم",
            "الرجل الذي أيقظ أولاده للصلاة": "صلاة",
            "قصة الغدار": "غدر وخيانة",
            "ندم الرجل على ذنبه": "ندم",
            "رحمة الله واسعة": "رحمة",
            "القاضي العادل": "عدل",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(classify_title(title), expected)

    def test_first_match_wins(self):
        # «توبة» قبل «صبر» في ترتيب الخريطة.
        self.assertEqual(classify_title("توبة الصابر على البلاء"), "توبة")
        # «أمانة» قبل «صبر» في ترتيب الخريطة.
        self.assertEqual(classify_title("أمانة الصابر"), "أمانة")
        # «ظلم وعوض» قبل «ندم» في ترتيب الخريطة.
        self.assertEqual(classify_title("ندم الظالم"), "ظلم وعوض")

    def test_no_match_is_other(self):
        self.assertEqual(classify_title("رحلة في الغابة"), TOPIC_OTHER)

    def test_normalization_diacritics_and_tatweel(self):
        self.assertEqual(classify_title("قصّة التّوبة"), "توبة")
        self.assertEqual(classify_title("التوـبة"), "توبة")
        self.assertEqual(classify_title("الصَّلاة عماد الدين"), "صلاة")
        self.assertEqual(classify_title("قصة الإمام الأمين"), "أمانة")

    def test_classify_invalid_title(self):
        for bad in ("", "   ", None, 42):
            with self.assertRaises(ValueError, msg=repr(bad)):
                classify_title(bad)


class TestTopicalAuthority(unittest.TestCase):
    def test_happy_path_manual_authority(self):
        result = topical_authority(HAPPY_LIBRARY)
        self.assertEqual(result["total"], 13)
        self.assertEqual(result["covered_topics"], 4)
        self.assertEqual(result["total_topics"], 12)
        self.assertAlmostEqual(result["coverage"], 4 / 12, places=4)
        self.assertEqual(result["coverage_pct"], 33.3)
        self.assertEqual(result["average_depth"], 21.7)
        self.assertEqual(result["authority"], 27.5)
        self.assertEqual(result["verdict"], VERDICT_WEAK)
        counts = {e["topic"]: e["count"] for e in result["topics"]}
        self.assertEqual(counts["توبة"], 2)
        self.assertEqual(counts["أمانة"], 1)
        self.assertEqual(counts["صدقة"], 3)
        self.assertEqual(counts["صبر"], 6)
        self.assertEqual(counts["بر الوالدين"], 0)
        depths = {e["topic"]: e["depth"] for e in result["topics"]}
        self.assertEqual(depths["توبة"], 55)
        self.assertEqual(depths["أمانة"], 30)
        self.assertEqual(depths["صدقة"], 75)
        self.assertEqual(depths["صبر"], 100)
        self.assertEqual(depths["عدل"], 0)

    def test_gaps_ordered_zero_before_one(self):
        result = topical_authority(HAPPY_LIBRARY)
        gaps = [(g["topic"], g["count"]) for g in result["gaps"]]
        self.assertEqual(gaps, [
            ("بر الوالدين", 0),
            ("ظلم وعوض", 0),
            ("كرم", 0),
            ("صلاة", 0),
            ("غدر وخيانة", 0),
            ("ندم", 0),
            ("رحمة", 0),
            ("عدل", 0),
            ("أمانة", 1),
        ])
        for gap in result["gaps"]:
            self.assertEqual(gap["suggestion"],
                             f"قصة جديدة في موضوع {gap['topic']}")

    def test_other_separate_from_coverage(self):
        result = topical_authority([_story("رحلة في الغابة")])
        self.assertEqual(result["other_count"], 1)
        self.assertEqual(result["other_titles"], ["رحلة في الغابة"])
        self.assertEqual(result["covered_topics"], 0)
        self.assertEqual(result["coverage"], 0.0)
        self.assertEqual(result["authority"], 0.0)
        self.assertEqual(result["verdict"], VERDICT_WEAK)
        self.assertEqual(len(result["gaps"]), 12)
        # «أخرى» نفسها ليست موضوعًا في جدول المواضيع.
        self.assertNotIn(TOPIC_OTHER,
                         [e["topic"] for e in result["topics"]])

    def test_empty_library_raises(self):
        for bad in ([], (), None, "[]", "not json"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                topical_authority(bad)

    def test_explicit_topic_used_as_is(self):
        # الموضوع الصريح يغلب التصنيف التلقائي (العنوان يقول
        # صبر لكن المشغّل قال صدقة).
        result = topical_authority([_story("قصة الصبر", "صدقة")])
        self.assertEqual(result["stories"][0]["topic"], "صدقة")
        counts = {e["topic"]: e["count"] for e in result["topics"]}
        self.assertEqual(counts["صدقة"], 1)
        self.assertEqual(counts["صبر"], 0)

    def test_explicit_topic_with_al_prefix_matches_map(self):
        # «الصدقة» المعطاة تطابق موضوع «صدقة» في الخريطة.
        result = topical_authority([_story("عنوان ما", "الصدقة")])
        self.assertEqual(result["stories"][0]["topic"], "صدقة")
        self.assertEqual(result["covered_topics"], 1)

    def test_explicit_unknown_topic_not_in_coverage(self):
        library = [
            _story("قصة البطل", "شجاعة"),
            _story("فضل الصدقة"),
        ]
        result = topical_authority(library)
        self.assertEqual(result["covered_topics"], 1)
        self.assertEqual(result["total_topics"], 12)
        self.assertEqual(result["extra_topics"],
                         [{"topic": "شجاعة", "count": 1, "depth": 30}])
        self.assertEqual(result["stories"][0]["topic"], "شجاعة")

    def test_strong_verdict_full_deep_library(self):
        library = []
        for topic in DEFAULT_TOPIC_MAP:
            for i in range(6):
                library.append(_story(f"قصة {i + 1}", topic))
        result = topical_authority(library)
        self.assertEqual(result["total"], 72)
        self.assertEqual(result["covered_topics"], 12)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["average_depth"], 100.0)
        self.assertEqual(result["authority"], 100.0)
        self.assertEqual(result["verdict"], VERDICT_STRONG)
        self.assertEqual(result["gaps"], [])

    def test_medium_verdict(self):
        # 6 مواضيع × 3 قصص: متوسط العمق 37.5، التغطية 50%،
        # السلطة = 0.5×37.5 + 0.5×50 = 43.75 ≈ 43.8.
        topics = list(DEFAULT_TOPIC_MAP)[:6]
        library = [_story(f"قصة {i + 1}", topic)
                   for topic in topics for i in range(3)]
        result = topical_authority(library)
        self.assertEqual(result["covered_topics"], 6)
        self.assertEqual(result["coverage"], 0.5)
        self.assertEqual(result["average_depth"], 37.5)
        self.assertEqual(result["authority"], 43.8)
        self.assertEqual(result["verdict"], VERDICT_MEDIUM)

    def test_custom_topic_map(self):
        topic_map = {
            "شجاعة": ("شجاع", "بطل"),
            "حكمة": ("حكيم", "حكمه"),
        }
        library = [
            _story("قصة البطل الشجاع"),
            _story("الحكيم والقرية"),
        ]
        result = topical_authority(library, topic_map=topic_map)
        self.assertEqual(result["total_topics"], 2)
        self.assertEqual(result["covered_topics"], 2)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["authority"], 65.0)
        self.assertEqual(result["verdict"], VERDICT_MEDIUM)
        self.assertEqual([g["topic"] for g in result["gaps"]],
                         ["شجاعة", "حكمة"])

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            topical_authority([{"title": ""}])
        with self.assertRaises(ValueError):
            topical_authority([{"title": 42}])
        with self.assertRaises(ValueError):
            topical_authority([{"no_title": "x"}])
        with self.assertRaises(ValueError):
            topical_authority(["not a dict"])
        with self.assertRaises(ValueError):
            topical_authority([_story("عنوان", 5)])
        with self.assertRaises(ValueError):
            topical_authority(HAPPY_LIBRARY[:1], topic_map={})
        with self.assertRaises(ValueError):
            topical_authority(HAPPY_LIBRARY[:1],
                              topic_map={"شجاعة": ()})
        with self.assertRaises(ValueError):
            topical_authority(HAPPY_LIBRARY[:1],
                              topic_map={"توبة": ("x",),
                                         "توبه": ("y",)})

    def test_accepts_json_string(self):
        text = json.dumps(HAPPY_LIBRARY, ensure_ascii=False)
        result = topical_authority(text)
        self.assertEqual(result["total"], 13)
        self.assertEqual(result["authority"], 27.5)


class TestLoadLibraryJson(unittest.TestCase):
    def test_valid_json(self):
        text = json.dumps([{"title": "توبة كعب بن مالك"}], ensure_ascii=False)
        library = load_library_json(text)
        self.assertEqual(library, [{"title": "توبة كعب بن مالك",
                                    "topic": None}])

    def test_invalid_json(self):
        for bad in ("not json", '{"a": 1}', "[]", 42, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                load_library_json(bad)


class TestToJsonAndReport(unittest.TestCase):
    def test_to_json_roundtrip(self):
        result = topical_authority(HAPPY_LIBRARY)
        text = to_json(result)
        self.assertTrue(text.endswith("\n"))
        # عربي بلا ASCII هارب.
        self.assertIn("توبة", text)
        self.assertNotIn("\\u", text)
        self.assertEqual(json.loads(text), result)

    def test_to_json_invalid(self):
        with self.assertRaises(ValueError):
            to_json("not a dict")

    def test_format_report_contains_key_lines(self):
        result = topical_authority(HAPPY_LIBRARY)
        report = format_report(result)
        self.assertIn("27.5/100", report)
        self.assertIn("ضعيفة", report)
        self.assertIn("4/12", report)
        self.assertIn("قصة جديدة في موضوع بر الوالدين", report)
        self.assertIn("«أخرى»", report)
        self.assertIn("تصنيف بالكلمات فقط", report)
        self.assertIn("رحلة في الغابة", report)

    def test_format_report_invalid(self):
        with self.assertRaises(ValueError):
            format_report({})
        with self.assertRaises(ValueError):
            format_report("not a dict")


if __name__ == "__main__":
    unittest.main()
