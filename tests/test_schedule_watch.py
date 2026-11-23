#!/usr/bin/env python3
"""اختبارات مراقبة المنشور المجدول — كلها على دوال وهمية.

ممنوع تمامًا لمس المنشورات المجدولة الحقيقية أو نشر تعليق
حقيقي: read_fn وcomment_fn هنا عدّادات محلية فقط.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_check
from lib import schedule_watch


STORY = {"moral": "الظلم مهما طال ليله، الحق بيظهر.",
         "question": "لو كنت مكانه، كنت عملت إيه؟",
         "next_part_time": "بكرة 7 مساءً"}
POST_ID = "122132235897269645"


def _fakes(state="published", fail_times=0):
    """دالتان وهميتان بعدّادات استدعاء.

    read_fn ترجع الحالة المطلوبة؛ وcomment_fn تفشل
    fail_times مرات ثم تنجح بقاموس إيصال.
    """
    calls = {"read": 0, "comment": 0, "texts": []}
    failures_left = [fail_times]

    def read_fn(post_id):
        calls["read"] += 1
        calls["read_post_id"] = post_id
        return state

    def comment_fn(post_id, text):
        calls["comment"] += 1
        calls["texts"].append(text)
        if failures_left[0] > 0:
            failures_left[0] -= 1
            raise RuntimeError("رفض فيسبوك التعليق (وهمي)")
        return {"comment_id": "2056409585228722",
                "comment_url": "https://www.facebook.com/xxx"}

    return read_fn, comment_fn, calls


class TestDryRun(unittest.TestCase):
    def test_dry_run_calls_nothing_and_returns_plan(self):
        read_fn, comment_fn, calls = _fakes()
        plan = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                         comment_fn)
        self.assertEqual(calls["read"], 0)
        self.assertEqual(calls["comment"], 0)
        self.assertEqual(plan["post_id"], POST_ID)
        self.assertEqual(plan["slot"], "morning")
        self.assertTrue(plan["would_check"])
        self.assertTrue(plan["dry_run"])
        self.assertIn(STORY["moral"], plan["would_post"])
        self.assertIn(STORY["question"], plan["would_post"])
        self.assertIn("بكرة 7 مساءً", plan["would_post"])

    def test_dry_run_evening_slot(self):
        read_fn, comment_fn, calls = _fakes()
        plan = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                         comment_fn, slot="evening")
        self.assertEqual(plan["slot"], "evening")
        self.assertEqual(calls["read"], 0)
        self.assertEqual(calls["comment"], 0)


class TestExecute(unittest.TestCase):
    def test_execute_published_comments_once_with_exact_text(self):
        read_fn, comment_fn, calls = _fakes(state="published")
        expected = schedule_watch.build_first_comment(STORY)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["read"], 1)
        self.assertEqual(calls["comment"], 1)
        self.assertEqual(calls["texts"][0], expected)
        self.assertEqual(calls["read_post_id"], POST_ID)
        self.assertEqual(res["comment_id"], "2056409585228722")

    def test_execute_published_dict_state(self):
        def read_fn(post_id):
            return {"state": "published", "post_id": post_id}
        _, comment_fn, calls = _fakes()
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["comment"], 1)

    def test_execute_scheduled_posts_no_comment(self):
        read_fn, comment_fn, calls = _fakes(state="scheduled")
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "not_published")
        self.assertIn("لم يُنشر بعد", res["message"])
        self.assertEqual(calls["read"], 1)
        self.assertEqual(calls["comment"], 0)

    def test_execute_unknown_state_posts_no_comment(self):
        read_fn, comment_fn, calls = _fakes(state=None)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "not_published")
        self.assertEqual(res["state"], "غير معروفة")
        self.assertEqual(calls["comment"], 0)

    def test_execute_comment_fails_once_then_succeeds(self):
        read_fn, comment_fn, calls = _fakes(state="published",
                                            fail_times=1)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["comment"], 2)
        self.assertEqual(res["attempts"], 2)

    def test_execute_comment_fails_twice_retries_only_once(self):
        read_fn, comment_fn, calls = _fakes(state="published",
                                            fail_times=2)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(calls["comment"], 2)
        self.assertIn("فشل نشر أول تعليق", res["error"])
        self.assertIn("محاولتين", res["error"])

    def test_execute_comment_fails_many_times_still_two_attempts(self):
        read_fn, comment_fn, calls = _fakes(state="published",
                                            fail_times=10)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(calls["comment"], 2)

    def test_execute_read_failure_returns_arabic_error(self):
        def read_fn(post_id):
            raise RuntimeError("انقطع الاتصال (وهمي)")
        _, comment_fn, calls = _fakes()
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertIn("تعذّرت قراءة حالة المنشور", res["error"])
        self.assertEqual(calls["comment"], 0)


class TestBuildFirstComment(unittest.TestCase):
    def test_contains_moral_question_and_next_part_time(self):
        text = schedule_watch.build_first_comment(STORY)
        self.assertIn("«الظلم مهما طال ليله، الحق بيظهر.»", text)
        self.assertIn("لو كنت مكانه، كنت عملت إيه؟", text)
        self.assertIn("بكرة 7 مساءً", text)
        self.assertIn("اعمل متابعة عشان يوصلك أول ما ينزل", text)

    def test_every_sentence_passes_caption_check(self):
        text = schedule_watch.build_first_comment(STORY)
        for sentence in caption_check.split_sentences(text):
            self.assertIsNone(caption_check.sentence_issue(sentence),
                              "جملة مرفوضة: %s" % sentence)

    def test_default_next_part_time_when_missing(self):
        story = {"moral": STORY["moral"],
                 "question": STORY["question"]}
        text = schedule_watch.build_first_comment(story)
        self.assertIn(caption_check.DEFAULT_NEXT_PART_TIME, text)
        for sentence in caption_check.split_sentences(text):
            self.assertIsNone(caption_check.sentence_issue(sentence))

    def test_missing_moral_raises_value_error(self):
        with self.assertRaises(ValueError):
            schedule_watch.build_first_comment(
                {"question": STORY["question"]})

    def test_missing_question_raises_value_error(self):
        with self.assertRaises(ValueError):
            schedule_watch.build_first_comment(
                {"moral": STORY["moral"]})

    def test_uses_approved_invite_not_a_rewording(self):
        text = schedule_watch.build_first_comment(STORY)
        self.assertIn(
            caption_check.approved_invite("بكرة 7 مساءً"), text)


class TestValidation(unittest.TestCase):
    def test_missing_post_id_raises(self):
        read_fn, comment_fn, _ = _fakes()
        with self.assertRaises(ValueError):
            schedule_watch.watch_slot("", STORY, read_fn, comment_fn)

    def test_bad_slot_raises(self):
        read_fn, comment_fn, _ = _fakes()
        with self.assertRaises(ValueError):
            schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                      comment_fn, slot="noon")


class TestWatchResultToPublishStatus(unittest.TestCase):
    """ترجمة نتيجة watch_slot إلى حالة نشر موحّدة (أ2-8)."""

    def test_published_ok_maps_to_published(self):
        self.assertEqual(
            schedule_watch.status_from_watch({"ok": True}),
            "published")

    def test_not_published_maps_to_pending(self):
        self.assertEqual(
            schedule_watch.status_from_watch(
                {"ok": False, "reason": "not_published"}),
            "pending")

    def test_error_maps_to_failed(self):
        self.assertEqual(
            schedule_watch.status_from_watch(
                {"ok": False, "error": "فشل نشر أول تعليق"}),
            "failed")

    def test_dry_run_and_empty_map_to_pending(self):
        self.assertEqual(schedule_watch.status_from_watch(
            {"dry_run": True}), "pending")
        self.assertEqual(schedule_watch.status_from_watch({}),
                         "pending")
        self.assertEqual(schedule_watch.status_from_watch(None),
                         "pending")

    def test_apply_watch_result_updates_facebook_by_default(self):
        statuses = {}
        entry = schedule_watch.apply_watch_result(
            statuses, 3, {"ok": True})
        self.assertEqual(entry["facebook"], "published")
        self.assertEqual(entry["youtube"], "pending")
        entry = schedule_watch.apply_watch_result(
            statuses, 3, {"ok": False, "error": "فشل"})
        self.assertEqual(entry["facebook"], "failed")

    def test_apply_watch_result_not_published_keeps_pending(self):
        entry = schedule_watch.apply_watch_result(
            {}, 5, {"ok": False, "reason": "not_published"})
        self.assertEqual(entry["facebook"], "pending")


if __name__ == "__main__":
    unittest.main()
