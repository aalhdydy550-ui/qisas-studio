#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات نشر TikTok عبر مهمة متصفح — جولة v0.1.57.

يغطي: الباني (الوسوم الأربعة بالظبط، سطر العبرة، الدعوة
اللطيفة، الإفصاح فقط مع ai_voice، حد 2200، رفض الفارغ،
ناتج الباني يمرّ `caption_check.check_caption` بلا مشاكل،
وبلا أي جملة بوابة متابعة)، كاتب الحزمة (الملفات الثلاثة
موجودة، metadata.json صالح ويحوي الحساب والروابط، steps.txt
يحوي @qisaswaebareg وtiktok.com/upload ومسار الفيديو)،
الحالة (مضبوط/غير مضبوط)، وbrief يقرأ حزمة مكتوبة.

بلا أي شبكة — كل الشبكة محاكاة تفشل عند استدعائها، وبملفات
mp4 وهمية + probe_info محقون مثل tests/test_publish_tiktok_ig.py.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_check
from lib import social_publish as sp
from lib import tiktok_publish as tp

EXPECTED_HASHTAGS = ["#قصص", "#قصص_حقيقية", "#قصص_واقعية",
                     "#قصة_وعبرة"]


def _mp4(tmpdir, size=1024):
    path = os.path.join(tmpdir, "video.mp4")
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


def _probe(duration=45.0, width=720, height=1280, has_audio=True):
    return {"duration": duration, "width": width, "height": height,
            "has_audio": has_audio}


def _no_network():
    """سياق: أي طلب شبكة يفشل الاختبار فورًا."""
    failing = mock.Mock(side_effect=AssertionError("شبكة!"))
    return mock.patch.object(urllib.request, "urlopen", failing), \
        mock.patch.object(sp, "_http_json", failing)


class TestBuildCaption(unittest.TestCase):
    def test_exact_four_hashtags_last_line(self):
        text = tp.build_tiktok_caption("عنوان القصة", "نص القصة.")
        lines = text.splitlines()
        self.assertEqual(lines[-1], " ".join(EXPECTED_HASHTAGS))
        self.assertEqual(tp.TIKTOK_HASHTAGS, EXPECTED_HASHTAGS)
        for tag in EXPECTED_HASHTAGS:
            self.assertIn(tag, text)

    def test_line_order_title_story_moral_hashtags(self):
        text = tp.build_tiktok_caption("عنوان القصة", "نص القصة.",
                                       moral="الصبر مفتاح الفرج")
        lines = text.splitlines()
        self.assertEqual(lines[0], "عنوان القصة")
        self.assertEqual(lines[1], "نص القصة.")
        self.assertEqual(lines[2], "العبرة: الصبر مفتاح الفرج")
        self.assertEqual(lines[3], " ".join(EXPECTED_HASHTAGS))

    def test_no_moral_line_without_moral(self):
        text = tp.build_tiktok_caption("عنوان", "نص.")
        self.assertNotIn("العبرة:", text)

    def test_gentle_invite_with_next_part(self):
        text = tp.build_tiktok_caption("عنوان", "نص.", next_part=True)
        invite = caption_check.approved_invite("بكرة 7 مساءً")
        self.assertIn(invite, text)
        self.assertIn("بكرة 7 مساءً", text)

    def test_gentle_invite_custom_time(self):
        text = tp.build_tiktok_caption(
            "عنوان", "نص.", next_part=True,
            next_part_time="غدًا 8 مساءً")
        self.assertIn(
            caption_check.approved_invite("غدًا 8 مساءً"), text)

    def test_no_invite_without_next_part(self):
        text = tp.build_tiktok_caption("عنوان", "نص.")
        self.assertNotIn("الجزء الثاني", text)
        self.assertNotIn("اعمل متابعة", text)

    def test_disclosure_only_with_ai_voice(self):
        with_ai = tp.build_tiktok_caption("عنوان", "نص.",
                                          ai_voice=True)
        self.assertIn("صوت مولّد بالذكاء الاصطناعي", with_ai)
        without_ai = tp.build_tiktok_caption("عنوان", "نص.")
        self.assertNotIn("صوت مولّد بالذكاء الاصطناعي", without_ai)
        # ترتيب الإفصاح: قبل الوسوم مباشرة.
        lines = with_ai.splitlines()
        self.assertEqual(lines[-2], "صوت مولّد بالذكاء الاصطناعي")
        self.assertEqual(lines[-1], " ".join(EXPECTED_HASHTAGS))

    def test_full_order_with_all_parts(self):
        text = tp.build_tiktok_caption(
            "عنوان", "نص.", moral="عبرة", next_part=True,
            ai_voice=True)
        lines = text.splitlines()
        self.assertEqual(lines[0], "عنوان")
        self.assertEqual(lines[1], "نص.")
        self.assertEqual(lines[2], "العبرة: عبرة")
        self.assertEqual(
            lines[3],
            caption_check.approved_invite("بكرة 7 مساءً"))
        self.assertEqual(lines[4], "صوت مولّد بالذكاء الاصطناعي")
        self.assertEqual(lines[5], " ".join(EXPECTED_HASHTAGS))

    def test_empty_rejected_arabic(self):
        for title, caption in [("", ""), ("   ", ""), ("", "  "),
                               (None, None)]:
            with self.assertRaises(tp.TikTokPublishError) as cm:
                tp.build_tiktok_caption(title, caption)
            self.assertIn("فارغ", str(cm.exception))

    def test_over_2200_rejected_arabic(self):
        with self.assertRaises(tp.TikTokPublishError) as cm:
            tp.build_tiktok_caption("عنوان", "x" * 2200)
        self.assertIn("2200", str(cm.exception))

    def test_at_limit_passes(self):
        # عنوان + سطر + الوسوم = 2200 حرفًا بالظبط.
        hashtags = " ".join(EXPECTED_HASHTAGS)
        body_len = 2200 - len(hashtags) - 1
        text = tp.build_tiktok_caption("x" * body_len, "")
        self.assertEqual(len(text), 2200)

    def test_built_output_passes_caption_check(self):
        for kwargs in ({}, {"moral": "عبرة"}, {"next_part": True},
                       {"next_part": True, "ai_voice": True}):
            text = tp.build_tiktok_caption("عنوان القصة",
                                           "نص القصة.", **kwargs)
            checked = caption_check.check_caption(text)
            self.assertTrue(checked["ok"], checked["issues"])
            self.assertEqual(checked["issues"], [])

    def test_no_follow_gate_sentence(self):
        # الباني لا يُصدر إلا الدعوة اللطيفة المعتمدة — بلا أي
        # جملة تجعل الجزء التالي مشروطًا بالمتابعة/التعليق.
        text = tp.build_tiktok_caption("عنوان", "نص.",
                                       next_part=True)
        self.assertNotIn("لو عايز", text)
        self.assertNotIn("اكتب في التعليقات", text)
        self.assertNotIn("مش هينزل", text)
        self.assertEqual(caption_check.find_issues(text), [])

    def test_gate_sentence_in_title_rejected(self):
        # جملة بوابة في العنوان نفسه تُرفض (بلا إصلاح صامت).
        with self.assertRaises(tp.TikTokPublishError) as cm:
            tp.build_tiktok_caption(
                "لو عايز الجزء الثاني اعمل متابعة", "نص القصة.")
        self.assertIn("غير معتمدة", str(cm.exception))

    def test_no_network(self):
        patchers = _no_network()
        for p in patchers:
            p.start()
        try:
            tp.build_tiktok_caption("عنوان", "نص.", next_part=True,
                                    ai_voice=True)
        finally:
            for p in patchers:
                p.stop()


class TestValidateVideo(unittest.TestCase):
    def test_valid_video_with_probe_info(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            info = tp.validate_tiktok_video(
                video, probe_info=_probe(duration=45.0))
            self.assertEqual(info["video"], os.path.abspath(video))
            self.assertEqual(info["size"], 1024)
            self.assertEqual(info["duration"], 45.0)
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))

    def test_missing_video_rejected_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(tp.TikTokPublishError) as cm:
                tp.validate_tiktok_video(
                    os.path.join(td, "nope.mp4"))
            self.assertIn("غير موجود", str(cm.exception))

    def test_duration_over_limit_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(tp.TikTokPublishError) as cm:
                tp.validate_tiktok_video(
                    video, probe_info=_probe(duration=700.0))
            self.assertIn("600", str(cm.exception))

    def test_non_vertical_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(tp.TikTokPublishError):
                tp.validate_tiktok_video(
                    video, probe_info=_probe(width=1280, height=720))


class TestWriteBundle(unittest.TestCase):
    def _write(self, td, **kwargs):
        video = _mp4(td)
        bundle = os.path.join(td, "bundle")
        kwargs.setdefault("probe_info", _probe())
        return tp.write_tiktok_bundle(bundle, video, "عنوان القصة",
                                      "نص القصة.", **kwargs), video

    def test_three_files_exist(self):
        with tempfile.TemporaryDirectory() as td:
            res, _video = self._write(td)
            for name in ("metadata.json", "caption.txt", "steps.txt"):
                self.assertTrue(
                    os.path.isfile(os.path.join(res["bundle_dir"],
                                                name)),
                    name)

    def test_return_dict_keys(self):
        with tempfile.TemporaryDirectory() as td:
            res, _video = self._write(td)
            self.assertEqual(
                set(res.keys()),
                {"bundle_dir", "caption", "metadata_path",
                 "steps_path", "video_info"})
            self.assertEqual(res["metadata_path"],
                             os.path.join(res["bundle_dir"],
                                          "metadata.json"))
            self.assertEqual(res["steps_path"],
                             os.path.join(res["bundle_dir"],
                                          "steps.txt"))

    def test_metadata_valid_with_account_and_links(self):
        with tempfile.TemporaryDirectory() as td:
            res, video = self._write(td, moral="عبرة",
                                     next_part=True, ai_voice=True)
            with open(res["metadata_path"], encoding="utf-8") as f:
                meta = json.load(f)
            self.assertEqual(meta["platform"], "tiktok")
            self.assertEqual(meta["account"], "qisaswaebareg")
            self.assertEqual(meta["profile_url"],
                             "https://www.tiktok.com/@qisaswaebareg")
            self.assertEqual(meta["upload_url"],
                             "https://www.tiktok.com/upload")
            self.assertEqual(meta["video"], os.path.abspath(video))
            self.assertEqual(meta["caption"], res["caption"])
            self.assertEqual(meta["hashtags"], EXPECTED_HASHTAGS)
            self.assertEqual(meta["privacy"], "public")
            self.assertIn("created_at", meta)
            self.assertIn("video_info", meta)
            self.assertEqual(meta["video_info"]["duration"], 45.0)

    def test_bundle_probes_video_when_no_probe_info(self):
        # إصلاح دمج المنسق: بلا probe_info محقون يُقرأ الفيديو
        # عبر check.probe فتُسجَّل المدة والأبعاد والصوت في الحزمة.
        with tempfile.TemporaryDirectory() as td:
            stub = _probe(duration=47.6, width=720, height=1280,
                          has_audio=True)
            with mock.patch.object(tp.check_lib, "probe",
                                   return_value=stub) as probed:
                res, video = self._write(td, probe_info=None)
                probed.assert_called_once_with(video)
            self.assertEqual(res["video_info"]["duration"], 47.6)
            self.assertEqual(res["video_info"]["width"], 720)
            self.assertEqual(res["video_info"]["height"], 1280)
            self.assertTrue(res["video_info"]["has_audio"])

    def test_bundle_builds_when_probe_fails(self):
        # فشل الفحص لا يمنع بناء الحزمة — تُسجَّل القيم
        # «غير معروفة» وتُفحص عند الرفع (عقد validate_social_video).
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(
                    tp.check_lib, "probe",
                    side_effect=tp.check_lib.CheckError(
                        "لا يوجد مسار فيديو")):
                res, _video = self._write(td, probe_info=None)
            self.assertIsNone(res["video_info"]["duration"])
            self.assertIsNone(res["video_info"]["width"])
            self.assertIsNone(res["video_info"]["has_audio"])

    def test_caption_txt_is_caption_literally(self):
        with tempfile.TemporaryDirectory() as td:
            res, _video = self._write(td)
            with open(os.path.join(res["bundle_dir"], "caption.txt"),
                      encoding="utf-8") as f:
                self.assertEqual(f.read(), res["caption"])

    def test_steps_txt_contents(self):
        with tempfile.TemporaryDirectory() as td:
            res, video = self._write(td)
            with open(res["steps_path"], encoding="utf-8") as f:
                steps = f.read()
            self.assertIn("@qisaswaebareg", steps)
            self.assertIn("tiktok.com/upload", steps)
            self.assertIn(os.path.abspath(video), steps)
            self.assertIn("caption.txt", steps)
            self.assertIn("عامة", steps)
            self.assertIn("لا تتابع أحدًا", steps)
            self.assertIn("لا تعيد الرفع", steps)
            self.assertIn("ولا تسجّل بحساب آخر", steps)

    def test_invalid_video_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = os.path.join(td, "bundle")
            with self.assertRaises(tp.TikTokPublishError):
                tp.write_tiktok_bundle(
                    bundle, os.path.join(td, "nope.mp4"),
                    "عنوان", "نص.")
            self.assertFalse(os.path.exists(bundle))

    def test_no_network(self):
        patchers = _no_network()
        for p in patchers:
            p.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                self._write(td)
        finally:
            for p in patchers:
                p.stop()


class TestBrowserTaskBrief(unittest.TestCase):
    def test_brief_reads_written_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            bundle = os.path.join(td, "bundle")
            res = tp.write_tiktok_bundle(
                bundle, video, "عنوان", "نص.",
                probe_info=_probe())
            brief = tp.browser_task_brief(bundle)
            with open(res["steps_path"], encoding="utf-8") as f:
                self.assertEqual(brief, f.read())
            self.assertIn("@qisaswaebareg", brief)
            self.assertIn("tiktok.com/upload", brief)
            self.assertIn(os.path.abspath(video), brief)

    def test_brief_missing_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(tp.TikTokPublishError):
                tp.browser_task_brief(os.path.join(td, "nope"))

    def test_brief_wrong_platform_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = os.path.join(td, "bundle")
            os.makedirs(bundle)
            with open(os.path.join(bundle, "metadata.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"platform": "youtube",
                           "account": "qisaswaebareg"}, f)
            with open(os.path.join(bundle, "steps.txt"), "w",
                      encoding="utf-8") as f:
                f.write("خطوات")
            with self.assertRaises(tp.TikTokPublishError):
                tp.browser_task_brief(bundle)


class TestStatus(unittest.TestCase):
    def test_unconfigured_without_cfg(self):
        with tempfile.TemporaryDirectory() as td:
            st = tp.tiktok_status(studio_dir=td)
            self.assertFalse(st["configured"])
            self.assertEqual(st["username"], "qisaswaebareg")
            self.assertEqual(
                st["profile_url"],
                "https://www.tiktok.com/@qisaswaebareg")
            self.assertEqual(st["upload_method"], "browser-task")
            self.assertFalse(st["api_linked"])
            self.assertIn("غير مضبوط", st["detail"])

    def test_unconfigured_with_empty_username(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"tiktok_username": "   "}}
            st = tp.tiktok_status(cfg=cfg, studio_dir=td)
            self.assertFalse(st["configured"])

    def test_configured_with_username(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"tiktok_username": "qisaswaebareg"}}
            st = tp.tiktok_status(cfg=cfg, studio_dir=td)
            self.assertTrue(st["configured"])
            self.assertEqual(st["username"], "qisaswaebareg")
            self.assertIn("مضبوط", st["detail"])
            self.assertEqual(st["upload_method"], "browser-task")

    def test_api_linked_when_token_file_exists(self):
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("tiktok", "x" * 20, studio_dir=td)
            cfg = {"publish": {"tiktok_username": "qisaswaebareg"}}
            st = tp.tiktok_status(cfg=cfg, studio_dir=td)
            self.assertTrue(st["api_linked"])
            self.assertTrue(st["configured"])

    def test_detail_is_single_line(self):
        with tempfile.TemporaryDirectory() as td:
            st = tp.tiktok_status(studio_dir=td)
            self.assertNotIn("\n", st["detail"])

    def test_no_network(self):
        patchers = _no_network()
        for p in patchers:
            p.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                tp.tiktok_status(
                    cfg={"publish": {"tiktok_username": "qisaswaebareg"}},
                    studio_dir=td)
        finally:
            for p in patchers:
                p.stop()


class TestConstants(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(tp.TIKTOK_USERNAME_DEFAULT, "qisaswaebareg")
        self.assertEqual(tp.TIKTOK_PROFILE_URL,
                         "https://www.tiktok.com/@qisaswaebareg")
        self.assertEqual(tp.TIKTOK_UPLOAD_URL,
                         "https://www.tiktok.com/upload")
        self.assertEqual(tp.TIKTOK_CAPTION_LIMIT, 2200)


if __name__ == "__main__":
    unittest.main()
