#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات موجز بحث الموضوع قبل الكتابة — جولة v0.1.58 (W5).

بيانات الترند هنا **حقيقية** من تحليل ترند TikTok
2026-11-26 (``~/workspace/studio-work/tiktok-trends/
2026-11-26-ANALYSIS-AR.md``): العناوين والهوكات والأنماط
والأرقام كما وردت في التحليل (1.7 مليون إعجاب لفيديو
الصلاة، 420 ألفًا لسلسلة «جزء 30»، أعلى حفظ 20.9%،
أعلى مشاركة 37%). الدرجات الرقمية للمرشحين درجات W1
المحسوبة — لا تُقرأ كأرقام مشاهدات. عناوين الطابور
تركيبية لأغراض الاختبار فقط.
"""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import topic_brief
from lib.topic_brief import BriefError, build_brief, main, \
    titles_from_queue_text


def _candidate(title, hook, moral_angle, pattern, score,
               source_url=""):
    """مرشح ترند بصيغة W1 — الحقول السبعة الموثقة في الخطة."""
    return {"title": title, "hook": hook,
            "moral_angle": moral_angle, "source_url": source_url,
            "pattern": pattern, "score": score,
            "reason": "مرشح اختبار"}


# --- بيانات ترند حقيقية (تحليل 2026-11-26) ---
# 1. «أيقظ أولاده للصلاة» — 1.7M إعجاب، 162K مفضلة،
#    170.3K مشاركة. الهوك: «ايقضهم للصلاة».
PRAYER = _candidate(
    "قصة الرجل الذي أيقظ أولاده للصلاة ورزقهم الله من حيث "
    "لا يحتسبون",
    "أيقظ أولاده للصلاة",
    "الصلاة تجلب الرزق",
    "إطار ديني/أخلاقي", 9.5,
    "https://www.tiktok.com/@food29797/video/7590733365557366038")
# 2. «جزء 30 | حفر حفرة للنبي» — 420K إعجاب؛ منفردات
#    الحساب نفسه 3–4K فقط — السلسلة هي الفرق.
PART30 = _candidate(
    "جزء 30 | قصة الرجل الذي حفر حفرة للنبي ﷺ",
    "جزء 30",
    "عاقبة الحقد على النبي",
    "سلسلة مرقمة", 9.0,
    "https://www.tiktok.com/@abdulrah363/video/7579926707092638998")
# 3. «الأب وكيس المسامير» — 10.3K إعجاب، 3,855 مشاركة
#    (37% — أعلى نسبة مشاركة في التحليل).
NAILS = _candidate(
    "قصة الأب وكيس المسامير",
    "نزع كل المسامير... لكن الأثر بقى",
    "أثر الكلام الجارح",
    "مفارقة", 8.5,
    "https://www.tiktok.com/@raawialazman/video/7646863554338901270")
# 4. «غيط القصب» — 175K إعجاب، 36.5K مفضلة (20.9% —
#    أعلى نسبة حفظ) — رعب ريفي: مستبعد من الخط.
SUGARCANE = _candidate(
    "غيط القصب.. قصة حقيقية ملهاش تفسير",
    "ملهاش تفسير",
    "الغموض الريفي",
    "رعب ريفي/غامض", 8.0,
    "https://www.tiktok.com/@7beeeb/video/7689209168020000020")
# 5. «أغلق على زوجته بالقفل وسافر» — 7,056 إعجاب.
LOCKED_WIFE = _candidate(
    "قصة الرجل الذي أغلق على زوجته بالقفل وسافر — القصة الكاملة",
    "أغلق على زوجته بالقفل وسافر",
    "الظلم الزوجي وعاقبته",
    "عنوان صادم", 7.0,
    "https://www.tiktok.com/@qss6532/video/7650578618220809492")

REAL_CANDIDATES = [PRAYER, PART30, NAILS, SUGARCANE, LOCKED_WIFE]

QUEUE_TEXT = """# طابور قصص

## في الانتظار

1. **قصة الأب وكيس المسامير** — منشور واحد
2. **قصة التاجر الأمين** — منشور واحد
3. **قصة الرجل الذي أيقظ أولاده للصلاة** — منشور واحد

## منشور
"""


class TestRealTrendData(unittest.TestCase):
    def test_winning_patterns_from_real_trends(self):
        brief = build_brief("قصص دينية وأخلاقية",
                            REAL_CANDIDATES, [])
        patterns = {p["pattern"]: p
                    for p in brief["winning_patterns"]}
        self.assertEqual(
            patterns["إطار ديني/أخلاقي"]["count"], 1)
        self.assertEqual(
            patterns["إطار ديني/أخلاقي"]["best_score"], 9.5)
        self.assertEqual(
            patterns["سلسلة مرقمة"]["example_title"],
            PART30["title"])
        # الرعب مستبعد من الأنماط الرابحة مهما علت درجته.
        self.assertNotIn("رعب ريفي/غامض", patterns)
        self.assertEqual(brief["theme"], "قصص دينية وأخلاقية")

    def test_winning_hooks_sorted_by_score_horror_excluded(self):
        brief = build_brief("قصص دينية وأخلاقية",
                            REAL_CANDIDATES, [])
        hooks = [h["hook"] for h in brief["winning_hooks"]]
        self.assertEqual(hooks[0], "أيقظ أولاده للصلاة")
        self.assertEqual(hooks[1], "جزء 30")
        self.assertEqual(
            hooks[2], "نزع كل المسامير... لكن الأثر بقى")
        self.assertNotIn("ملهاش تفسير", hooks)

    def test_brief_text_contains_evidence_and_avoid_list(self):
        brief = build_brief("قصص دينية وأخلاقية",
                            REAL_CANDIDATES, [])
        text = brief["brief_text"]
        self.assertIn("قصص دينية وأخلاقية", text)
        self.assertIn("إطار ديني/أخلاقي", text)
        self.assertIn("أيقظ أولاده للصلاة", text)
        # المستبعد يُذكر صراحة في الموجز.
        self.assertIn("غيط القصب", text)
        self.assertIn("مستبعد", text)
        # ما يُتجنَّب دائمًا في نص الموجز.
        self.assertIn("بلا موسيقى", text)
        self.assertIn("بلا بوابة متابعة", text)
        self.assertIn("الراوي رجل", text)
        self.assertIn("أسفل الصورة", text)

    def test_brief_text_notes_hook_title(self):
        # لمسة ربط المنسق (جولة v0.1.58): الهوك يظهر أيضًا
        # عنوانًا كبيرًا مكتوبًا أول 3 ثوانٍ (وحدة hook_title).
        brief = build_brief("قصص دينية وأخلاقية",
                            REAL_CANDIDATES, [])
        text = brief["brief_text"]
        self.assertIn("عنوانًا كبيرًا مكتوبًا", text)
        self.assertIn("أول 3 ثوانٍ", text)

    def test_uncovered_angles_real_data(self):
        # الطابور يحوي «التاجر الأمين» فقط كعنوان غير متداخل؛
        # فزوايا الصلاة والكلام الجارح غير مغطاة.
        brief = build_brief("قصص دينية وأخلاقية",
                            REAL_CANDIDATES,
                            ["قصة التاجر الأمين"])
        self.assertIn("الصلاة تجلب الرزق",
                      brief["uncovered_angles"])
        self.assertIn("أثر الكلام الجارح",
                      brief["uncovered_angles"])
        self.assertIn("الظلم الزوجي وعاقبته",
                      brief["uncovered_angles"])


class TestDuplicatesAndCoverage(unittest.TestCase):
    def test_duplicate_candidate_title_flagged_in_brief(self):
        brief = build_brief("قصص أخلاقية", REAL_CANDIDATES,
                            ["قصة الأب وكيس المسامير"])
        self.assertIn("قصة الأب وكيس المسامير",
                      brief["existing_titles"])
        self.assertIn("قصة الأب وكيس المسامير",
                      brief["brief_text"])
        self.assertIn("تنبيه تكرار", brief["brief_text"])

    def test_covered_angle_not_uncovered(self):
        # عنوان الطابور «أيقظ أولاده للصلاة» يشارك زاوية
        # الصلاة كلمة «الصلاة» — فالزاوية مغطاة.
        brief = build_brief("قصص دينية", [PRAYER],
                            ["قصة الرجل الذي أيقظ أولاده للصلاة"])
        self.assertNotIn("الصلاة تجلب الرزق",
                         brief["uncovered_angles"])
        self.assertEqual(brief["uncovered_angles"], [])

    def test_hook_dedup_keeps_highest_score(self):
        dup = _candidate("عنوان آخر", "أيقظ أولاده للصلاة",
                         "زاوية أخرى", "إطار ديني/أخلاقي", 5.0)
        brief = build_brief("موضوع", [PRAYER, dup], [])
        hooks = [h for h in brief["winning_hooks"]
                 if h["hook"] == "أيقظ أولاده للصلاة"]
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0]["score"], 9.5)


class TestEdgeCases(unittest.TestCase):
    def test_no_candidates(self):
        brief = build_brief("موضوع بلا ترند", [], [])
        self.assertEqual(brief["winning_patterns"], [])
        self.assertEqual(brief["winning_hooks"], [])
        self.assertEqual(brief["uncovered_angles"], [])
        self.assertIn("لا مرشحي ترند", brief["brief_text"])

    def test_empty_queue(self):
        brief = build_brief("موضوع", [PRAYER], [])
        self.assertEqual(brief["existing_titles"], [])
        self.assertIn("الطابور فارغ", brief["brief_text"])

    def test_score_missing_shown_as_not_measured(self):
        cand = _candidate("عنوان بلا درجة", "هوك بلا درجة",
                          "زاوية", "مفارقة", None)
        cand["score"] = None
        brief = build_brief("موضوع", [cand, PRAYER], [])
        hooks = brief["winning_hooks"]
        self.assertEqual(hooks[-1]["hook"], "هوك بلا درجة")
        self.assertIsNone(hooks[-1]["score"])
        self.assertIn("غير مقاس", brief["brief_text"])

    def test_deterministic(self):
        first = build_brief("موضوع", REAL_CANDIDATES,
                            ["قصة التاجر الأمين"])
        second = build_brief("موضوع", REAL_CANDIDATES,
                             ["قصة التاجر الأمين"])
        self.assertEqual(first, second)


class TestInvalidInput(unittest.TestCase):
    def test_empty_theme(self):
        with self.assertRaises(BriefError):
            build_brief("   ", [PRAYER], [])

    def test_theme_not_string(self):
        with self.assertRaises(BriefError):
            build_brief(None, [PRAYER], [])

    def test_candidates_not_list(self):
        with self.assertRaises(BriefError):
            build_brief("موضوع", {"title": "x"}, [])

    def test_candidate_not_dict(self):
        with self.assertRaises(BriefError):
            build_brief("موضوع", ["عنوان نصي"], [])

    def test_candidate_without_title(self):
        with self.assertRaises(BriefError):
            build_brief("موضوع", [{"hook": "هوك"}], [])

    def test_candidate_non_numeric_score(self):
        bad = _candidate("عنوان", "هوك", "زاوية", "نمط", "عالية")
        with self.assertRaises(BriefError):
            build_brief("موضوع", [bad], [])

    def test_existing_titles_not_list(self):
        with self.assertRaises(BriefError):
            build_brief("موضوع", [PRAYER], "عنوان واحد")

    def test_existing_title_invalid(self):
        with self.assertRaises(BriefError):
            build_brief("موضوع", [PRAYER], ["عنوان صالح", ""])


class TestQueueTextReading(unittest.TestCase):
    def test_titles_from_queue_text(self):
        titles = titles_from_queue_text(QUEUE_TEXT)
        self.assertEqual(titles, [
            "قصة الأب وكيس المسامير",
            "قصة التاجر الأمين",
            "قصة الرجل الذي أيقظ أولاده للصلاة",
        ])

    def test_titles_from_queue_text_invalid(self):
        with self.assertRaises(BriefError):
            titles_from_queue_text(None)

    def test_brief_with_queue_text_titles(self):
        titles = titles_from_queue_text(QUEUE_TEXT)
        brief = build_brief("قصص دينية وأخلاقية",
                            REAL_CANDIDATES, titles)
        # «كيس المسامير» مكرر في الطابور، و«الصلاة» مغطاة.
        self.assertIn("تنبيه تكرار", brief["brief_text"])
        self.assertNotIn("الصلاة تجلب الرزق",
                         brief["uncovered_angles"])


class TestMainCli(unittest.TestCase):
    def _run_main(self, payload, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout, stderr
        try:
            code = main(argv)
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        return code, stdout.getvalue(), stderr.getvalue()

    def test_main_json_file(self):
        payload = {"theme": "قصص دينية",
                   "candidates": [PRAYER, NAILS],
                   "existing_titles": []}
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", encoding="utf-8",
                delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            path = f.name
        try:
            code, out, _ = self._run_main(payload, [path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)
        brief = json.loads(out)
        self.assertEqual(brief["theme"], "قصص دينية")
        self.assertIn("أيقظ أولاده للصلاة", brief["brief_text"])

    def test_main_invalid_input_exits_2(self):
        payload = {"theme": "", "candidates": [], "existing_titles": []}
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", encoding="utf-8",
                delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            path = f.name
        try:
            code, _, err = self._run_main(payload, [path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 2)
        self.assertIn("خطأ", err)


if __name__ == "__main__":
    unittest.main()
