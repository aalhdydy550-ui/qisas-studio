#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مُحسِّن المحتوى (Content Optimizer) — جولة v0.1.61 (W2).

الأرقام المتوقعة محسوبة يدويًا من الأوزان الموثقة في
``lib/content_optimizer.py`` (العنوان 15، الوصف 10، الكثافة 20،
تغطية العبارات 30، طول النص 10، البنية 10، طول العنوان 5؛
والنطاق الصحي 55–75). بيانات الاختبار تركيبية.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import content_optimizer
from lib.content_optimizer import format_report, optimize_content, to_json

# جملة أساس بلا كلمة مفتاحية: 12 كلمة بالضبط.
BASE = "عاش الرجل الصالح في قرية صغيرة يعمل بجد ويساعد جيرانه كل يوم"
KEYWORD = "الصلاة"
TITLE = "قصة الرجل الصالح والصلاة التي غيرت حياته"  # 42 حرفًا، فيها الكلمة.
DESCRIPTION = "قصة مؤثرة عن الصلاة وأثرها في حياة الإنسان وكيف تغيّر القلوب"
PHRASES = [
    {"phrase": "الصلاة نور", "used_by_top": 18},
    {"phrase": "حافظ على صلاتك", "used_by_top": 15},
    {"phrase": "الخير يبقى", "used_by_top": 12},
    {"phrase": "بر الوالدين", "used_by_top": 10},
]


def _body(repeats, suffix=""):
    """نص من تكرار جملة الأساس + لاحقة اختيارية."""
    text = " ".join([BASE] * repeats)
    return text + suffix if suffix else text


class TestHealthyScore(unittest.TestCase):
    def test_healthy_score(self):
        # 199 كلمة، 3 تكرارات (كثافة 1.5% داخل النطاق):
        # 15 + 10 + 20 + 7.5 + 5 + 10 + 5 = 72.5 — صحي.
        body = _body(16, " الصلاة الصلاة الصلاة العبرة أن الخير يبقى")
        result = optimize_content(TITLE, DESCRIPTION, body, KEYWORD, PHRASES)
        self.assertEqual(result["score"], 72.5)
        self.assertEqual(result["verdict"], "صحي")
        self.assertIsNone(result["warning"])
        self.assertEqual(result["healthy_range"], [55, 75])
        self.assertEqual(result["found_phrases"], ["الخير يبقى"])
        self.assertEqual(result["missing_phrases"],
                         ["الصلاة نور", "حافظ على صلاتك", "بر الوالدين"])
        self.assertEqual(result["recommendations"], [])
        density = result["components"]["keyword_density"]
        self.assertEqual(density["occurrences"], 3)
        self.assertEqual(density["word_count"], 199)
        self.assertTrue(density["in_range"])
        self.assertEqual(density["points"], 20)

    def test_empty_recommended_phrases(self):
        # بلا عبارات موصى بها: التغطية صفر «غير مقاس»، والباقي
        # 15 + 10 + 20 + 0 + 5 + 10 + 5 = 65 — صحي.
        body = _body(16, " الصلاة الصلاة الصلاة العبرة أن الخير يبقى")
        for phrases in (None, []):
            with self.subTest(phrases=phrases):
                result = optimize_content(TITLE, DESCRIPTION, body,
                                          KEYWORD, phrases)
                self.assertEqual(result["score"], 65.0)
                self.assertEqual(result["verdict"], "صحي")
                self.assertEqual(
                    result["components"]["phrase_coverage"]["points"], 0.0)
                self.assertEqual(
                    result["components"]["phrase_coverage"]["note"],
                    "غير مقاس — بلا عبارات موصى بها")
                self.assertEqual(result["missing_phrases"], [])
                self.assertEqual(result["found_phrases"], [])


class TestLowScore(unittest.TestCase):
    def test_low_score_with_missing_phrases(self):
        # صفر في كل مكوّن: الدرجة 0 — يحتاج تحسين، والغائب فقط.
        body = _body(5)
        result = optimize_content("قصة قصيرة", "وصف بلا كلمة",
                                  body, KEYWORD, PHRASES)
        self.assertEqual(result["score"], 0.0)
        self.assertLess(result["score"], 55)
        self.assertEqual(result["verdict"], "يحتاج تحسين")
        self.assertIsNone(result["warning"])
        self.assertEqual(result["missing_phrases"],
                         ["الصلاة نور", "حافظ على صلاتك",
                          "الخير يبقى", "بر الوالدين"])
        self.assertLessEqual(len(result["missing_phrases"]), 5)
        self.assertTrue(result["recommendations"])
        self.assertIn("الصلاة نور", result["recommendations"][0])

    def test_missing_phrases_capped_at_five(self):
        # 7 عبارات غائبة → القائمة 5 كحد أقصى، الأكثر استخدامًا أولًا.
        phrases = [{"phrase": f"عبارة {i}", "used_by_top": i}
                   for i in range(7)]
        result = optimize_content("قصة قصيرة", "وصف بلا كلمة",
                                  _body(5), KEYWORD, phrases)
        self.assertEqual(len(result["missing_phrases"]), 5)
        self.assertEqual(result["missing_phrases"],
                         ["عبارة 6", "عبارة 5", "عبارة 4",
                          "عبارة 3", "عبارة 2"])


class TestOverstuffedScore(unittest.TestCase):
    def test_overstuffed_no_add_recommendations(self):
        # كل المكوّنات كاملة: 15 + 10 + 20 + 30 + 10 + 10 + 5 = 100.
        body = _body(
            25,
            " الصلاة الصلاة الصلاة الصلاة الصلاة نور حافظ على صلاتك "
            "العبرة أن الخير يبقى بر الوالدين")
        result = optimize_content(TITLE, DESCRIPTION, body, KEYWORD, PHRASES)
        self.assertEqual(result["score"], 100.0)
        self.assertGreater(result["score"], 75)
        self.assertEqual(result["verdict"], "مبالغ فيه — خطر حشو")
        self.assertEqual(result["missing_phrases"], [])
        self.assertIn("لا ترفع الدرجة أكثر — النطاق الصحي 55–75",
                      result["warning"])
        # بلا أي توصية إضافة كلمات — حذف/تخفيف فقط.
        self.assertTrue(result["recommendations"])
        self.assertNotIn("أضف", " ".join(result["recommendations"]))


class TestDensity(unittest.TestCase):
    def test_density_out_of_range_zero(self):
        # 10 تكرارات / 100 كلمة = 10% — خارج النطاق البعيد → صفر.
        body = " ".join(["الصلاة"] * 10 + ["كلمة"] * 90)
        result = optimize_content(TITLE, DESCRIPTION, body, KEYWORD, [])
        density = result["components"]["keyword_density"]
        self.assertEqual(density["density"], 0.1)
        self.assertEqual(density["points"], 0.0)
        self.assertFalse(density["in_range"])

    def test_density_below_range_partial(self):
        # تكرار واحد / 301 كلمة ≈ 0.33% — قريب من النطاق من تحت → جزئي.
        body = _body(25, " الصلاة")
        result = optimize_content(TITLE, DESCRIPTION, body, KEYWORD, [])
        points = result["components"]["keyword_density"]["points"]
        self.assertEqual(points, 13.3)
        self.assertGreater(points, 0)
        self.assertLess(points, 20)

    def test_density_above_range_partial(self):
        # 6 تكرارات / 200 كلمة = 3% — قريب من النطاق من فوق → جزئي 16.
        body = _body(16, " الصلاة الصلاة الصلاة الصلاة الصلاة الصلاة "
                          "كلمة كلمة")
        result = optimize_content(TITLE, DESCRIPTION, body, KEYWORD, [])
        points = result["components"]["keyword_density"]["points"]
        self.assertEqual(points, 16.0)
        self.assertGreater(points, 0)
        self.assertLess(points, 20)

    def test_density_zero_when_keyword_absent(self):
        body = _body(13)
        result = optimize_content(TITLE, DESCRIPTION, body, KEYWORD, [])
        density = result["components"]["keyword_density"]
        self.assertEqual(density["occurrences"], 0)
        self.assertEqual(density["points"], 0.0)


class TestComponents(unittest.TestCase):
    def test_title_keyword_and_length(self):
        body = _body(13)
        # عنوان قصير فيه الكلمة: 15 للكلمة، وصفر للطول.
        short = optimize_content("الصلاة نور", DESCRIPTION, body,
                                 KEYWORD, [])
        self.assertEqual(short["components"]["keyword_in_title"]["points"],
                         15)
        self.assertEqual(short["components"]["title_length"]["points"], 0)
        # عنوان 42 حرفًا بلا كلمة: صفر للكلمة، و5 للطول.
        no_keyword = optimize_content(
            "قصة الرجل الصالح الذي غير حياته بالخير",
            DESCRIPTION, body, KEYWORD, [])
        self.assertEqual(
            no_keyword["components"]["keyword_in_title"]["points"], 0)
        self.assertEqual(no_keyword["components"]["title_length"]["points"],
                         5)

    def test_title_length_boundaries(self):
        body = _body(13)
        # 30 حرفًا بالضبط → 5 نقاط؛ و29 حرفًا → صفر.
        exact = optimize_content("قصة الرجل الصالح والصلاة نوران",
                                 DESCRIPTION, body, KEYWORD, [])
        self.assertEqual(exact["components"]["title_length"]["length"], 30)
        self.assertEqual(exact["components"]["title_length"]["points"], 5)
        short = optimize_content("قصة الرجل الصالح والصلاة نورا",
                                 DESCRIPTION, body, KEYWORD, [])
        self.assertEqual(short["components"]["title_length"]["length"], 29)
        self.assertEqual(short["components"]["title_length"]["points"], 0)

    def test_description_first_120_chars(self):
        body = _body(13)
        filler = "مقدمة طويلة عن القصة وأحداثها المشوقة "  # 39 حرفًا.
        # الكلمة بعد 156 حرفًا → خارج أول 120 → صفر.
        late = optimize_content(TITLE, filler * 4 + "الصلاة", body,
                                KEYWORD, [])
        self.assertEqual(
            late["components"]["keyword_in_description_start"]["points"], 0)
        # الكلمة في أول الوصف → 10.
        early = optimize_content(TITLE, "الصلاة نور وهداية " + filler,
                                 body, KEYWORD, [])
        self.assertEqual(
            early["components"]["keyword_in_description_start"]["points"],
            10)

    def test_structure_moral_marker_and_closing_question(self):
        # علامة العبرة → 10.
        moral = optimize_content(TITLE, DESCRIPTION,
                                 _body(13, " العبرة أن الخير يبقى"),
                                 KEYWORD, [])
        self.assertEqual(moral["components"]["structure"]["points"], 10)
        self.assertTrue(moral["components"]["structure"]["has_moral_marker"])
        # سؤال ختامي → 10.
        question = optimize_content(
            TITLE, DESCRIPTION,
            _body(13, " فما رأيك في هذه القصة؟"), KEYWORD, [])
        self.assertEqual(question["components"]["structure"]["points"], 10)
        self.assertTrue(
            question["components"]["structure"]["has_closing_question"])
        self.assertFalse(
            question["components"]["structure"]["has_moral_marker"])
        # بلا عبرة وبلا سؤال → صفر.
        plain = optimize_content(TITLE, DESCRIPTION, _body(13),
                                 KEYWORD, [])
        self.assertEqual(plain["components"]["structure"]["points"], 0)

    def test_body_length_points(self):
        # 156 كلمة → 5؛ و315 كلمة → 10؛ و60 كلمة → صفر.
        self.assertEqual(
            optimize_content(TITLE, DESCRIPTION, _body(13), KEYWORD,
                             [])["components"]["body_length"]["points"], 5)
        self.assertEqual(
            optimize_content(TITLE, DESCRIPTION, _body(25) + " كلمة " * 15,
                             KEYWORD,
                             [])["components"]["body_length"]["points"], 10)
        self.assertEqual(
            optimize_content(TITLE, DESCRIPTION, _body(5), KEYWORD,
                             [])["components"]["body_length"]["points"], 0)


class TestNormalization(unittest.TestCase):
    def test_normalization_variants_match(self):
        # ة/ه والتشكيل والتطويل تُطبَّع قبل المطابقة.
        body = _body(13, " الصَّلاة")
        result = optimize_content("قصة الصلاه التي غيرت حياة الرجل",
                                  DESCRIPTION, body, KEYWORD, [])
        self.assertEqual(result["components"]["keyword_in_title"]["points"],
                         15)
        self.assertEqual(
            result["components"]["keyword_density"]["occurrences"], 1)
        self.assertEqual(
            result["components"]["keyword_density"]["points"], 20)


class TestInvalidInputs(unittest.TestCase):
    def test_empty_title(self):
        body = _body(13)
        for title in ("", "   "):
            with self.subTest(title=title):
                with self.assertRaises(ValueError) as ctx:
                    optimize_content(title, DESCRIPTION, body, KEYWORD, [])
                self.assertIn("العنوان", str(ctx.exception))

    def test_invalid_inputs(self):
        body = _body(13)
        cases = [
            (TITLE, DESCRIPTION, "", KEYWORD, []),       # نص فارغ
            (TITLE, DESCRIPTION, "   ", KEYWORD, []),    # نص مسافات
            (TITLE, DESCRIPTION, body, "", []),           # كلمة فارغة
            (TITLE, DESCRIPTION, body, "   ", []),        # كلمة مسافات
            (123, DESCRIPTION, body, KEYWORD, []),        # عنوان غير نص
            (TITLE, DESCRIPTION, body, None, []),         # كلمة غير نص
            (TITLE, 123, body, KEYWORD, []),              # وصف غير نص
            (TITLE, DESCRIPTION, 123, KEYWORD, []),       # نص غير نص
        ]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    optimize_content(*args)

    def test_invalid_recommended_phrases(self):
        body = _body(13)
        cases = [
            [{"phrase": "الصلاة نور", "used_by_top": 21}],  # فوق 20
            [{"phrase": "الصلاة نور", "used_by_top": -1}],  # سالب
            [{"phrase": "الصلاة نور", "used_by_top": True}],  # bool
            [{"phrase": "", "used_by_top": 5}],               # عبارة فارغة
            [{"used_by_top": 5}],                            # بلا phrase
            ["الصلاة نور"],                                  # عنصر غير قاموس
            {"phrase": "الصلاة نور"},                        # ليست قائمة
        ]
        for phrases in cases:
            with self.subTest(phrases=phrases):
                with self.assertRaises(ValueError):
                    optimize_content(TITLE, DESCRIPTION, body, KEYWORD,
                                     phrases)


class TestOutput(unittest.TestCase):
    def _healthy_result(self):
        body = _body(16, " الصلاة الصلاة الصلاة العبرة أن الخير يبقى")
        return optimize_content(TITLE, DESCRIPTION, body, KEYWORD, PHRASES)

    def _low_result(self):
        return optimize_content("قصة قصيرة", "وصف بلا كلمة", _body(5),
                                KEYWORD, PHRASES)

    def _high_result(self):
        body = _body(
            25,
            " الصلاة الصلاة الصلاة الصلاة الصلاة نور حافظ على صلاتك "
            "العبرة أن الخير يبقى بر الوالدين")
        return optimize_content(TITLE, DESCRIPTION, body, KEYWORD, PHRASES)

    def test_to_json_roundtrip(self):
        result = self._healthy_result()
        text = to_json(result)
        self.assertTrue(text.endswith("\n"))
        self.assertIn("الصلاة", text)  # عربي غير هارب (ensure_ascii=False)
        self.assertEqual(json.loads(text)["score"], 72.5)
        with self.assertRaises(ValueError):
            to_json("ليست نتيجة")

    def test_format_report_always_shows_healthy_range(self):
        for result in (self._healthy_result(), self._low_result(),
                       self._high_result()):
            with self.subTest(verdict=result["verdict"]):
                report = format_report(result)
                self.assertIn("النطاق الصحي", report)
                self.assertIn("55–75", report)
        self.assertIn("لا ترفع الدرجة أكثر",
                      format_report(self._high_result()))
        self.assertIn("الصلاة نور", format_report(self._low_result()))
        self.assertIn("لا توصيات", format_report(self._healthy_result()))
        with self.assertRaises(ValueError):
            format_report({})
        with self.assertRaises(ValueError):
            format_report("ليست نتيجة")


if __name__ == "__main__":
    unittest.main()
