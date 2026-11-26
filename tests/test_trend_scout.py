#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مساعد بحث الترندات الأسبوعي — جولة v0.1.58 (W1).

الأرقام الحقيقية هنا من تحليل ترند TikTok 2026-11-26
(~/workspace/studio-work/tiktok-trends/2026-11-26-ANALYSIS-AR.md):
فيديو 1.7M إعجاب، سلسلة «جزء 30» بـ420K إعجاب، أعلى
نسبة حفظ 20.9%، وأعلى نسبة مشاركة 37%. باقي البيانات
تركيبية لأغراض الاختبار فقط.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import trend_scout
from lib.trend_scout import (
    PATTERN_HORROR,
    PATTERN_OTHER,
    PATTERN_RELIGIOUS,
    PATTERN_SERIES,
    PATTERN_SHOCK,
    STATUS_CANDIDATE,
    STATUS_EXCLUDED,
    classify_hook_pattern,
    format_report,
    load_videos_json,
    scout_trends,
    to_json,
)


def _video(channel, title, **kwargs):
    """فيديو مدخل — قناة وعنوان وعدّادات اختيارية."""
    video = {"platform": "tiktok", "channel": channel, "title": title}
    video.update(kwargs)
    return video


# الأرقام الحقيقية الخمسة من تحليل الترند (بلا مشاهدات —
# نسخة TikTok على الويب لا تعرضها).
REAL_VIDEOS = [
    _video("قادة ستايل @food29797",
           "قصة الرجل الذي أيقظ أولاده للصلاة ورزقهم الله "
           "من حيث لا يحتسبون",
           likes=1_700_000, comments=24_100, saves=162_000,
           shares=170_300,
           url="https://www.tiktok.com/@food29797/video/7590733365557366038"),
    _video("قصص واقعية @qss6532",
           "قصة الرجل الذي أغلق على زوجته بالقفل وسافر — القصة الكاملة",
           likes=7_056, comments=305, saves=1_225, shares=653,
           url="https://www.tiktok.com/@qss6532/video/7650578618220809492"),
    _video("قصة وعبرة @abdulrah363",
           "جزء 30 | قصه الرجل الذي حفر حفره للنبي ﷺ",
           likes=420_000, comments=16_600, saves=52_500, shares=31_800,
           url="https://www.tiktok.com/@abdulrah363/video/7579926707092638998"),
    _video("راوي الأزمان @raawialazman",
           "نزع كل المسامير... لكن الأثر بقى / قصة الأب وكيس المسامير",
           likes=10_300, comments=177, saves=1_717, shares=3_855,
           url="https://www.tiktok.com/@raawialazman/video/7646863554338901270"),
    _video("في الضلمة @7beeeb",
           "غيط القصب.. قصة حقيقية ملهاش تفسير",
           likes=175_000, comments=2_311, saves=36_500, shares=11_600,
           url="https://www.tiktok.com/@7beeeb/video/7689209168020000020"),
]


class TestRealTrendNumbers(unittest.TestCase):
    """أرقام حقيقية من تحليل الترند — النسب والأنماط والترتيب."""

    def test_top_video_1_7m_likes_rates(self):
        """فيديو 1.7M إعجاب: حفظ 9.5% ومشاركة 10.0% من الإعجابات."""
        result = scout_trends([REAL_VIDEOS[0]])
        entry = result["candidates"][0]
        self.assertAlmostEqual(entry["save_rate"], 162_000 / 1_700_000, places=4)
        self.assertAlmostEqual(entry["share_rate"], 170_300 / 1_700_000, places=4)
        self.assertEqual(entry["save_basis"], "likes")
        self.assertEqual(entry["pattern"], PATTERN_RELIGIOUS)
        self.assertEqual(entry["status"], STATUS_CANDIDATE)
        self.assertEqual(entry["score"], 30.0)

    def test_series_420k_part_30(self):
        """سلسلة «جزء 30» بـ420K إعجاب: حفظ 12.5% ومشاركة 7.6%."""
        result = scout_trends([REAL_VIDEOS[2]])
        entry = result["candidates"][0]
        self.assertEqual(entry["pattern"], PATTERN_SERIES)
        self.assertAlmostEqual(entry["save_rate"], 0.125, places=4)
        self.assertAlmostEqual(entry["share_rate"], 31_800 / 420_000, places=4)
        self.assertEqual(entry["score"], 34.1)
        # عنوان الاقتراح بلا بادئة «جزء 30»، والهوك بالعنوان الكامل.
        suggestion = result["suggestions"][0]
        self.assertNotIn("جزء 30", suggestion["title"])
        self.assertIn("جزء 30", suggestion["hook"])
        self.assertEqual(suggestion["pattern"], PATTERN_SERIES)

    def test_highest_save_20_9_percent_is_horror_excluded(self):
        """أعلى حفظ 20.9% (غيط القصب): رعب — مستبعد ولا يُقترح أبدًا."""
        result = scout_trends(REAL_VIDEOS)
        entry = [e for e in result["candidates"]
                 if "غيط القصب" in e["title"]][0]
        self.assertAlmostEqual(entry["save_rate"], 36_500 / 175_000, places=4)
        self.assertGreater(entry["save_rate"], 0.208)
        self.assertEqual(entry["pattern"], PATTERN_HORROR)
        self.assertEqual(entry["status"], STATUS_EXCLUDED)
        self.assertIn("غيط القصب", result["excluded"][0])
        self.assertFalse(any("غيط القصب" in s["title"]
                             or "غيط القصب" in s["hook"]
                             for s in result["suggestions"]))

    def test_highest_share_37_percent_tops_ranking(self):
        """أعلى مشاركة 37% (الأب وكيس المسامير): الدرجة الأعلى 70.9."""
        result = scout_trends(REAL_VIDEOS)
        top = result["candidates"][0]
        self.assertIn("كيس المسامير", top["title"])
        self.assertAlmostEqual(top["share_rate"], 3_855 / 10_300, places=4)
        self.assertGreater(top["share_rate"], 0.37)
        self.assertEqual(top["score"], 70.9)
        self.assertEqual(top["pattern"], PATTERN_SHOCK)

    def test_real_five_ranking_order(self):
        """ترتيب الخمسة الحقيقيين بالنسب لا بالإعجابات الخام."""
        result = scout_trends(REAL_VIDEOS)
        titles = [e["title"] for e in result["candidates"]]
        self.assertIn("كيس المسامير", titles[0])
        self.assertIn("غيط القصب", titles[1])
        self.assertIn("القفل وسافر", titles[2])
        self.assertIn("جزء 30", titles[3])
        self.assertIn("أيقظ أولاده", titles[4])
        self.assertEqual([e["score"] for e in result["candidates"]],
                         [70.9, 51.2, 46.1, 34.1, 30.0])

    def test_real_suggestions_exclude_horror(self):
        """اقتراحات الخمسة: 4 فقط — الرعب مستبعد منها."""
        result = scout_trends(REAL_VIDEOS, top_n=5)
        self.assertEqual(len(result["suggestions"]), 4)
        self.assertEqual(result["total"], 5)
        for suggestion in result["suggestions"]:
            self.assertNotEqual(suggestion["pattern"], PATTERN_HORROR)
            self.assertIn("moral_angle", suggestion)
            self.assertTrue(suggestion["moral_angle"])
            self.assertTrue(suggestion["source_url"].startswith("https://"))
            self.assertIn("reason", suggestion)

    def test_real_videos_have_no_multiplier(self):
        """بلا مشاهدات (حدّ قياس التحليل): المضاعف غير مقاس لكل القنوات."""
        result = scout_trends(REAL_VIDEOS)
        self.assertTrue(all(e["multiplier"] is None
                            for e in result["candidates"]))
        self.assertEqual(len(result["skipped_channels"]), 5)
        self.assertTrue(all(count == 0
                            for count in result["skipped_channels"].values()))
        self.assertIn("غير مقاس", result["candidates"][0]["reason"])


class TestChannelMultiplier(unittest.TestCase):
    """مضاعف القناة على وسيطها — مفهوم viral_rank."""

    def _channel_videos(self, channel, views_list, **extra):
        videos = []
        for i, views in enumerate(views_list):
            videos.append(_video(channel, f"قصة تجريبية {i + 1}",
                                 views=views, likes=100,
                                 saves=10, shares=10, **extra))
        return videos

    def test_multiplier_with_four_videos(self):
        """4 فيديوهات وسيطها 250: فيديو بـ1000 مشاهدة مضاعفه ×4.00."""
        videos = self._channel_videos("قناة تجريبية أ", [100, 200, 300])
        videos.append(_video("قناة تجريبية أ", "قصة الأعلى",
                             views=1000, likes=100, saves=10, shares=10))
        result = scout_trends(videos)
        top = [e for e in result["candidates"]
               if e["title"] == "قصة الأعلى"][0]
        self.assertEqual(top["multiplier"], 4.0)
        # 45*(0.1/0.209) + 35*(0.1/0.37) + 20 = 51.0
        self.assertEqual(top["score"], 51.0)
        self.assertEqual(result["skipped_channels"], {})

    def test_channel_below_min_videos_skipped(self):
        """قناة بـ3 فيديوهات: تُتخطى والمضاعف غير مقاس."""
        videos = self._channel_videos("قناة تجريبية ب", [100, 200, 300])
        result = scout_trends(videos)
        self.assertEqual(result["skipped_channels"], {"قناة تجريبية ب": 3})
        self.assertTrue(all(e["multiplier"] is None
                            for e in result["candidates"]))

    def test_median_zero_multiplier_infinite(self):
        """وسيط صفر وفيديو بمشاهدات: مضاعف بلا حد ويُسلسل JSON."""
        videos = self._channel_videos("قناة تجريبية ج", [0, 0, 0, 10])
        result = scout_trends(videos)
        entry = [e for e in result["candidates"]
                 if e["views"] == 10][0]
        self.assertEqual(entry["multiplier"], float("inf"))
        payload = json.loads(to_json(result))
        dumped = [e for e in payload["candidates"]
                  if e["views"] == 10][0]
        self.assertEqual(dumped["multiplier"], "∞")

    def test_score_caps_at_reference(self):
        """نسب فوق المرجع تُقصّ عندها: حفظ 50% + مشاركة 90% = 80.0."""
        video = _video("قناة تجريبية د", "قصة مبالغ فيها",
                       likes=100, saves=50, shares=90)
        result = scout_trends([video])
        self.assertEqual(result["candidates"][0]["score"], 80.0)


class TestEdgeCases(unittest.TestCase):
    """حالات حدّية: بلا عدّادات، ومدخل فاسد."""

    def test_no_saves_no_views(self):
        """بلا saves/views: النسب غير مقاسة والدرجة صفر بلا اختراع."""
        video = _video("قناة تجريبية هـ", "قصة بلا عدّادات", likes=500)
        result = scout_trends([video])
        entry = result["candidates"][0]
        self.assertIsNone(entry["save_rate"])
        self.assertIsNone(entry["share_rate"])
        self.assertIsNone(entry["multiplier"])
        self.assertEqual(entry["score"], 0.0)
        self.assertIn("غير مقاس", entry["reason"])

    def test_save_via_views_when_no_likes(self):
        """بلا إعجابات ومع مشاهدات: الحفظ من المشاهدات ويُذكر أساسه."""
        video = _video("قناة تجريبية و", "قصة بلا إعجابات",
                       views=10_000, saves=1_500, shares=100)
        result = scout_trends([video])
        entry = result["candidates"][0]
        self.assertAlmostEqual(entry["save_rate"], 0.15, places=4)
        self.assertEqual(entry["save_basis"], "views")
        self.assertIsNone(entry["share_rate"])
        self.assertIn("من المشاهدات", entry["reason"])

    def test_zero_likes_no_division_error(self):
        """إعجابات صفر: بلا قسمة على صفر — النسبة غير مقاسة."""
        video = _video("قناة تجريبية ز", "قصة بلا إعجابات",
                       likes=0, saves=10, shares=5)
        result = scout_trends([video])
        entry = result["candidates"][0]
        self.assertIsNone(entry["save_rate"])
        self.assertIsNone(entry["share_rate"])
        self.assertEqual(entry["score"], 0.0)

    def test_minimal_video_only_channel_and_title(self):
        """فيديو بقناة وعنوان فقط: يُقبل ويُصنَّف «أخرى»."""
        result = scout_trends([{"channel": "ق", "title": "قصة عادية"}])
        entry = result["candidates"][0]
        self.assertEqual(entry["pattern"], PATTERN_OTHER)
        self.assertEqual(entry["status"], STATUS_CANDIDATE)
        self.assertEqual(entry["score"], 0.0)

    def test_invalid_empty_list(self):
        with self.assertRaises(ValueError):
            scout_trends([])

    def test_invalid_non_dict_entry(self):
        with self.assertRaises(ValueError):
            scout_trends(["ليست قاموسًا"])

    def test_invalid_missing_title(self):
        with self.assertRaises(ValueError):
            scout_trends([{"channel": "ق"}])

    def test_invalid_missing_channel(self):
        with self.assertRaises(ValueError):
            scout_trends([{"title": "قصة"}])

    def test_invalid_negative_likes(self):
        with self.assertRaises(ValueError):
            scout_trends([_video("ق", "قصة", likes=-5)])

    def test_invalid_bool_likes(self):
        with self.assertRaises(ValueError):
            scout_trends([_video("ق", "قصة", likes=True)])

    def test_invalid_non_numeric_shares(self):
        with self.assertRaises(ValueError):
            scout_trends([_video("ق", "قصة", shares="كثير")])

    def test_invalid_top_n(self):
        with self.assertRaises(ValueError):
            scout_trends(REAL_VIDEOS, top_n=0)

    def test_deterministic(self):
        """نفس المدخل مرتين: نفس النتيجة تمامًا."""
        first = scout_trends(REAL_VIDEOS)
        second = scout_trends(REAL_VIDEOS)
        self.assertEqual(first, second)


class TestClassifyHookPattern(unittest.TestCase):
    """تصنيف نمط الهوك بالكلمات — أول مطابقة تفوز."""

    def test_series_wins_over_religious(self):
        self.assertEqual(
            classify_hook_pattern("جزء 30 | قصة الرجل الذي حفر حفرة للنبي"),
            PATTERN_SERIES)

    def test_horror_wins_over_shock(self):
        self.assertEqual(
            classify_hook_pattern("غيط القصب.. قصة حقيقية ملهاش تفسير"),
            PATTERN_HORROR)

    def test_religious(self):
        self.assertEqual(
            classify_hook_pattern("قصة الرجل الذي أيقظ أولاده للصلاة"),
            PATTERN_RELIGIOUS)

    def test_shock(self):
        self.assertEqual(
            classify_hook_pattern("نزع كل المسامير... لكن الأثر بقى"),
            PATTERN_SHOCK)

    def test_other(self):
        self.assertEqual(classify_hook_pattern("قصة رجل عادي"),
                         PATTERN_OTHER)

    def test_empty_title_raises(self):
        with self.assertRaises(ValueError):
            classify_hook_pattern("   ")
        with self.assertRaises(ValueError):
            classify_hook_pattern(None)


class TestJsonAndReport(unittest.TestCase):
    """المدخل JSON والمخرج JSON والتقرير العربي."""

    def test_load_videos_json_valid(self):
        text = json.dumps(REAL_VIDEOS, ensure_ascii=False)
        videos = load_videos_json(text)
        self.assertEqual(len(videos), 5)
        self.assertEqual(videos[0]["likes"], 1_700_000)

    def test_load_videos_json_broken(self):
        with self.assertRaises(ValueError):
            load_videos_json("{ليس json")
        with self.assertRaises(ValueError):
            load_videos_json(json.dumps({"title": "ليست قائمة"}))
        with self.assertRaises(ValueError):
            load_videos_json("[]")

    def test_scout_accepts_json_string(self):
        text = json.dumps(REAL_VIDEOS, ensure_ascii=False)
        result = scout_trends(text)
        self.assertEqual(result["total"], 5)

    def test_to_json_round_trip(self):
        result = scout_trends(REAL_VIDEOS)
        payload = json.loads(to_json(result))
        self.assertEqual(len(payload["suggestions"]), 4)
        self.assertEqual(payload["candidates"][0]["score"], 70.9)
        self.assertIn("reference", payload)
        self.assertEqual(payload["reference"]["save_rate_range"],
                         [0.095, 0.209])

    def test_report_contents(self):
        result = scout_trends(REAL_VIDEOS)
        report = format_report(result)
        self.assertIn("تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح",
                      report)
        self.assertIn("لا أرقام مخترعة", report)
        self.assertIn("مستبعد", report)
        self.assertIn("غيط القصب", report)
        self.assertIn("لا تُكتب في ملف الطابور", report)
        self.assertIn("غير مقاس", report)
        self.assertIn("70.9/100", report)

    def test_report_rejects_bad_result(self):
        with self.assertRaises(ValueError):
            format_report({"candidates": []})
        with self.assertRaises(ValueError):
            format_report("ليست نتيجة")


if __name__ == "__main__":
    unittest.main()
