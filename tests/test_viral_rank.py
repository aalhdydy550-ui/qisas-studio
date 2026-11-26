#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات ترتيب الشواذ بمضاعف القناة — بلا شبكة وبلا أرقام حقيقية.

كل البيانات هنا **تركيبية** (قنوات وعناوين وأرقام مختلقة لأغراض
الاختبار فقط) — لا تمثّل أي قناة فعلية ولا أي مشاهدات حقيقية.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import viral_rank
from lib.viral_rank import format_report, rank_outliers


def _video(channel, title, views, duration=45, url=""):
    """فيديو تركيبي — قناة وعنوان وأرقام مختلقة للاختبار فقط."""
    return {"channel": channel, "title": title,
            "views": views, "duration": duration, "url": url}


# قناة تركيبية أ: 4 فيديوهات — وسيطها 250 (وسيط 100/200/300/400).
CHANNEL_A = [
    _video("قناة تجريبية أ", "قصة رجل عادي", 100),
    _video("قناة تجريبية أ", "قصة امرأة صابرة", 200),
    _video("قناة تجريبية أ", "قصة تاجر أمين", 300),
    _video("قناة تجريبية أ", "قصة حقيقية هزت المدينة", 4000),
]
# قناة تركيبية ب: 4 فيديوهات — وسيطها 1000.
CHANNEL_B = [
    _video("قناة تجريبية ب", "حكاية الجار", 800),
    _video("قناة تجريبية ب", "حكاية المسافر", 900),
    _video("قناة تجريبية ب", "حكاية المعلم", 1100),
    _video("قناة تجريبية ب", "كيف نجا من الغرق؟", 3000),
]


class TestMedianAndMultiplier(unittest.TestCase):
    def test_median_of_even_count_is_average_of_middle_two(self):
        result = rank_outliers(CHANNEL_A)
        top = result["ranked"][0]
        self.assertEqual(top["title"], "قصة حقيقية هزت المدينة")
        # وسيط 100/200/300/400 = (200+300)/2 = 250.
        self.assertEqual(top["median"], 250)
        self.assertEqual(top["multiplier"], 16.0)

    def test_raw_views_do_not_rank_channel_size(self):
        # فيديو «ب» بمشاهدات 3000 أقل مضاعفًا (×3) من فيديو «أ»
        # بمشاهدات 4000 (×16) — لكن فيديو «أ» بـ300 مشاهدة
        # (×1.2) يجب أن يسبق فيديو «ب» بـ1100 مشاهدة (×1.1)
        # رغم أن مشاهداته الخام أقل.
        result = rank_outliers(CHANNEL_A + CHANNEL_B)
        titles = [e["title"] for e in result["ranked"]]
        self.assertEqual(titles[0], "قصة حقيقية هزت المدينة")
        self.assertEqual(titles[1], "كيف نجا من الغرق؟")
        self.assertEqual(result["ranked"][1]["multiplier"], 3.0)
        self.assertLess(titles.index("قصة تاجر أمين"),
                        titles.index("حكاية المعلم"))

    def test_top_n_limits_ranked(self):
        result = rank_outliers(CHANNEL_A + CHANNEL_B, top_n=2)
        self.assertEqual(len(result["ranked"]), 2)

    def test_ranked_entry_has_all_fields(self):
        result = rank_outliers(CHANNEL_A)
        entry = result["ranked"][0]
        for key in ("title", "channel", "views", "median",
                    "multiplier", "url", "duration", "title_format"):
            self.assertIn(key, entry)

    def test_zero_median_channel(self):
        videos = [_video("قناة تجريبية صفرية", f"قصة {i}", 0)
                   for i in range(4)]
        videos.append(_video("قناة تجريبية صفرية",
                             "قصة حقيقية واحدة مشاهدة", 10))
        result = rank_outliers(videos)
        self.assertEqual(result["ranked"][0]["multiplier"], float("inf"))
        self.assertEqual(result["ranked"][-1]["multiplier"], 0.0)

    def test_result_is_deterministic(self):
        videos = CHANNEL_A + CHANNEL_B
        self.assertEqual(rank_outliers(videos), rank_outliers(videos))


class TestSkippedChannels(unittest.TestCase):
    def test_channel_below_min_videos_is_skipped_and_named(self):
        small = [_video("قناة تجريبية صغيرة", "قصة قصيرة", 5000),
                 _video("قناة تجريبية صغيرة", "قصة أخرى", 6000)]
        result = rank_outliers(CHANNEL_A + small)
        self.assertEqual(result["skipped_channels"],
                         {"قناة تجريبية صغيرة": 2})
        titles = [e["title"] for e in result["ranked"]]
        self.assertNotIn("قصة قصيرة", titles)

    def test_min_videos_parameter(self):
        small = [_video("قناة تجريبية صغيرة", "قصة قصيرة", 5000),
                 _video("قناة تجريبية صغيرة", "قصة أخرى", 6000)]
        result = rank_outliers(CHANNEL_A + small, min_videos=2)
        self.assertEqual(result["skipped_channels"], {})
        self.assertIn("قصة قصيرة",
                      [e["title"] for e in result["ranked"]])

    def test_report_names_skipped_channels(self):
        small = [_video("قناة تجريبية صغيرة", "قصة قصيرة", 5000)]
        report = format_report(rank_outliers(CHANNEL_A + small))
        self.assertIn("قناة تجريبية صغيرة", report)
        self.assertIn("1 فيديوهات", report)


class TestTitleFormatClassification(unittest.TestCase):
    def test_part_of_series(self):
        self.assertEqual(
            viral_rank.classify_title_format("الجزء 2 من 5: عودة التاجر"),
            "جزء من سلسلة")

    def test_true_story(self):
        self.assertEqual(
            viral_rank.classify_title_format("قصة حقيقية حدثت في القرية"),
            "قصة حقيقية")

    def test_question_mark(self):
        self.assertEqual(
            viral_rank.classify_title_format("ماذا فعل بعد أن خسر كل شيء؟"),
            "سؤال")

    def test_question_word_without_mark(self):
        self.assertEqual(
            viral_rank.classify_title_format("كيف نجا من الغرق"),
            "سؤال")
        self.assertEqual(
            viral_rank.classify_title_format("لماذا ترك بيته"),
            "سؤال")

    def test_number_first(self):
        self.assertEqual(
            viral_rank.classify_title_format("3 قصص عن الصبر"),
            "رقم في البداية")
        self.assertEqual(
            viral_rank.classify_title_format("٥ دروس من الحياة"),
            "رقم في البداية")

    def test_curiosity_words(self):
        self.assertEqual(
            viral_rank.classify_title_format("السر الذي أخفاه الجار"),
            "فضول")
        self.assertEqual(
            viral_rank.classify_title_format("الحقيقة الكاملة وراء الحادثة"),
            "فضول")
        self.assertEqual(
            viral_rank.classify_title_format("كشف المستور عن التاجر"),
            "فضول")
        self.assertEqual(
            viral_rank.classify_title_format("لن تصدق ما فعله الأخ"),
            "فضول")

    def test_other(self):
        self.assertEqual(
            viral_rank.classify_title_format("قصة رجل عادي"),
            "أخرى")

    def test_part_beats_true_story_when_both_match(self):
        # ترتيب القواعد موثّق: أول مطابقة تفوز.
        self.assertEqual(
            viral_rank.classify_title_format(
                "الجزء 1 من 3: قصة حقيقية"),
            "جزء من سلسلة")

    def test_empty_title_raises(self):
        with self.assertRaises(ValueError):
            viral_rank.classify_title_format("   ")


class TestSharedPattern(unittest.TestCase):
    def test_clear_majority_format_and_duration_range(self):
        # 4 من 5 أسئلة — أغلبية واضحة.
        videos = [
            _video("قناة تجريبية ج", "كيف حدث هذا؟", 5000, duration=40),
            _video("قناة تجريبية ج", "لماذا غادر؟", 4000, duration=50),
            _video("قناة تجريبية ج", "ماذا قال القاضي؟", 3000, duration=45),
            _video("قناة تجريبية ج", "هل عاد المسافر؟", 2000, duration=60),
            _video("قناة تجريبية ج", "قصة الجار", 100),
        ]
        result = rank_outliers(videos)
        self.assertEqual(len(result["ranked"]), 5)
        self.assertIn("سؤال (4 من 5)", result["shared_pattern"])
        self.assertIn("المدة الوسيطة", result["shared_pattern"])

    def test_no_clear_pattern_when_formats_split(self):
        # صيغ متفرقة بلا أغلبية — لا اختراع نمط.
        videos = [
            _video("قناة تجريبية د", "كيف حدث هذا؟", 5000),
            _video("قناة تجريبية د", "3 قصص عن الصبر", 4000),
            _video("قناة تجريبية د", "قصة حقيقية هزت المدينة", 3000),
            _video("قناة تجريبية د", "السر الذي أخفاه الجار", 2000),
            _video("قناة تجريبية د", "قصة الجار", 100),
        ]
        result = rank_outliers(videos)
        self.assertEqual(result["shared_pattern"], "لا نمط واحد واضح")

    def test_no_ranked_means_no_pattern(self):
        small = [_video("قناة تجريبية صغيرة", "قصة قصيرة", 5000)]
        result = rank_outliers(small)
        self.assertEqual(result["ranked"], [])
        self.assertEqual(result["shared_pattern"], "لا نمط واحد واضح")


class TestInvalidInputs(unittest.TestCase):
    def test_empty_list_raises(self):
        with self.assertRaises(ValueError) as ctx:
            rank_outliers([])
        self.assertIn("فارغة", str(ctx.exception))

    def test_not_a_list_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers("ليست قائمة")

    def test_negative_views_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers([_video("قناة تجريبية أ", "قصة", -5)])

    def test_non_numeric_views_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers([_video("قناة تجريبية أ", "قصة", "كثير")])

    def test_missing_channel_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers([{"title": "قصة", "views": 10}])

    def test_missing_title_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers([{"channel": "قناة تجريبية أ", "views": 10}])

    def test_missing_views_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers([{"channel": "قناة تجريبية أ", "title": "قصة"}])

    def test_non_dict_video_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers(["قصة"])

    def test_negative_duration_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers([_video("قناة تجريبية أ", "قصة", 10, duration=-3)])

    def test_bad_top_n_raises(self):
        with self.assertRaises(ValueError):
            rank_outliers(CHANNEL_A, top_n=0)

    def test_optional_url_and_duration(self):
        videos = [{"channel": "قناة تجريبية أ", "title": f"قصة {i}",
                   "views": 100 * (i + 1)} for i in range(4)]
        result = rank_outliers(videos)
        self.assertEqual(len(result["ranked"]), 4)
        self.assertEqual(result["ranked"][0]["url"], "")
        self.assertIsNone(result["ranked"][0]["duration"])


class TestFormatReport(unittest.TestCase):
    def test_report_contains_ranked_and_disclaimer(self):
        report = format_report(rank_outliers(CHANNEL_A + CHANNEL_B))
        self.assertIn("قصة حقيقية هزت المدينة", report)
        self.assertIn("×16.00", report)
        self.assertIn("تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح",
                      report)
        self.assertIn("النمط المشترك", report)
        self.assertIn("السطر الأصعب", report)

    def test_report_with_no_ranked_still_has_disclaimer(self):
        small = [_video("قناة تجريبية صغيرة", "قصة قصيرة", 5000)]
        report = format_report(rank_outliers(small))
        self.assertIn("لا فيديوهات مرتّبة", report)
        self.assertIn("تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح",
                      report)

    def test_report_rejects_malformed_result(self):
        with self.assertRaises(ValueError):
            format_report({"ranked": []})


if __name__ == "__main__":
    unittest.main()
