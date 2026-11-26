#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مدقق العنوان + المصغرة — بلا نشر وبلا شبكة."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import title_lint

MANQASHA = "منقشة الرغيف | الجزء 1 من 2 | قصة حقيقية"
NAJJAR = "النجار الأمين | قصة حقيقية"
KAAB = "توبة كعب بن مالك | قصة حقيقية"
LONG_TITLE = "توبة كعب بن مالك | قصة حقيقية مؤثرة عن التوبة والرجوع إلى الله"


def _codes(report):
    return [i["code"] for i in report["issues"]]


class TestEmptyTitle(unittest.TestCase):
    def test_empty_raises_arabic_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            title_lint.lint_title("")
        self.assertIn("فارغ", str(ctx.exception))

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            title_lint.lint_title("   ")

    def test_non_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            title_lint.lint_title(123)


class TestLengthAndCuts(unittest.TestCase):
    def test_real_titles_lengths(self):
        self.assertEqual(title_lint.lint_title(MANQASHA)["length"], 40)
        self.assertEqual(title_lint.lint_title(NAJJAR)["length"], 26)
        self.assertEqual(title_lint.lint_title(KAAB)["length"], 29)

    def test_exactly_40_chars_not_truncated(self):
        # منقشة على حدّ الموبايل تمامًا — لا قطع في أي سطح.
        rep = title_lint.lint_title(MANQASHA)
        self.assertFalse(rep["desktop_cut"]["truncated"])
        self.assertFalse(rep["mobile_cut"]["truncated"])
        self.assertEqual(rep["mobile_cut"]["visible"], MANQASHA)
        self.assertEqual(rep["mobile_cut"]["hidden"], "")

    def test_long_title_cut_at_both_limits(self):
        rep = title_lint.lint_title(LONG_TITLE)
        self.assertTrue(rep["desktop_cut"]["truncated"])
        self.assertTrue(rep["mobile_cut"]["truncated"])
        self.assertEqual(rep["desktop_cut"]["visible"], LONG_TITLE[:60])
        self.assertEqual(rep["desktop_cut"]["hidden"], LONG_TITLE[60:])
        self.assertEqual(rep["mobile_cut"]["visible"], LONG_TITLE[:40])
        self.assertEqual(rep["mobile_cut"]["hidden"], LONG_TITLE[40:])
        self.assertIn("TITLE-CUT-060", _codes(rep))
        self.assertIn("TITLE-CUT-040", _codes(rep))

    def test_desktop_only_cut(self):
        # بين 41 و60 حرفًا: يقطع الموبايل ولا يقطع سطح المكتب.
        title = "أ" * 50
        rep = title_lint.lint_title(title)
        self.assertFalse(rep["desktop_cut"]["truncated"])
        self.assertTrue(rep["mobile_cut"]["truncated"])
        self.assertEqual(rep["mobile_cut"]["visible"], "أ" * 40)
        self.assertEqual(rep["mobile_cut"]["hidden"], "أ" * 10)

    def test_boundary_60_and_61(self):
        self.assertFalse(title_lint.lint_title("أ" * 60)["desktop_cut"]["truncated"])
        self.assertTrue(title_lint.lint_title("أ" * 61)["desktop_cut"]["truncated"])


class TestThumbOverlap(unittest.TestCase):
    def test_thumb_repeating_title_named(self):
        rep = title_lint.lint_title(NAJJAR, "النجار الأمين")
        self.assertTrue(rep["thumb_overlap"]["repeats"])
        self.assertIn("النجار", rep["thumb_overlap"]["words"])
        self.assertIn("الأمين", rep["thumb_overlap"]["words"])
        self.assertIn("THUMB-REPEAT", _codes(rep))

    def test_thumb_different_words_same_promise_ok(self):
        rep = title_lint.lint_title(NAJJAR, "أمانة تنجي صاحبها")
        self.assertFalse(rep["thumb_overlap"]["repeats"])
        self.assertEqual(rep["thumb_overlap"]["words"], [])
        self.assertNotIn("THUMB-REPEAT", _codes(rep))

    def test_stop_words_not_counted_as_overlap(self):
        rep = title_lint.lint_title(NAJJAR, "من القصة")
        self.assertEqual(rep["thumb_overlap"]["words"], ["قصة"])

    def test_definite_article_normalized(self):
        # «نجار» بلا «ال» تطابق «النجار» في العنوان.
        rep = title_lint.lint_title(NAJJAR, "نجار صادق")
        self.assertIn("النجار", rep["thumb_overlap"]["words"])

    def test_no_thumb_no_overlap(self):
        rep = title_lint.lint_title(NAJJAR)
        self.assertIsNone(rep["thumb_text"])
        self.assertEqual(rep["thumb_words"], 0)
        self.assertFalse(rep["thumb_overlap"]["repeats"])


class TestThumbWordCount(unittest.TestCase):
    def test_three_words_allowed(self):
        rep = title_lint.lint_title(NAJJAR, "أمانة تنجي صاحبها")
        self.assertEqual(rep["thumb_words"], 3)
        self.assertFalse(rep["thumb_too_long"])

    def test_four_words_warns(self):
        rep = title_lint.lint_title(NAJJAR, "أمانة تنجي صاحبها دائما")
        self.assertEqual(rep["thumb_words"], 4)
        self.assertTrue(rep["thumb_too_long"])
        self.assertIn("THUMB-WORDS", _codes(rep))


class TestConcreteElement(unittest.TestCase):
    def test_manqasha_has_digits(self):
        rep = title_lint.lint_title(MANQASHA)
        self.assertTrue(rep["concrete"]["has_concrete"])
        self.assertIn("رقم: 1", rep["concrete"]["found"])
        self.assertIn("رقم: 2", rep["concrete"]["found"])

    def test_kaab_has_names(self):
        rep = title_lint.lint_title(KAAB)
        self.assertTrue(rep["concrete"]["has_concrete"])
        self.assertIn("اسم: كعب", rep["concrete"]["found"])
        self.assertIn("اسم: مالك", rep["concrete"]["found"])

    def test_eastern_digits_count(self):
        rep = title_lint.lint_title("قصة الجزء ٣ من ٤")
        self.assertIn("رقم: ٣", rep["concrete"]["found"])

    def test_number_word_counts(self):
        rep = title_lint.lint_title("ثلاث قصص عن الصبر")
        self.assertIn("كلمة عددية: ثلاث", rep["concrete"]["found"])

    def test_place_counts(self):
        rep = title_lint.lint_title("امرأة تبكي في مكة")
        self.assertIn("مكان: مكة", rep["concrete"]["found"])

    def test_najjar_has_no_concrete(self):
        rep = title_lint.lint_title(NAJJAR)
        self.assertFalse(rep["concrete"]["has_concrete"])
        self.assertEqual(rep["concrete"]["found"], [])
        self.assertIn("لا يوجد عنصر ملموس", rep["concrete"]["note"])
        self.assertIn("TITLE-NO-CONCRETE", _codes(rep))


class TestSpamSignals(unittest.TestCase):
    def test_three_caps_words_is_spam(self):
        rep = title_lint.lint_title("قصة FREE GIFT NOW")
        self.assertEqual(rep["spam"]["caps_words"], ["FREE", "GIFT", "NOW"])
        self.assertTrue(rep["spam"]["is_spammy"])
        self.assertIn("TITLE-SPAM", _codes(rep))

    def test_two_caps_words_allowed(self):
        rep = title_lint.lint_title("قصة FREE GIFT عن الصبر")
        self.assertFalse(rep["spam"]["is_spammy"])
        self.assertNotIn("TITLE-SPAM", _codes(rep))

    def test_three_exclamations_is_spam(self):
        rep = title_lint.lint_title("قصة مؤثرة!!!")
        self.assertEqual(rep["spam"]["exclamations"], 3)
        self.assertTrue(rep["spam"]["is_spammy"])

    def test_two_exclamations_allowed(self):
        rep = title_lint.lint_title("قصة مؤثرة!!")
        self.assertFalse(rep["spam"]["is_spammy"])

    def test_arabic_only_has_no_caps_words(self):
        rep = title_lint.lint_title(KAAB)
        self.assertEqual(rep["spam"]["caps_words"], [])


class TestVagueness(unittest.TestCase):
    def test_generic_only_is_vague(self):
        rep = title_lint.lint_title("قصة مؤثرة جدًا")
        self.assertTrue(rep["vague"])
        self.assertIn("TITLE-VAGUE", _codes(rep))

    def test_najjar_is_vague(self):
        # أدوار وصفات عامة فقط، بلا اسم ولا رقم ولا مكان.
        rep = title_lint.lint_title(NAJJAR)
        self.assertTrue(rep["vague"])

    def test_kaab_not_vague(self):
        rep = title_lint.lint_title(KAAB)
        self.assertFalse(rep["vague"])

    def test_specific_word_removes_vagueness(self):
        rep = title_lint.lint_title(MANQASHA)
        self.assertFalse(rep["vague"])


class TestRankTitles(unittest.TestCase):
    def test_fewest_issues_first(self):
        ranked = title_lint.rank_titles(["قصة مؤثرة جدًا", KAAB])
        self.assertEqual(ranked[0]["title"], KAAB)
        self.assertEqual(ranked[1]["title"], "قصة مؤثرة جدًا")

    def test_tie_keeps_input_order(self):
        ranked = title_lint.rank_titles([KAAB, MANQASHA])
        self.assertEqual([r["title"] for r in ranked], [KAAB, MANQASHA])

    def test_rank_passes_thumb_text(self):
        ranked = title_lint.rank_titles([NAJJAR, KAAB], "النجار الأمين")
        # النجار يكرر المصغرة فيتأخر؛ كعب لا يكررها.
        self.assertEqual(ranked[0]["title"], KAAB)

    def test_rank_empty_title_raises(self):
        with self.assertRaises(ValueError):
            title_lint.rank_titles([KAAB, ""])


class TestFormatReport(unittest.TestCase):
    def test_clean_report_arabic(self):
        rep = title_lint.lint_title(KAAB, "رجوع إلى الله")
        self.assertTrue(rep["ok"])
        text = title_lint.format_report(rep)
        self.assertIn("العنوان: " + KAAB, text)
        self.assertIn("الطول: 29 حرفًا", text)
        self.assertIn("لا يُقطع", text)
        self.assertIn("المصغرة لا تكرر العنوان", text)
        self.assertIn("لا مشكلات", text)

    def test_report_names_problems(self):
        rep = title_lint.lint_title(NAJJAR, "النجار الأمين")
        text = title_lint.format_report(rep)
        self.assertIn("المصغرة تكرر العنوان: النجار، الأمين", text)
        self.assertIn("لا يوجد عنصر ملموس", text)
        self.assertIn("المشكلات", text)
        self.assertIn("THUMB-REPEAT", text)

    def test_report_shows_cut_text(self):
        rep = title_lint.lint_title(LONG_TITLE)
        text = title_lint.format_report(rep)
        self.assertIn("يُقطع", text)
        self.assertIn(LONG_TITLE[:40], text)


if __name__ == "__main__":
    unittest.main()
