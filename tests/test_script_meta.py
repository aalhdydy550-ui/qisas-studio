#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات بيانات نشر فيسبوك المولّدة بالـLLM (lib.script_meta).

تعمل بـ `python3 -m unittest discover -s tests -v`.
بلا شبكة: `chat_fn` وهمية أو ترفع استثناءً.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_check
from lib import script_meta

STORY_LINE = caption_check.APPROVED_STORY_LINE


def _assert_no_banned_sentence(test, description):
    for sentence in caption_check.split_sentences(description):
        test.assertIsNone(
            caption_check.sentence_issue(sentence),
            "جملة محظورة في الوصف: %r" % sentence)


class TestGeneratePublishMeta(unittest.TestCase):
    def test_llm_result_returned_as_is(self):
        """مع chat_fn وهمية ترجع وصفًا وهاشتاغات — تُرجع كما هي."""
        calls = []

        def fake_chat(prompt):
            calls.append(prompt)
            return ("قصة حقيقية عن أمانة ردّها صاحبها رغم فقره.\n"
                    "والنهاية أغرب مما تتخيل.\n" + STORY_LINE + "\n"
                    "#قصص_وعبر #قصص_واقعية #الأمانة\n")

        res = script_meta.generate_publish_meta(
            {"title": "الأمانة", "text": "نجار فقير وجد ذهبًا في باب"},
            chat_fn=fake_chat)
        self.assertEqual(len(calls), 1)
        self.assertIn("الأمانة", calls[0])
        self.assertEqual(res["source"], "omniroute")
        self.assertEqual(
            res["description"],
            "قصة حقيقية عن أمانة ردّها صاحبها رغم فقره.\n"
            "والنهاية أغرب مما تتخيل.\n" + STORY_LINE)
        self.assertEqual(res["hashtags"],
                         ["#قصص_وعبر", "#قصص_واقعية", "#الأمانة"])
        _assert_no_banned_sentence(self, res["description"])

    def test_llm_failure_uses_local_fallback(self):
        """مع chat_fn ترفع استثناءً — البديل المحلي يعمل."""
        def boom(prompt):
            raise RuntimeError("بلا شبكة")

        res = script_meta.generate_publish_meta(
            "عائشة الأرملة", chat_fn=boom)
        self.assertEqual(res["source"], "local")
        self.assertIn("عائشة الأرملة", res["description"])
        self.assertTrue(res["description"].endswith(STORY_LINE))
        for tag in script_meta.FIXED_HASHTAGS:
            self.assertIn(tag, res["hashtags"])
        self.assertIn("#عائشة_الأرملة", res["hashtags"])
        _assert_no_banned_sentence(self, res["description"])

    def test_empty_llm_text_uses_local_fallback(self):
        """نص فارغ من النموذج — البديل المحلي يعمل."""
        res = script_meta.generate_publish_meta(
            "النجار الأمين", chat_fn=lambda prompt: "   \n")
        self.assertEqual(res["source"], "local")
        for tag in script_meta.FIXED_HASHTAGS:
            self.assertIn(tag, res["hashtags"])
        _assert_no_banned_sentence(self, res["description"])

    def test_no_chat_fn_uses_local_fallback(self):
        res = script_meta.generate_publish_meta("قصة جديدة")
        self.assertEqual(res["source"], "local")
        self.assertIn("#قصص_وعبر", res["hashtags"])

    def test_llm_gated_sentence_removed(self):
        """جملة بوابة متابعة من النموذج تُحذف ويبقى الوصف السليم."""
        def fake_chat(prompt):
            return ("لو عايز الجزء الثاني اعمل متابعة.\n"
                    "قصة حقيقية عن أمانة ردّها صاحبها.\n"
                    "#قصص_وعبر\n")

        res = script_meta.generate_publish_meta(
            "الأمانة", chat_fn=fake_chat)
        self.assertEqual(res["source"], "omniroute")
        self.assertNotIn("لو عايز الجزء الثاني", res["description"])
        self.assertIn("قصة حقيقية عن أمانة ردّها صاحبها",
                      res["description"])
        _assert_no_banned_sentence(self, res["description"])

    def test_llm_description_without_hashtags_gets_fixed_ones(self):
        """وصف بلا هاشتاغات من النموذج — الحزمة الثابتة تُستخدم."""
        res = script_meta.generate_publish_meta(
            "الأمانة",
            chat_fn=lambda prompt: "قصة حقيقية عن أمانة.\n")
        self.assertEqual(res["hashtags"], script_meta.FIXED_HASHTAGS)
        _assert_no_banned_sentence(self, res["description"])


if __name__ == "__main__":
    unittest.main()
