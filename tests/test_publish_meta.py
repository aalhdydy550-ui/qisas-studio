#!/usr/bin/env python3
"""اختبارات عنوان/وسوم/وصف النشر المولّدة (lib.publish_meta).

تعمل بـ `python3 -m unittest discover -s tests -v`.
بلا شبكة إطلاقًا: `chat_fn` وهمية أو ترفع استثناءً.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_check
from lib import publish_meta

STORY_LINE = caption_check.APPROVED_STORY_LINE


def _assert_no_banned_sentence(test, description):
    for sentence in caption_check.split_sentences(description):
        test.assertIsNone(
            caption_check.sentence_issue(sentence),
            "جملة محظورة في الوصف: %r" % sentence)


class TestLocalFallback(unittest.TestCase):
    def test_single_part_title(self):
        res = publish_meta.generate_publish_meta("عائشة الأرملة")
        self.assertEqual(res["source"], "local")
        self.assertEqual(res["title"], "عائشة الأرملة | قصة حقيقية")
        self.assertTrue(res["description"].startswith("قصة حقيقية"))
        self.assertIn(STORY_LINE, res["description"])
        self.assertEqual(res["tags"][:4], publish_meta.FIXED_TAGS)
        for tag in publish_meta.FIXED_HASHTAGS:
            self.assertIn(tag, res["hashtags"])
        self.assertIn("#عائشة_الأرملة", res["hashtags"])
        _assert_no_banned_sentence(self, res["description"])

    def test_multi_part_title(self):
        res = publish_meta.generate_publish_meta(
            {"title": "عائشة الأرملة", "text": "أرملة ظلمتها حماتها"},
            part=1, parts=2)
        self.assertEqual(res["title"],
                         "عائشة الأرملة | الجزء 1 من 2")
        res2 = publish_meta.generate_publish_meta(
            {"title": "عائشة الأرملة", "part": 2, "parts": 2})
        self.assertEqual(res2["title"],
                         "عائشة الأرملة | الجزء 2 من 2")

    def test_hook_used_in_description(self):
        res = publish_meta.generate_publish_meta(
            {"title": "الأمانة", "text": "نجار وجد ذهبًا",
             "hook": "لقى محفظة ورفض يسرقها رغم فقره"})
        self.assertIn("لقى محفظة ورفض يسرقها رغم فقره",
                      res["description"])

    def test_long_title_trimmed_to_100(self):
        title = "قصة " + "طويلة جدًا " * 20
        res = publish_meta.generate_publish_meta(title)
        self.assertLessEqual(len(res["title"]), 100)
        self.assertIn("قصة حقيقية", res["title"])

    def test_invalid_parts_rejected(self):
        with self.assertRaises(ValueError):
            publish_meta.generate_publish_meta("عنوان", part=3, parts=2)
        with self.assertRaises(ValueError):
            publish_meta.generate_publish_meta("عنوان", parts=0)

    def test_format_for_publish(self):
        res = publish_meta.generate_publish_meta("عائشة الأرملة")
        args = publish_meta.format_for_publish(res)
        self.assertEqual(args["title"], res["title"])
        self.assertEqual(args["caption"], res["description"])
        self.assertEqual(args["tags"], ",".join(res["tags"]))
        self.assertLessEqual(len(",".join(res["tags"])), 500)


class TestLlmPath(unittest.TestCase):
    def test_llm_result_parsed(self):
        calls = []

        def fake_chat(prompt):
            calls.append(prompt)
            return ("النجار الأمين | قصة حقيقية\n"
                    "قصة حقيقية عن أمانة ردّها صاحبها رغم فقره.\n"
                    "#قصص_وعبر #الأمانة\n")

        res = publish_meta.generate_publish_meta(
            {"title": "الأمانة", "text": "نجار فقير وجد ذهبًا في باب"},
            chat_fn=fake_chat)
        self.assertEqual(len(calls), 1)
        self.assertIn("الأمانة", calls[0])
        self.assertEqual(res["source"], "llm")
        self.assertEqual(res["title"], "النجار الأمين | قصة حقيقية")
        self.assertIn("أمانة ردّها صاحبها", res["description"])
        self.assertIn("قصص وعبر", res["tags"])
        self.assertIn("الأمانة", res["tags"])
        self.assertIn("#الأمانة", res["hashtags"])
        _assert_no_banned_sentence(self, res["description"])

    def test_llm_failure_uses_local(self):
        def boom(prompt):
            raise RuntimeError("بلا شبكة")

        res = publish_meta.generate_publish_meta(
            "عائشة الأرملة", chat_fn=boom)
        self.assertEqual(res["source"], "local")
        self.assertEqual(res["title"], "عائشة الأرملة | قصة حقيقية")

    def test_empty_llm_text_uses_local(self):
        res = publish_meta.generate_publish_meta(
            "النجار الأمين", chat_fn=lambda prompt: "   \n")
        self.assertEqual(res["source"], "local")

    def test_llm_long_title_rejected_to_local(self):
        long_title = "عنوان " + "طويل " * 40
        res = publish_meta.generate_publish_meta(
            "الأمانة", chat_fn=lambda prompt: long_title + "\nوصف.\n")
        self.assertEqual(res["source"], "local")

    def test_llm_gated_sentence_removed(self):
        def fake_chat(prompt):
            return ("الأمانة | قصة حقيقية\n"
                    "لو عايز الجزء الثاني اعمل متابعة.\n"
                    "قصة حقيقية عن أمانة ردّها صاحبها.\n"
                    "#قصص_وعبر\n")

        res = publish_meta.generate_publish_meta(
            "الأمانة", chat_fn=fake_chat)
        self.assertEqual(res["source"], "llm")
        self.assertNotIn("لو عايز الجزء الثاني", res["description"])
        self.assertIn("قصة حقيقية عن أمانة ردّها صاحبها",
                      res["description"])
        _assert_no_banned_sentence(self, res["description"])

    def test_llm_only_gated_description_falls_back(self):
        def fake_chat(prompt):
            return ("الأمانة | قصة حقيقية\n"
                    "لو عايز الجزء الثاني اعمل متابعة.\n")

        res = publish_meta.generate_publish_meta(
            "الأمانة", chat_fn=fake_chat)
        self.assertEqual(res["source"], "local")

    def test_llm_no_tags_gets_fixed_tags(self):
        res = publish_meta.generate_publish_meta(
            "الأمانة",
            chat_fn=lambda prompt: ("الأمانة | قصة حقيقية\n"
                                    "قصة حقيقية عن أمانة.\n"))
        self.assertEqual(res["source"], "llm")
        self.assertEqual(res["tags"], publish_meta.FIXED_TAGS)
        self.assertEqual(res["hashtags"],
                         publish_meta.FIXED_HASHTAGS)


if __name__ == "__main__":
    unittest.main()
