#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات المُثبِّتات العدائية (v0.1.37 — البند 4 من تقرير tinker).

كل مُثبِّت يُشغَّل عبر دوال الخط الحالية (بلا Veo وبلا شبكة)
ويُؤكَّد أن الخط يمسك العيب المتوقع. المُثبِّتات تُولَّد في
مجلد مؤقت عبر tests/make_adversarial_fixtures.py — بلا ملفات
ثنائية ملتزمة (الصوت WAV مولَّد برمجيًا؛ والفيديو الطويل
مولَّد عبر ffmpeg lavfi في الاختبار نفسه).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import make_adversarial_fixtures as gen

from lib import ass_shaping
from lib import caption_check
from lib import check as check_lib
from lib import coverage
from lib import dna as dna_lib
from lib import openmontage_stage


def _silent_wav(path, seconds=1.0, sample_rate=16000):
    frames = int(seconds * sample_rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframesraw(b"\x00\x00" * frames)


class TestAdversarialFixtures(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.paths = gen.build_all(self.dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_hook_numeral_rewritten_in_words(self):
        # (أ) هوك يبدأ برقم يُعاد كتابته كلمات — لا يبدأ برقم أبدًا.
        with open(self.paths["hook_numeral"], encoding="utf-8") as f:
            story = json.load(f)
        fixed = dna_lib.normalize_hook(story["hook"])
        self.assertEqual(fixed, "ثلاثة أخطاء تدمر البيوت من غير ما تحس!")
        self.assertFalse(fixed[0].isdigit())
        # المشرقي مثل الغربي.
        self.assertEqual(dna_lib.normalize_hook("٣ أخطاء تدمر البيوت"),
                         "ثلاثة أخطاء تدمر البيوت")
        # هوك سليم يمر كما هو؛ وفوق العشرة يُترك للكاتب.
        self.assertEqual(dna_lib.normalize_hook("عنزة صغيرة هزّت القاهرة"),
                         "عنزة صغيرة هزّت القاهرة")
        self.assertEqual(dna_lib.normalize_hook("15 قصة مؤثرة"),
                         "15 قصة مؤثرة")

    def test_hook_numeral_normalized_at_stage(self):
        # التوصيل: stage() يطبّق التطبيع — كل الخلفيات تقرأ
        # الهوك من البيان، فلا يصل هوك رقمي لأي فيديو.
        proj = os.path.join(self.dir, "proj")
        os.makedirs(os.path.join(proj, "artifacts"))
        os.makedirs(os.path.join(proj, "assets", "images"))
        os.makedirs(os.path.join(proj, "assets", "audio"))
        with open(os.path.join(proj, "artifacts", "script.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"sections": [
                {"label": "Hook", "text": "3 أخطاء تدمر البيوت!"},
                {"label": "Body", "text": "رجل طيب دخل بيته."}]},
                f, ensure_ascii=False)
        with open(os.path.join(proj, "artifacts", "captions.json"),
                  "w", encoding="utf-8") as f:
            json.dump([{"word": "رجل", "startMs": 0, "endMs": 400,
                        "pageBreakAfter": True},
                       {"word": "طيب", "startMs": 400, "endMs": 800,
                        "pageBreakAfter": False}],
                      f, ensure_ascii=False)
        from PIL import Image
        Image.new("RGB", (100, 100), (200, 30, 30)).save(
            os.path.join(proj, "assets", "images", "scene1.jpg"))
        _silent_wav(os.path.join(proj, "assets", "audio",
                                 "narration-full.wav"), seconds=1.0)
        manifest = openmontage_stage.stage(proj, os.path.join(self.dir, "run"))
        self.assertEqual(manifest["hook"],
                         "ثلاثة أخطاء تدمر البيوت!")

    def test_follow_gate_caption_rejected_and_fixed(self):
        # (ب) جملة follow-gate يرفضها فحص الامتثال ويستبدلها الإصلاح.
        with open(self.paths["follow_gate"], encoding="utf-8") as f:
            caption = f.read()
        issues = caption_check.find_issues(caption)
        self.assertTrue(any(i["category"] == "next_part"
                            for i in issues),
                        "follow-gate لم يُكتشف: %s" % (issues,))
        result = caption_check.check_caption(caption)
        self.assertFalse(result["ok"])
        self.assertEqual(result["issues"], issues)
        fixed = caption_check.fix_caption(caption)
        self.assertIsNotNone(fixed)
        self.assertNotIn("لو عايز الجزء الثاني اعمل متابعة", fixed)
        self.assertEqual(caption_check.find_issues(fixed), [])

    def test_no_silence_scene_uses_word_timings(self):
        # (ج) مشهد سردي بلا فاصل صمت: silencedetect يجد لا شيء،
        # فلا توقيتات صمت تُبنى عليه؛ والخط يتخطى فحص الصوت
        # بلا إيجاب كاذب، وتوقيتات الكلمات تقسّم العبارات.
        # (انحراف موثق عن صيغة التقرير: fix-audio لا يطبَّق هنا
        # لأنه لا فجوة أصلًا — fix_silence_gaps يرجع fixed=False
        # على الصوت السليم — وcheck لا يفشل لأن غياب الصمت سليم؛
        # الممسوك فعلًا هو ألا تُبنى عبارات خاطئة من غياب الحدود.)
        silences = check_lib.detect_silences(
            self.paths["no_silence_wav"], min_seconds=0.3)
        self.assertEqual(silences, [])
        manifest = {"scenes": [
            {"start": 0.0, "end": 1.5, "text": "سنة 1184 عنزة صغيرة بقت"},
            {"start": 1.5, "end": 2.7, "text": "أشهر مخلوق في القاهرة"}],
            "narration": {"duration_seconds": 3.0}}
        ok, detail, skipped = coverage.check_phrase_audio(manifest, silences)
        self.assertTrue(ok)
        self.assertTrue(skipped)
        phrases = openmontage_stage.build_phrases(
            self.paths["no_silence_captions"])
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[0]["text"],
                         "سنة 1184 عنزة صغيرة بقت")
        self.assertAlmostEqual(phrases[0]["end"], 1.5, places=2)

    def test_long_story_rejected_by_duration(self):
        # (د) قصة مدتها المخططة >60ث تُرفض من فحص المدة —
        # وحدةً (eval_duration) ونهايةً (فيديو 61ث حقيقي).
        with open(self.paths["long_story"], encoding="utf-8") as f:
            story = json.load(f)
        ok, _detail = check_lib.eval_duration(
            story["planned_duration"], long_mode=False)
        self.assertFalse(ok)
        video = os.path.join(self.dir, "long-61s.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "lavfi", "-i", "color=c=black:s=320x240:d=61",
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-t", "61", "-c:v", "libx264", "-preset", "veryfast",
             "-c:a", "aac", video],
            check=True, timeout=120)
        report = check_lib.run_checks(video)
        duration_check = [c for c in report["checks"]
                          if c["name"] == "المدة"][0]
        self.assertFalse(duration_check["ok"])
        self.assertFalse(report["passed"])

    def test_broken_caption_caught_by_shaping_audit(self):
        # (هـ) U+FFFD وحروف Presentation Forms يمسكهما التدقيق.
        res = ass_shaping.audit_ass_file(self.paths["broken_caption"])
        self.assertFalse(res["ok"])
        kinds = {i["kind"] for i in res["issues"]}
        self.assertIn("replacement_char", kinds)
        self.assertIn("presentation_form", kinds)


if __name__ == "__main__":
    unittest.main()
