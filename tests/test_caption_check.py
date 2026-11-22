#!/usr/bin/env python3
"""اختبارات فحص امتثال الكابشن — بلا نشر وبلا شبكة."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_check


GENTLE = ("الجزء الثاني بكرة 7 مساءً — اعمل متابعة عشان يوصلك "
          "أول ما ينزل")
STORY_LINE = caption_check.APPROVED_STORY_LINE
GATE = ("لو عايز الجزء الثاني اعمل متابعة واكتب في التعليقات: "
        "الجزء الثاني")


class TestBannedSentences(unittest.TestCase):
    def test_abolished_follow_gate_rejected(self):
        res = caption_check.check_caption("عنوان القصة\n" + GATE)
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["issues"]), 1)
        self.assertIn("المتابعة أو التعليق", res["issues"][0]["reason"])
        self.assertIsNotNone(res["fixed"])
        self.assertIn("بكرة 7 مساء", res["fixed"])
        self.assertIn("اعمل متابعة عشان يوصلك أول ما ينزل",
                      res["fixed"])

    def test_single_line_gate_is_the_hook_needs_rewrite(self):
        # الكابشن كله بوابة = الهوك نفسه محظور — لا إصلاح جزئي.
        res = caption_check.check_caption(GATE)
        self.assertFalse(res["ok"])
        self.assertTrue(res["issues"][0]["in_hook"])
        self.assertIsNone(res["fixed"])

    def test_follow_for_part_without_time_rejected(self):
        res = caption_check.check_caption(
            "اعمل متابعة عشان يوصلك الجزء الثاني")
        self.assertFalse(res["ok"])

    def test_comment_for_part_rejected(self):
        res = caption_check.check_caption(
            "اكتب في التعليقات: الجزء الثاني")
        self.assertFalse(res["ok"])

    def test_withholding_part_rejected(self):
        res = caption_check.check_caption(
            "الجزء الثاني مش هينزل إلا لو عملت متابعة")
        self.assertFalse(res["ok"])

    def test_engagement_for_part_rejected(self):
        res = caption_check.check_caption(
            "شارك المنشور عشان يوصلك الجزء الثاني")
        self.assertFalse(res["ok"])

    def test_follow_for_reward_rejected(self):
        res = caption_check.check_caption("اعمل متابعة عشان تكسب")
        self.assertFalse(res["ok"])

    def test_story_request_in_comments_rejected_and_fixed(self):
        res = caption_check.check_caption(
            "عنوان القصة\nابعت قصتك في التعليقات عشان نحكيها")
        self.assertFalse(res["ok"])
        self.assertEqual(res["issues"][0]["category"], "story")
        self.assertIn("رسائل الصفحة", res["fixed"])

    def test_gate_in_hook_needs_full_rewrite(self):
        res = caption_check.check_caption(GATE + "\nباقي الكابشن هنا.")
        self.assertFalse(res["ok"])
        self.assertTrue(res["issues"][0]["in_hook"])
        self.assertIsNone(res["fixed"])


class TestAllowedSentences(unittest.TestCase):
    def test_gentle_time_based_invite_allowed(self):
        res = caption_check.check_caption(GENTLE)
        self.assertTrue(res["ok"])
        self.assertEqual(res["issues"], [])

    def test_story_line_allowed(self):
        res = caption_check.check_caption(STORY_LINE)
        self.assertTrue(res["ok"])

    def test_opinion_comment_allowed(self):
        res = caption_check.check_caption("اكتب رأيك في التعليقات")
        self.assertTrue(res["ok"])

    def test_plain_follow_for_news_allowed(self):
        res = caption_check.check_caption(
            "تابعنا عشان يوصلك كل جديد")
        self.assertTrue(res["ok"])

    def test_full_built_caption_allowed(self):
        caption = "\n".join([
            "عائشة الأرملة — الجزء 2",
            "الكاتب باع ضميره… بس الرسالة وصلت لصاحبتها!",
            GENTLE,
            STORY_LINE,
            "#قصص_وعبر #قصص_واقعية #قصص_مؤثرة #حكايات",
        ])
        res = caption_check.check_caption(caption)
        self.assertTrue(res["ok"])

    def test_empty_caption_ok(self):
        self.assertTrue(caption_check.check_caption("")["ok"])
        self.assertTrue(caption_check.check_caption("   ")["ok"])


class TestFixCaption(unittest.TestCase):
    def test_gate_mid_caption_replaced(self):
        caption = "عنوان القصة\n" + GATE + "\n" + STORY_LINE
        fixed = caption_check.fix_caption(caption)
        self.assertIsNotNone(fixed)
        self.assertNotIn("لو عايز", fixed)
        self.assertIn("بكرة 7 مساء", fixed)
        self.assertIn("عنوان القصة", fixed)
        # الكابشن المصحح نفسه سليم
        self.assertTrue(caption_check.check_caption(fixed)["ok"])

    def test_custom_next_part_time_used(self):
        fixed = caption_check.fix_caption(
            "نص عادي\nاعمل متابعة عشان يوصلك الجزء الثاني",
            next_part_time="الجمعة 8 مساءً")
        self.assertIn("الجمعة 8 مساءً", fixed)


if __name__ == "__main__":
    unittest.main()
