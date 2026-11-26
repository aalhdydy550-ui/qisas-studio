#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات باحث التخصصات الدقيقة (Micro Niche Finder) — جولة v0.1.61 (W4).

الأرقام هنا تركيبية لأغراض الاختبار فقط، ومحسوبة يدويًا من
الصيغة الموثّقة في ``lib/micro_niche.py``:
منافسة 40 × (1 − متوسط المنافسة/100) + حجم 30 ×
min(متوسط الحجم/5000, 1) + فجوة 30 × (1 − التغطية).
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import micro_niche
from lib.micro_niche import (
    UNMEASURED,
    VERDICT_CROWDED,
    VERDICT_NO_DEMAND,
    VERDICT_OPPORTUNITY,
    VERDICT_POSSIBLE,
    find_micro_niches,
    format_report,
    load_niches_json,
    to_json,
)


def _niche(name, keywords):
    """تخصص مدخل — اسم وقائمة كلمات {keyword, volume?, competition?}."""
    return {"name": name, "keywords": keywords}


def _kw(keyword, volume=None, competition=None):
    """كلمة مدخل — الحجم والمنافسة اختياريان."""
    entry = {"keyword": keyword}
    if volume is not None:
        entry["volume"] = volume
    if competition is not None:
        entry["competition"] = competition
    return entry


# بيانات المسار السعيد — محسوبة يدويًا:
# فرصة: منافسة 25 → 30.0 + حجم 5000 → 30.0 + فجوة 1.0 → 30.0 = 90.0.
OPPORTUNITY = _niche("قصص الصدقة", [
    _kw("الصدقة", volume=6000, competition=20),
    _kw("فضل الصدقة", volume=4000, competition=30),
])
# ممكن: منافسة 50 → 20.0 + حجم 2500 → 15.0 + فجوة 0.5 → 15.0 = 50.0
# (المكتبة تغطي «الكرم» فقط من كلمتين).
POSSIBLE = _niche("قصص الكرم", [
    _kw("الكرم", volume=3000, competition=50),
    _kw("الجود", volume=2000, competition=50),
])
POSSIBLE_LIBRARY = [{"title": "قصة عن الكرم"}]


class TestHappyPath(unittest.TestCase):
    """المسار السعيد: فرصة ومزدحم وممكن — بالصيغة الموثّقة."""

    def test_opportunity_score_and_components(self):
        """فرصة: 30.0 منافسة + 30.0 حجم + 30.0 فجوة = 90.0."""
        result = find_micro_niches([OPPORTUNITY])
        entry = result["niches"][0]
        self.assertEqual(entry["verdict"], VERDICT_OPPORTUNITY)
        self.assertEqual(entry["score"], 90.0)
        self.assertEqual(entry["components"],
                         {"competition": 30.0, "volume": 30.0, "gap": 30.0})
        self.assertEqual(entry["avg_competition"], 25.0)
        self.assertEqual(entry["total_volume"], 10000)
        self.assertEqual(entry["avg_volume"], 5000.0)
        self.assertEqual(entry["coverage"], 0.0)
        self.assertEqual(entry["gap"], 1.0)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["library_size"], 0)

    def test_crowded_high_competition_beats_high_score(self):
        """مزدحم رغم درجة 68.0: منافسة 80 ≥ 65 تتقدم على «فرصة»."""
        niche = _niche("قصص الأنبياء",
                       [_kw("الأنبياء", volume=10000, competition=80)])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertEqual(entry["score"], 68.0)
        self.assertEqual(entry["verdict"], VERDICT_CROWDED)

    def test_crowded_low_score_with_high_competition(self):
        """مزدحم بدرجة 19.0: منافسة 60 مع درجة < 40."""
        niche = _niche("قصص التوبة",
                       [_kw("التوبة", volume=500, competition=60)])
        library = [{"title": "قصة التوبة"}]
        result = find_micro_niches([niche], library)
        entry = result["niches"][0]
        self.assertEqual(entry["score"], 19.0)
        self.assertEqual(entry["verdict"], VERDICT_CROWDED)

    def test_possible_mid_score(self):
        """ممكن: درجة 50.0 مع تغطية نصفية من المكتبة."""
        result = find_micro_niches([POSSIBLE], POSSIBLE_LIBRARY)
        entry = result["niches"][0]
        self.assertEqual(entry["verdict"], VERDICT_POSSIBLE)
        self.assertEqual(entry["score"], 50.0)
        self.assertEqual(entry["coverage"], 0.5)
        self.assertEqual(entry["covered_keywords"], 1)
        self.assertEqual(entry["gap"], 0.5)

    def test_sorting_by_score_then_name(self):
        """الترتيب بالدرجة تنازليًا ثم الاسم عند التعادل."""
        tie_b = _niche("تخصص ب", OPPORTUNITY["keywords"])
        tie_a = _niche("تخصص أ", OPPORTUNITY["keywords"])
        result = find_micro_niches([tie_b, POSSIBLE, tie_a],
                                   POSSIBLE_LIBRARY)
        names = [entry["name"] for entry in result["niches"]]
        self.assertEqual(names, ["تخصص أ", "تخصص ب", "قصص الكرم"])
        scores = [entry["score"] for entry in result["niches"]]
        self.assertEqual(scores, [90.0, 90.0, 50.0])

    def test_volume_cap_at_reference(self):
        """حجم فوق المرجع يُقصّ: متوسط 20000 يعطي 30.0 كاملة."""
        niche = _niche("قصص مشهورة",
                       [_kw("مشهور", volume=20000, competition=0)])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertEqual(entry["components"]["volume"], 30.0)
        self.assertEqual(entry["score"], 100.0)


class TestNoDemand(unittest.TestCase):
    """«بلا طلب»: كل الأحجام معروفة والإجمالي < 500."""

    def test_no_demand_despite_high_score(self):
        """بلا طلب رغم منافسة منخفضة وفجوة كاملة: إجمالي 350."""
        niche = _niche("قصص الصبر", [
            _kw("الصبر", volume=200, competition=10),
            _kw("الرضا", volume=150, competition=10),
        ])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertEqual(entry["verdict"], VERDICT_NO_DEMAND)
        self.assertEqual(entry["total_volume"], 350)
        self.assertEqual(entry["avg_volume"], 175.0)

    def test_no_demand_boundary_total_500_is_not_no_demand(self):
        """إجمالي 500 تمامًا ليس «بلا طلب» — الحد «أقل من 500»."""
        niche = _niche("قصص الأمانة", [
            _kw("الأمانة", volume=300, competition=20),
            _kw("الوفاء", volume=200, competition=20),
        ])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertEqual(entry["total_volume"], 500)
        self.assertNotEqual(entry["verdict"], VERDICT_NO_DEMAND)
        self.assertEqual(entry["verdict"], VERDICT_OPPORTUNITY)
        self.assertEqual(entry["score"], 63.5)


class TestUnknownVolume(unittest.TestCase):
    """حجم مجهول: «غير مقاس» لا «بلا طلب» أبدًا."""

    def test_all_volumes_unknown_shows_unmeasured(self):
        """كل الأحجام مجهولة: الحالة «غير مقاس» والحجم صفر في الدرجة."""
        niche = _niche("قصص الكرم", [
            _kw("الكرم", competition=20),
            _kw("الجود", competition=30),
        ])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertEqual(entry["volume_status"], UNMEASURED)
        self.assertIsNone(entry["total_volume"])
        self.assertIsNone(entry["avg_volume"])
        self.assertEqual(entry["components"]["volume"], 0.0)
        self.assertEqual(entry["score"], 60.0)
        self.assertNotEqual(entry["verdict"], VERDICT_NO_DEMAND)
        self.assertIn("غير مقاس", entry["reason"])
        self.assertIn("لا يعني", entry["reason"])

    def test_partial_unknown_volume_uses_known_only(self):
        """حجم معروف جزئيًا: الإجمالي والمتوسط من المعروف فقط."""
        niche = _niche("قصص مختلطة", [
            _kw("الصدقة", volume=4000, competition=20),
            _kw("الكرم", competition=20),
        ])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertEqual(entry["total_volume"], 4000)
        self.assertEqual(entry["avg_volume"], 4000.0)
        self.assertEqual(entry["keywords_with_volume"], 1)
        self.assertEqual(entry["volume_status"], "مقاس")
        self.assertNotEqual(entry["verdict"], VERDICT_NO_DEMAND)
        self.assertEqual(entry["score"], 86.0)

    def test_no_competition_known_is_unmeasured(self):
        """بلا منافسة معروفة: المتوسط None وجزء المنافسة صفر."""
        niche = _niche("قصص بلا منافسة",
                       [_kw("الصدقة", volume=5000)])
        result = find_micro_niches([niche])
        entry = result["niches"][0]
        self.assertIsNone(entry["avg_competition"])
        self.assertEqual(entry["components"]["competition"], 0.0)
        self.assertEqual(entry["score"], 60.0)
        self.assertIn("غير مقاس", entry["reason"])


class TestCoverage(unittest.TestCase):
    """تغطية المكتبة: كاملة وجزئية وتطبيع عربي."""

    def test_full_library_coverage_gap_zero(self):
        """تغطية كاملة: 1.0 والفجوة صفر وجزء الفجوة صفر."""
        niche = _niche("قصص الصلاة والصدقة", [
            _kw("الصلاة", volume=1000, competition=50),
            _kw("الصدقة", volume=1000, competition=50),
        ])
        library = [
            {"title": "قصة الصلاة في حياة رجل"},
            {"title": "فضل الصدقة"},
        ]
        result = find_micro_niches([niche], library)
        entry = result["niches"][0]
        self.assertEqual(entry["coverage"], 1.0)
        self.assertEqual(entry["covered_keywords"], 2)
        self.assertEqual(entry["gap"], 0.0)
        self.assertEqual(entry["components"]["gap"], 0.0)
        self.assertEqual(entry["score"], 26.0)
        # درجة < 40 مع منافسة 50 → مزدحم، لا «فرصة» ولا «ممكن» قوية.
        self.assertEqual(entry["verdict"], VERDICT_CROWDED)

    def test_empty_library_coverage_zero(self):
        """بلا مكتبة: التغطية صفر والفجوة كاملة."""
        result = find_micro_niches([OPPORTUNITY], None)
        entry = result["niches"][0]
        self.assertEqual(entry["coverage"], 0.0)
        self.assertEqual(entry["covered_keywords"], 0)
        result_empty = find_micro_niches([OPPORTUNITY], [])
        self.assertEqual(result_empty["niches"][0]["coverage"], 0.0)
        self.assertEqual(result_empty["library_size"], 0)

    def test_topic_field_counts_for_coverage(self):
        """موضوع عنصر المكتبة (topic) يُحسب في التغطية كالعنوان."""
        niche = _niche("قصص الصدقة",
                       [_kw("الصدقة", volume=1000, competition=50)])
        library = [{"title": "قصة عادية", "topic": "فضل الصدقة"}]
        result = find_micro_niches([niche], library)
        self.assertEqual(result["niches"][0]["coverage"], 1.0)

    def test_arabic_normalization_matches(self):
        """التطبيع يطابق: تشكيل وتطويل و«إ/آ/ة/ى» مع الصيغ المبسطة."""
        niche = _niche("قصص متنوعة", [
            _kw("الصَّلاة", volume=1000, competition=50),
            _kw("التَّوبة", volume=1000, competition=50),
            _kw("إحسان", volume=1000, competition=50),
            _kw("الصـلاة", volume=1000, competition=50),
        ])
        library = [{"title": "قصه عن الصلاه والتوبه والاحسان"}]
        result = find_micro_niches([niche], library)
        entry = result["niches"][0]
        self.assertEqual(entry["covered_keywords"], 4)
        self.assertEqual(entry["coverage"], 1.0)


class TestInvalidInputs(unittest.TestCase):
    """مدخلات فاسدة → ValueError عربي."""

    def test_invalid_empty_list(self):
        with self.assertRaises(ValueError):
            find_micro_niches([])

    def test_invalid_not_a_list(self):
        with self.assertRaises(ValueError):
            find_micro_niches(123)
        with self.assertRaises(ValueError):
            find_micro_niches("ليست json")

    def test_invalid_niche_without_name(self):
        with self.assertRaises(ValueError):
            find_micro_niches([{"keywords": [_kw("الصدقة")]}])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("   ", [_kw("الصدقة")])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche(123, [_kw("الصدقة")])])

    def test_invalid_niche_not_a_dict(self):
        with self.assertRaises(ValueError):
            find_micro_niches(["ليست قاموسًا"])

    def test_invalid_competition_out_of_range(self):
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", competition=101)])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", competition=-1)])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", competition="عالية")])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", competition=True)])])

    def test_invalid_negative_volume(self):
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", volume=-5)])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", volume="كثير")])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("ك", volume=True)])])

    def test_invalid_empty_keyword(self):
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", [_kw("   ")])])
        with self.assertRaises(ValueError):
            find_micro_niches([_niche("ت", ["ليست قاموسًا"])])

    def test_invalid_keywords_not_a_list(self):
        with self.assertRaises(ValueError):
            find_micro_niches([{"name": "ت", "keywords": "الصدقة"}])

    def test_invalid_library_entry_without_title(self):
        with self.assertRaises(ValueError):
            find_micro_niches([OPPORTUNITY], [{"topic": "الصدقة"}])
        with self.assertRaises(ValueError):
            find_micro_niches([OPPORTUNITY], ["ليست قاموسًا"])

    def test_deterministic(self):
        """نفس المدخل مرتين: نفس النتيجة تمامًا."""
        niches = [OPPORTUNITY, POSSIBLE]
        first = find_micro_niches(niches, POSSIBLE_LIBRARY)
        second = find_micro_niches(niches, POSSIBLE_LIBRARY)
        self.assertEqual(first, second)


class TestJsonAndReport(unittest.TestCase):
    """المدخل JSON والمخرج JSON والتقرير العربي."""

    def test_load_niches_json_list(self):
        text = json.dumps([OPPORTUNITY, POSSIBLE], ensure_ascii=False)
        niches, library = load_niches_json(text)
        self.assertEqual(len(niches), 2)
        self.assertEqual(niches[0]["name"], "قصص الصدقة")
        self.assertEqual(library, [])

    def test_load_niches_json_dict_with_library(self):
        payload = {"niches": [OPPORTUNITY], "library": POSSIBLE_LIBRARY}
        text = json.dumps(payload, ensure_ascii=False)
        niches, library = load_niches_json(text)
        self.assertEqual(len(niches), 1)
        self.assertEqual(len(library), 1)
        self.assertEqual(library[0]["title"], "قصة عن الكرم")

    def test_load_niches_json_broken(self):
        with self.assertRaises(ValueError):
            load_niches_json("{ليس json")
        with self.assertRaises(ValueError):
            load_niches_json(json.dumps({"title": "ليست تخصصات"}))
        with self.assertRaises(ValueError):
            load_niches_json("[]")
        with self.assertRaises(ValueError):
            load_niches_json(123)

    def test_find_accepts_json_string(self):
        payload = {"niches": [OPPORTUNITY, POSSIBLE],
                   "library": POSSIBLE_LIBRARY}
        text = json.dumps(payload, ensure_ascii=False)
        result = find_micro_niches(text)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["library_size"], 1)
        self.assertEqual(result["niches"][0]["name"], "قصص الصدقة")

    def test_to_json_round_trip(self):
        result = find_micro_niches([OPPORTUNITY, POSSIBLE],
                                   POSSIBLE_LIBRARY)
        text = to_json(result)
        self.assertTrue(text.endswith("\n"))
        self.assertIn("فرصة", text)  # عربي خام بلا ASCII هارب.
        payload = json.loads(text)
        self.assertEqual(payload["niches"][0]["score"], 90.0)
        self.assertEqual(payload["niches"][0]["verdict"], VERDICT_OPPORTUNITY)
        self.assertEqual(payload["niches"][1]["score"], 50.0)
        self.assertIn("reference", payload)
        self.assertEqual(payload["reference"]["volume_reference"], 5000)

    def test_to_json_rejects_bad_result(self):
        with self.assertRaises(ValueError):
            to_json("ليست نتيجة")

    def test_report_contents(self):
        result = find_micro_niches([OPPORTUNITY, POSSIBLE],
                                   POSSIBLE_LIBRARY)
        report = format_report(result)
        self.assertIn("قصص الصدقة", report)
        self.assertIn("فرصة", report)
        self.assertIn("ممكن", report)
        self.assertIn("90.0/100", report)
        self.assertIn("50.0/100", report)
        self.assertIn("منافسة منخفضة 40", report)
        self.assertIn("لا يعني «بلا طلب»", report)
        self.assertIn("بلا طلب", report)

    def test_report_shows_unmeasured_volume(self):
        niche = _niche("قصص الكرم", [_kw("الكرم", competition=20)])
        report = format_report(find_micro_niches([niche]))
        self.assertIn("غير مقاس", report)

    def test_report_rejects_bad_result(self):
        with self.assertRaises(ValueError):
            format_report({"niches": []})
        with self.assertRaises(ValueError):
            format_report("ليست نتيجة")


if __name__ == "__main__":
    unittest.main()
