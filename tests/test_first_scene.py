#!/usr/bin/env python3
"""اختبارات عيّنة المشهد الأول في dry-run (v0.1.37 — البند 7).

العيّنة: نص الكابشن الأول كما سيظهر + أول جملة سرد منطوقة +
مدة المقطع الخام + سرعة atempo — بلا أي إنفاق أو شبكة.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import first_scene
from lib import openmontage_stage

QUEUE_TEXT = """# طابور قصص

## في الانتظار

4. **العنزة المباركة** — تحتاج جزأين
5. **عجائب الصدقة** — منشور واحد
"""


def _silent_wav(path, seconds=1.0, sample_rate=16000):
    frames = int(seconds * sample_rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframesraw(b"\x00\x00" * frames)


def _fake_project(base, name="demo-part1"):
    proj = os.path.join(base, name)
    os.makedirs(os.path.join(proj, "artifacts"))
    os.makedirs(os.path.join(proj, "assets", "images"))
    os.makedirs(os.path.join(proj, "assets", "audio"))
    with open(os.path.join(proj, "artifacts", "script.json"),
              "w", encoding="utf-8") as f:
        json.dump({"sections": [
            {"label": "Hook",
             "text": "عنزة صغيرة هزّت القاهرة!"},
            {"label": "Body",
             "text": "سنة 1184 عنزة صغيرة بقت أشهر مخلوق. "
                     "والناس كانت بتركع لها!"}]},
            f, ensure_ascii=False)
    with open(os.path.join(proj, "artifacts", "captions.json"),
              "w", encoding="utf-8") as f:
        json.dump([{"word": "سنة", "startMs": 0, "endMs": 300,
                    "pageBreakAfter": False},
                   {"word": "1184", "startMs": 300, "endMs": 600,
                    "pageBreakAfter": False},
                   {"word": "عنزة", "startMs": 600, "endMs": 900,
                    "pageBreakAfter": True},
                   {"word": "صغيرة", "startMs": 900, "endMs": 1200,
                    "pageBreakAfter": False}],
                  f, ensure_ascii=False)
    from PIL import Image
    Image.new("RGB", (100, 100), (200, 30, 30)).save(
        os.path.join(proj, "assets", "images", "scene1.jpg"))
    _silent_wav(os.path.join(proj, "assets", "audio",
                             "narration-full.wav"), seconds=1.0)
    return proj


class TestFirstSceneSample(unittest.TestCase):
    def test_sample_fields(self):
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "om")
            projects = os.path.join(root, "projects")
            os.makedirs(projects)
            _fake_project(projects)
            cfg = {"openmontage": {"root": root},
                   "video": {"image_clip_seconds": 5},
                   "narration": {"atempo": 1.25}}
            sample = first_scene.first_scene_sample(cfg, "demo-part1")
            self.assertIsNotNone(sample)
            self.assertEqual(sample["first_caption"],
                             "سنة 1184 عنزة")
            self.assertEqual(sample["first_sentence"],
                             "عنزة صغيرة هزّت القاهرة")
            self.assertEqual(sample["clip_file"], "scene1.jpg")
            self.assertEqual(sample["clip_seconds"], 5)
            self.assertEqual(sample["clip_kind"], "image")
            self.assertEqual(sample["atempo"], 1.25)
            text = first_scene.format_sample(sample)
            self.assertIn("سنة 1184 عنزة", text)
            self.assertIn("عنزة صغيرة هزّت القاهرة", text)
            self.assertIn("scene1.jpg", text)
            self.assertIn("1.25", text)

    def test_defaults_without_narration_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "om")
            projects = os.path.join(root, "projects")
            os.makedirs(projects)
            _fake_project(projects)
            sample = first_scene.first_scene_sample(
                {"openmontage": {"root": root}}, "demo-part1")
            self.assertEqual(sample["atempo"], 1.0)
            self.assertEqual(sample["clip_seconds"], 5)

    def test_missing_project_returns_none(self):
        sample = first_scene.first_scene_sample(
            {"openmontage": {"root": "/no/such/root"}}, "ghost")
        self.assertIsNone(sample)

    @unittest.skipUnless(
        os.path.isdir(os.path.expanduser(
            "~/workspace/openmontage/projects/anza-part1")),
        "مشروع العنزة الحقيقي غائب — بيئة CI")
    def test_daily_dry_run_prints_sample(self):
        # مشروع العنزة الحقيقي — أول عبارة حقيقية حرفيًا.
        with tempfile.TemporaryDirectory() as d:
            queue = os.path.join(d, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(QUEUE_TEXT)
            cfg = {
                "paths": {
                    "queue_file": queue,
                    "videos_dir": os.path.join(d, "videos"),
                    "runs_dir": os.path.join(d, "runs"),
                },
                "publish": {"page_id": "1048148471706586",
                            "youtube_channel_id":
                                "UCz5VeqN-eolCaCPGTpiWtJw"},
                "veo": {"balance_units": 680,
                        "renews": "2026-12-13"},
                "openmontage": {
                    "root": os.path.expanduser("~/workspace/openmontage"),
                    "projects_dir": os.path.expanduser(
                        "~/workspace/openmontage/projects")},
                "video": {"image_clip_seconds": 5},
                "narration": {"atempo": 1.25},
            }
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = studio.cmd_daily(cfg, slot="evening", execute=False)
            out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("عيّنة المشهد الأول", out)
            self.assertIn(
                "سنة 1184… عنزة صغيرة بقت أشهر مخلوق في القاهرة، "
                "والناس كانت بتركع لها!", out)
            self.assertIn("1.25", out)

    @unittest.skipUnless(
        os.path.isdir(os.path.expanduser(
            "~/workspace/openmontage/projects/anza-part1")),
        "مشروع العنزة الحقيقي غائب — بيئة CI")
    def test_batch_dry_run_prints_sample(self):
        with tempfile.TemporaryDirectory() as d:
            queue = os.path.join(d, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(QUEUE_TEXT)
            cfg = {
                "paths": {
                    "queue_file": queue,
                    "videos_dir": os.path.join(d, "videos"),
                    "runs_dir": os.path.join(d, "runs"),
                },
                "publish": {"page_id": "1048148471706586",
                            "youtube_channel_id":
                                "UCz5VeqN-eolCaCPGTpiWtJw"},
                "veo": {"balance_units": 680,
                        "renews": "2026-12-13"},
                "openmontage": {
                    "root": os.path.expanduser("~/workspace/openmontage"),
                    "projects_dir": os.path.expanduser(
                        "~/workspace/openmontage/projects")},
                "video": {"image_clip_seconds": 5},
            }
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = studio.cmd_batch(cfg, count=1,
                                      source="openmontage",
                                      execute=False)
            out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("عيّنة المشهد الأول", out)
            self.assertIn("سنة 1184… عنزة صغيرة", out)


if __name__ == "__main__":
    unittest.main()
