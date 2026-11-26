#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات لوحة تقييم الهوك (lib.hook_panel) — الجولة v0.1.57، W3.

تعمل بـ `python3 -m unittest tests.test_hook_panel -v` من
`~/workspace/studio`. بلا شبكة وبلا LLM — التقييم كله من
مسجّل dna القائم، والدرجات المتوقعة أدناه مبنية على ذلك
المسجّل لا على أي توقع مشاهدات.

هوك «عائشة الأرملة» هوك حقيقي من القناة: نص الهوك على
مصغّرة فيديو عائشة ج1 المنشور («قالوا بتحفر قبرها… طلعت
بتحفر جنة بناتها!») — ودرجته المتوقعة 2/9 هي ما يعطيه
مسجّل dna القائم لهذا النص، لا حكمًا على أداء الفيديو
الحقيقي ولا توقعًا لمشاهداته.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import hook_panel
from lib.dna import DnaError

STRONG_HOOK = ("ليه الراجل ظلم أخوه 3 مرات؟ مستحيل يفلت — الحقيقة "
               "انكشفت فجأة!")
GOOD_HOOK = "ليه الراجل ظلم أخوه؟ الحقيقة انكشفت فجأة!"
WEAK_HOOK = "يا جماعة تعالوا أحكيلكم قصة راجل طيب"
STORY_TEXT = ("كان فيه راجل ظالم. سرق مال أخوه. أنكر الوصية. "
              "هرب من القرية. العبرة أن الظلم لا يدوم.")
# هوك حقيقي من القناة: نص مصغّرة «عائشة الأرملة» ج1.
AISHA_HOOK = "قالوا بتحفر قبرها… طلعت بتحفر جنة بناتها!"

WARNING = hook_panel.WARNING


class TestScoreHooksOrdering(unittest.TestCase):
    def test_sorted_descending_known_scores(self):
        """الترتيب الصحيح لخيارات معروفة الدرجات (8، 6، 1)."""
        result = hook_panel.score_hooks(
            [WEAK_HOOK, STRONG_HOOK, GOOD_HOOK])
        self.assertEqual([p["total"] for p in result], [8, 6, 1])
        self.assertEqual([p["rank"] for p in result], [1, 2, 3])
        self.assertEqual(result[0]["hook"], STRONG_HOOK)
        self.assertEqual(result[0]["max"], 9)
        self.assertEqual(result[2]["hook"], WEAK_HOOK)

    def test_five_hooks_top_two_marked(self):
        """خمسة هوكات (قاعدة yt-script) — أفضل اثنين فقط مميزان."""
        hooks = [WEAK_HOOK, GOOD_HOOK, AISHA_HOOK,
                 "عليه سريع يمين", STRONG_HOOK]
        result = hook_panel.score_hooks(hooks)
        self.assertEqual(len(result), 5)
        self.assertEqual([p["total"] for p in result], [8, 6, 2, 2, 1])
        self.assertEqual([p["top_two"] for p in result],
                         [True, True, False, False, False])
        # التساوي (2، 2) يحفظ ترتيب الإدخال — حتمي.
        self.assertEqual(result[2]["hook"], AISHA_HOOK)

    def test_single_hook_is_top_two(self):
        result = hook_panel.score_hooks([GOOD_HOOK])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["top_two"])
        self.assertEqual(result[0]["rank"], 1)

    def test_with_story_text_payoff_measured(self):
        """مع نص القصة: العائد يُقاس والحد الأقصى 10."""
        result = hook_panel.score_hooks(
            [STRONG_HOOK], story_text=STORY_TEXT)
        self.assertEqual(result[0]["total"], 9)
        self.assertEqual(result[0]["max"], 10)
        self.assertEqual(result[0]["breakdown"]["payoff"], 1)

    def test_without_story_text_payoff_unmeasured(self):
        result = hook_panel.score_hooks([STRONG_HOOK])
        self.assertIsNone(result[0]["breakdown"]["payoff"])
        self.assertEqual(result[0]["max"], 9)


class TestAishaRealHook(unittest.TestCase):
    def test_aisha_thumbnail_hook_score_from_dna_recorder(self):
        """هوك عائشة الحقيقي يسجّل 2/9 عند مسجّل dna القائم.

        الدرجة المتوقعة مبنية على مسجّل dna القائم لا على
        توقع مشاهدات — الفيديو نفسه منشور وناجح، والتقييم
        إرشادي فقط (انظر سطر التحذير في التقرير).
        """
        result = hook_panel.score_hooks([AISHA_HOOK])
        self.assertEqual(result[0]["total"], 2)
        self.assertEqual(result[0]["max"], 9)
        self.assertEqual(result[0]["breakdown"]["direct_entry"], 1)
        self.assertIn("ضعيف", result[0]["verdict"])


class TestNormalizeBeforeScore(unittest.TestCase):
    def test_leading_number_normalized_before_scoring(self):
        """رقم بداية الهوك يُطبَّع كلمات قبل التقييم."""
        result = hook_panel.score_hooks(
            ["3 أخطاء دمرت حياة عائشة؟"])
        self.assertEqual(result[0]["hook"],
                         "ثلاثة أخطاء دمرت حياة عائشة؟")
        self.assertEqual(result[0]["total"], 5)

    def test_eastern_digits_normalized(self):
        result = hook_panel.score_hooks(
            ["٣ أخطاء دمرت حياة عائشة؟"])
        self.assertEqual(result[0]["hook"],
                         "ثلاثة أخطاء دمرت حياة عائشة؟")


class TestEmptyInput(unittest.TestCase):
    def test_empty_list_raises_arabic_error(self):
        with self.assertRaises(DnaError) as ctx:
            hook_panel.score_hooks([])
        self.assertIn("الهوكات", str(ctx.exception))

    def test_none_raises_arabic_error(self):
        with self.assertRaises(DnaError):
            hook_panel.score_hooks(None)

    def test_single_string_raises_arabic_error(self):
        with self.assertRaises(DnaError):
            hook_panel.score_hooks(GOOD_HOOK)

    def test_empty_hook_inside_list_raises(self):
        with self.assertRaises(DnaError):
            hook_panel.score_hooks([GOOD_HOOK, "   "])

    def test_format_empty_panel_raises(self):
        with self.assertRaises(DnaError):
            hook_panel.format_panel([])


class TestFormatPanel(unittest.TestCase):
    def test_warning_line_ends_every_report(self):
        """سطر التحذير موجود وفي نهاية كل تقرير."""
        result = hook_panel.score_hooks(
            [WEAK_HOOK, STRONG_HOOK, GOOD_HOOK])
        text = hook_panel.format_panel(result)
        self.assertIn(WARNING, text)
        self.assertTrue(text.rstrip("\n").endswith(WARNING))
        self.assertIn("تقييم إرشادي (heuristic) وليس تنبؤًا "
                      "بالمشاهدات", text)

    def test_panel_shows_breakdown_and_top_two(self):
        result = hook_panel.score_hooks([STRONG_HOOK, WEAK_HOOK])
        text = hook_panel.format_panel(result)
        self.assertIn("8/9", text)
        self.assertIn("1/9", text)
        self.assertIn("فجوة فضول (0–3): 3", text)
        self.assertIn("حقيقة محددة (0–2): 1", text)
        self.assertIn("صراع/رأي قوي (0–2): 2", text)
        self.assertIn("عائد داخل المقطع (0–1): غير مقاس", text)
        self.assertIn("من أفضل اثنين", text)
        # «من أفضل اثنين» تظهر مرتين فقط (للهوكين الأولين).
        self.assertEqual(text.count("من أفضل اثنين"), 2)

    def test_single_panel_dict_accepted(self):
        result = hook_panel.score_hooks([GOOD_HOOK])
        text = hook_panel.format_panel(result[0])
        self.assertIn("6/9", text)
        self.assertTrue(text.rstrip("\n").endswith(WARNING))

    def test_deterministic(self):
        hooks = [WEAK_HOOK, STRONG_HOOK, GOOD_HOOK, AISHA_HOOK]
        first = hook_panel.format_panel(hook_panel.score_hooks(hooks))
        second = hook_panel.format_panel(hook_panel.score_hooks(hooks))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
