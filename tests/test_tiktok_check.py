#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات قوائم فحص TikTok قبل النشر (lib.tiktok_check).

تعمل بـ `python3 -m unittest tests.test_tiktok_check -v`
من `~/workspace/studio`. بلا شبكة وبلا LLM إطلاقًا.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import tiktok_check

GOOD_TITLE = "النجار الأمين | قصة حقيقية"
GOOD_HOOK = "ظلم أخاه وسرق ميراثه — فماذا فعل الله به؟"
GOOD_STORY = ("نجار فقير وجد ذهبًا في باب وأعاده لصاحبه. "
              "جملة ثانية في القصة. جملة ثالثة في القصة. "
              "العبرة: الظلم لا يدوم.")
GOOD_CAPTION = (GOOD_TITLE + "\n"
                "قصة حقيقية عن نجار فقير وجد ذهبًا وأعاده "
                "لصاحبه.\n"
                "العبرة: الأمانة ترفع صاحبها.\n"
                "#قصص #قصص_حقيقية #قصص_واقعية #قصة_وعبرة")


def _queue_text(count):
    """نص طابور فيه count عنصرًا في الانتظار."""
    lines = ["# طابور قصص — تجريبي للاختبار فقط", "",
             "## في الانتظار", ""]
    for i in range(1, count + 1):
        lines.append("%d. **قصة %d** — بلا ملاحظات" % (i, i))
    lines += ["", "## المنشور", "",
              "1. **قصة منشورة** — نُشرت"]
    return "\n".join(lines)


def _good(**overrides):
    kwargs = {"title": GOOD_TITLE, "caption": GOOD_CAPTION,
              "hook": GOOD_HOOK, "story_text": GOOD_STORY,
              "queue_text": _queue_text(7), "needed": 7,
              "trend_keywords": ["ميراث", "ظلم"]}
    kwargs.update(overrides)
    return tiktok_check.check_tiktok(**kwargs)


class TestHook(unittest.TestCase):
    def test_good_hook_scores_and_passes(self):
        report = tiktok_check.check_hook(GOOD_HOOK,
                                         story_text=GOOD_STORY)
        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "pass")
        self.assertGreaterEqual(report["score"], 6)
        self.assertEqual(report["word_count"], 9)
        self.assertFalse(report["has_warmup"])

    def test_empty_hook_fails_without_score(self):
        report = tiktok_check.check_hook("")
        self.assertFalse(report["ok"])
        self.assertIsNone(report["score"])
        self.assertEqual(report["verdict"], "غير مقاس")

    def test_long_hook_fails_word_limit(self):
        hook = ("قصة " * 13).strip()
        report = tiktok_check.check_hook(hook)
        self.assertGreater(report["word_count"], 12)
        self.assertFalse(report["ok"])

    def test_warmup_hook_flagged(self):
        hook = "يا جماعة تعالوا اسمعوا قصة النجار الأمين"
        report = tiktok_check.check_hook(hook)
        self.assertTrue(report["has_warmup"])
        self.assertFalse(report["ok"])

    def test_hook_is_advisory_not_prediction(self):
        report = _good()
        self.assertIn(tiktok_check.HOOK_ADVISORY, report["notes"])


class TestCaption(unittest.TestCase):
    def test_good_caption_passes(self):
        report = tiktok_check.check_caption(GOOD_TITLE, GOOD_CAPTION)
        self.assertTrue(report["ok"])
        self.assertEqual(report["hashtags_missing"], [])
        self.assertTrue(report["moral_present"])
        self.assertFalse(report["has_youtube_link"])
        self.assertTrue(report["gate_ok"])
        self.assertTrue(report["title_present"])
        self.assertTrue(report["length_ok"])

    def test_missing_hashtag_fails(self):
        caption = GOOD_CAPTION.replace("#قصة_وعبرة", "")
        report = tiktok_check.check_caption(GOOD_TITLE, caption)
        self.assertFalse(report["ok"])
        self.assertIn("#قصة_وعبرة", report["hashtags_missing"])

    def test_missing_moral_fails(self):
        caption = GOOD_CAPTION.replace("العبرة: الأمانة ترفع "
                                       "صاحبها.\n", "")
        report = tiktok_check.check_caption(GOOD_TITLE, caption)
        self.assertFalse(report["ok"])
        self.assertFalse(report["moral_present"])

    def test_moral_as_separate_input_passes(self):
        caption = GOOD_CAPTION.replace("العبرة: الأمانة ترفع "
                                       "صاحبها.\n", "")
        report = tiktok_check.check_caption(GOOD_TITLE, caption,
                                            moral="الأمانة ترفع "
                                            "صاحبها")
        self.assertTrue(report["moral_present"])

    def test_youtube_link_fails(self):
        caption = GOOD_CAPTION + "\nhttps://youtube.com/shorts/xyz"
        report = tiktok_check.check_caption(GOOD_TITLE, caption)
        self.assertFalse(report["ok"])
        self.assertTrue(report["has_youtube_link"])

    def test_follow_gate_fails(self):
        caption = (GOOD_CAPTION + "\nلو عايز الجزء الثاني اعمل "
                   "متابعة")
        report = tiktok_check.check_caption(GOOD_TITLE, caption)
        self.assertFalse(report["ok"])
        self.assertFalse(report["gate_ok"])
        self.assertTrue(report["gate_issues"])

    def test_over_length_fails(self):
        caption = GOOD_CAPTION + "\n" + ("نص طويل. " * 300)
        report = tiktok_check.check_caption(GOOD_TITLE, caption)
        self.assertGreater(report["length"], 2200)
        self.assertFalse(report["length_ok"])
        self.assertFalse(report["ok"])

    def test_title_absent_fails(self):
        caption = GOOD_CAPTION.replace(GOOD_TITLE, "")
        report = tiktok_check.check_caption(GOOD_TITLE, caption)
        self.assertFalse(report["ok"])
        self.assertFalse(report["title_present"])


class TestTrend(unittest.TestCase):
    def test_no_keywords_unmeasured_not_blocking(self):
        report = tiktok_check.check_trend(GOOD_TITLE, GOOD_HOOK,
                                          GOOD_CAPTION)
        self.assertEqual(report["status"], "unmeasured")
        self.assertTrue(report["ok"])
        self.assertEqual(report["matched"], [])

    def test_matched_keyword_passes(self):
        report = tiktok_check.check_trend(GOOD_TITLE, GOOD_HOOK,
                                          GOOD_CAPTION,
                                          ["ميراث"])
        self.assertTrue(report["ok"])
        self.assertEqual(report["matched"], ["ميراث"])

    def test_unmatched_keyword_fails(self):
        report = tiktok_check.check_trend(GOOD_TITLE, GOOD_HOOK,
                                          GOOD_CAPTION,
                                          ["كرة القدم"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["matched"], [])


class TestWeekPlan(unittest.TestCase):
    def test_seven_pending_passes_needed_seven(self):
        report = tiktok_check.check_week_plan(
            queue_text=_queue_text(7), needed=7)
        self.assertTrue(report["ok"])
        self.assertEqual(report["pending_count"], 7)

    def test_two_pending_fails_needed_seven(self):
        report = tiktok_check.check_week_plan(
            queue_text=_queue_text(2), needed=7)
        self.assertFalse(report["ok"])
        self.assertEqual(report["pending_count"], 2)

    def test_no_queue_unmeasured_not_blocking(self):
        report = tiktok_check.check_week_plan(needed=7)
        self.assertEqual(report["status"], "unmeasured")
        self.assertTrue(report["ok"])
        self.assertIsNone(report["pending_count"])

    def test_invalid_needed_raises(self):
        with self.assertRaises(ValueError):
            tiktok_check.check_week_plan(queue_text=_queue_text(7),
                                         needed=0)
        with self.assertRaises(ValueError):
            tiktok_check.check_week_plan(queue_text=_queue_text(7),
                                         needed="7")

    def test_missing_queue_path_raises(self):
        with self.assertRaises(ValueError):
            tiktok_check.check_week_plan(
                queue_path="/tmp/لا-يوجد-طابور-أبدًا.md", needed=7)

    def test_queue_path_reads_file(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".md", encoding="utf-8",
                delete=False) as f:
            f.write(_queue_text(7))
            path = f.name
        try:
            report = tiktok_check.check_week_plan(queue_path=path,
                                                  needed=7)
            self.assertTrue(report["ok"])
            self.assertEqual(report["pending_count"], 7)
        finally:
            os.unlink(path)

    def test_published_section_not_counted(self):
        report = tiktok_check.check_week_plan(
            queue_text=_queue_text(1), needed=2)
        self.assertEqual(report["pending_count"], 1)
        self.assertFalse(report["ok"])


class TestCheckTikTok(unittest.TestCase):
    def test_good_report_ok_with_four_checks(self):
        report = _good()
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["checks"]), 4)
        self.assertEqual(report["issues"], [])
        self.assertIn(tiktok_check.HOOK_ADVISORY, report["notes"])

    def test_bad_caption_makes_report_not_ok(self):
        report = _good(caption="نص بلا وسوم ولا عبرة ولا عنوان")
        self.assertFalse(report["ok"])
        self.assertTrue(report["issues"])

    def test_empty_title_raises(self):
        with self.assertRaises(ValueError):
            tiktok_check.check_tiktok("", GOOD_CAPTION)

    def test_non_string_caption_raises(self):
        with self.assertRaises(ValueError):
            tiktok_check.check_tiktok(GOOD_TITLE, None)

    def test_invalid_needed_raises(self):
        with self.assertRaises(ValueError):
            _good(needed=0)

    def test_deterministic(self):
        self.assertEqual(_good(), _good())

    def test_json_round_trip(self):
        dumped = tiktok_check.to_json_dict(_good())
        self.assertEqual(json.loads(json.dumps(
            dumped, ensure_ascii=False)), dumped)

    def test_format_report_good_mentions_ready(self):
        text = tiktok_check.format_report(_good())
        self.assertIn("جاهز للنشر", text)
        self.assertIn(tiktok_check.HOOK_ADVISORY, text)

    def test_format_report_bad_lists_issues(self):
        report = _good(caption="نص بلا وسوم ولا عبرة ولا عنوان")
        text = tiktok_check.format_report(report)
        self.assertIn("الملاحظات:", text)


class TestCmdTiktokCheck(unittest.TestCase):
    def test_cmd_good_returns_zero(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".md", encoding="utf-8",
                delete=False) as f:
            f.write(_queue_text(7))
            queue_path = f.name
        with tempfile.NamedTemporaryFile(
                "w", suffix=".txt", encoding="utf-8",
                delete=False) as f:
            f.write(GOOD_STORY)
            story_path = f.name
        try:
            code = tiktok_check.cmd_tiktok_check(
                None, GOOD_TITLE, GOOD_CAPTION, hook=GOOD_HOOK,
                story_file=story_path, queue_file=queue_path,
                needed=7, trend_keywords=["ميراث"])
        finally:
            os.unlink(queue_path)
            os.unlink(story_path)
        self.assertEqual(code, 0)

    def test_cmd_bad_returns_one(self):
        code = tiktok_check.cmd_tiktok_check(
            None, GOOD_TITLE, "نص بلا وسوم ولا عبرة ولا عنوان")
        self.assertEqual(code, 1)

    def test_cmd_invalid_title_returns_two(self):
        code = tiktok_check.cmd_tiktok_check(None, "   ",
                                             GOOD_CAPTION)
        self.assertEqual(code, 2)

    def test_cmd_missing_story_file_returns_two(self):
        code = tiktok_check.cmd_tiktok_check(
            None, GOOD_TITLE, GOOD_CAPTION,
            story_file="/tmp/لا-يوجد-ملف-قصة-أبدًا.txt")
        self.assertEqual(code, 2)

    def test_cmd_missing_queue_file_returns_two(self):
        code = tiktok_check.cmd_tiktok_check(
            None, GOOD_TITLE, GOOD_CAPTION,
            queue_file="/tmp/لا-يوجد-ملف-طابور-أبدًا.md")
        self.assertEqual(code, 2)

    def test_cmd_json_is_pure_json(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".md", encoding="utf-8",
                delete=False) as f:
            f.write(_queue_text(7))
            queue_path = f.name
        with tempfile.NamedTemporaryFile(
                "w", suffix=".txt", encoding="utf-8",
                delete=False) as f:
            f.write(GOOD_STORY)
            story_path = f.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = tiktok_check.cmd_tiktok_check(
                    None, GOOD_TITLE, GOOD_CAPTION, hook=GOOD_HOOK,
                    story_file=story_path, queue_file=queue_path,
                    needed=7, trend_keywords=["ميراث"],
                    as_json=True)
        finally:
            os.unlink(queue_path)
            os.unlink(story_path)
        self.assertEqual(code, 0)
        parsed = json.loads(buf.getvalue())
        self.assertTrue(parsed["ok"])
        self.assertEqual(len(parsed["checks"]), 4)


if __name__ == "__main__":
    unittest.main()
