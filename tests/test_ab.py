#!/usr/bin/env python3
"""اختبارات اختبار A/B (lib.ab).

تعمل بـ `python3 -m unittest discover -s tests -v`.
توليد المصغرات بدوال مزيفة (بلا ffmpeg)؛ والمقارنة بقوائم
منشورات مزيفة (بلا فيسبوك/يوتيوب حقيقيين).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ab


def _fake_thumbnail(calls):
    def fn(video, hook, out, at_seconds=None):
        calls.append((hook, at_seconds))
        with open(out, "wb") as f:
            f.write(b"fake-thumb")
        return out, at_seconds, [hook]
    return fn


class TestSuggestHooks(unittest.TestCase):
    def test_local_fallback_offline(self):
        a, b, src = ab.suggest_hooks("قصة جديدة", chat_fn=None)
        self.assertEqual(a, "قصة جديدة")
        self.assertIn("قصة جديدة", b)
        self.assertNotEqual(a, b)
        self.assertEqual(src, "local")

    def test_llm_hooks_used_when_available(self):
        def fake_chat(prompt):
            return "هوك أول صادم!\nهوك ثانٍ مختلف!\n"
        a, b, src = ab.suggest_hooks("قصة", chat_fn=fake_chat)
        self.assertEqual((a, b), ("هوك أول صادم!", "هوك ثانٍ مختلف!"))
        self.assertEqual(src, "omniroute")

    def test_llm_failure_falls_back(self):
        def boom(prompt):
            raise RuntimeError("بلا شبكة")
        _a, _b, src = ab.suggest_hooks("قصة", chat_fn=boom)
        self.assertEqual(src, "local")

    def test_llm_ass_tag_hooks_fall_back(self):
        # اختبار انحدار (اختراق 2026-11-22): هوكان من النموذج
        # يحويان وسوم ASS يُرفضان فيُستخدم البديل المحلي.
        def fake_chat(prompt):
            return "هوك {\\fs200}خدعة\nهوك ثانٍ {\\pos(1,1)}\n"
        _a, _b, src = ab.suggest_hooks("قصة", chat_fn=fake_chat)
        self.assertEqual(src, "local")


class TestCreateAb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "video.mp4")
        with open(self.video, "wb") as f:
            f.write(b"fake-video")

    def test_creates_two_thumbnails_and_record(self):
        calls = []
        record = ab.create_ab(
            self.video, "هوك أ!", "هوك ب!", self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail(calls),
            duration_fn=lambda v: 50.0)
        self.assertEqual(record["hook_a"], "هوك أ!")
        self.assertEqual(record["hook_b"], "هوك ب!")
        self.assertEqual(record["duration"], 50.0)
        self.assertTrue(os.path.isfile(record["thumb_a"]))
        self.assertTrue(os.path.isfile(record["thumb_b"]))
        self.assertTrue(os.path.isfile(record["record_path"]))
        # أ عند 35% والثانية عند 65% من المدة
        self.assertEqual(calls[0][1], 17.5)
        self.assertEqual(calls[1][1], 32.5)
        with open(record["record_path"], encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["hook_a"], "هوك أ!")

    def test_llm_model_recorded_when_given(self):
        record = ab.create_ab(
            self.video, "هوك أ!", "هوك ب!", self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0,
            llm_model="gemini-3-flash-preview")
        self.assertEqual(record["llm_model"],
                         "gemini-3-flash-preview")
        with open(record["record_path"], encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["llm_model"],
                         "gemini-3-flash-preview")

    def test_llm_model_defaults_to_none(self):
        record = ab.create_ab(
            self.video, "هوك أ!", "هوك ب!", self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0)
        self.assertIsNone(record["llm_model"])

    def test_identical_hooks_rejected(self):
        with self.assertRaises(ValueError):
            ab.create_ab(self.video, "نفس الهوك", "نفس الهوك",
                         self.tmp,
                         thumbnail_fn=_fake_thumbnail([]),
                         duration_fn=lambda v: 50.0)

    def test_missing_video_rejected(self):
        with self.assertRaises(ValueError):
            ab.create_ab(os.path.join(self.tmp, "nope.mp4"),
                         "أ", "ب", self.tmp,
                         thumbnail_fn=_fake_thumbnail([]),
                         duration_fn=lambda v: 50.0)

    def test_ass_tag_hooks_rejected(self):
        # اختبار انحدار (اختراق 2026-11-22): هوك يحوي وسوم ASS
        # كان يمرّ إلى السجل وعنوان النشر حرفيًا.
        with self.assertRaises(ValueError):
            ab.create_ab(self.video, "هوك {\\fs200}خدعة", "هوك ب!",
                         self.tmp,
                         thumbnail_fn=_fake_thumbnail([]),
                         duration_fn=lambda v: 50.0)
        with self.assertRaises(ValueError):
            ab.create_ab(self.video, "هوك أ!", "هوك \\ شرطة",
                         self.tmp,
                         thumbnail_fn=_fake_thumbnail([]),
                         duration_fn=lambda v: 50.0)


class TestCompare(unittest.TestCase):
    def setUp(self):
        self.record = {
            "record_path": "/tmp/ab.json",
            "video": "/tmp/video.mp4",
            "hook_a": "هوك أ الصادم",
            "hook_b": "هوك ب المختلف",
        }

    def test_winner_by_total_views(self):
        fb = [
            {"caption": "هوك أ الصادم — قصة", "views": 100},
            {"caption": "هوك ب المختلف — قصة", "views": 40},
        ]
        yt = [
            {"title": "هوك أ الصادم", "views": 30},
            {"title": "هوك ب المختلف", "views": 90},
        ]
        out = ab.compare_ab(self.record, fb, yt)
        self.assertEqual(out["variants"]["a"]["total_views"], 130)
        self.assertEqual(out["variants"]["b"]["total_views"], 130)
        self.assertEqual(out["winner"], "tie")
        self.assertTrue(out["decisive"])

    def test_clear_winner(self):
        fb = [{"caption": "هوك أ الصادم", "views": 500}]
        yt = [{"title": "هوك ب المختلف", "views": 10}]
        out = ab.compare_ab(self.record, fb, yt)
        self.assertEqual(out["winner"], "a")

    def test_unpublished_variant_indecisive(self):
        fb = [{"caption": "هوك أ الصادم", "views": 100}]
        out = ab.compare_ab(self.record, fb, [])
        self.assertFalse(out["variants"]["b"]["published"])
        self.assertIsNone(out["winner"])
        self.assertFalse(out["decisive"])

    def test_format_marks_unpublished(self):
        out = ab.compare_ab(self.record, [], [])
        text = ab.format_comparison(self.record, out)
        self.assertIn("غير منشورة بعد", text)
        self.assertIn("غير حاسمة", text)
        self.assertIn("بلا اختبار A/B أصلي", text)


if __name__ == "__main__":
    unittest.main()
