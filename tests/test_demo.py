#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات القصة التجريبية — بلا Piper حقيقي وبلا ريندر.

بناء المشروع يُختبر بمحاكاة (mock) للسرد؛ والريندر الحقيقي يُتحقق
منه يدويًا عبر `studio.py run --demo` (انظر README).
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import demo


FAKE_CHUNKS = [
    {"text": "جملة أولى.", "start": 0.0, "end": 2.0},
    {"text": "جملة ثانية.", "start": 2.35, "end": 4.5},
]


def _fake_synthesize(text, out_wav, gap=0.35, **kw):
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    Path(out_wav).write_bytes(b"RIFFfake")
    n = len(text.split(".")) if text.strip() else 1
    chunks = [{"text": "جملة %d." % (i + 1),
               "start": round(i * 2.35, 3),
               "end": round(i * 2.35 + 2.0, 3)}
              for i in range(max(n - 1, 1))]
    return {"output": out_wav,
            "duration": round(len(chunks) * 2.35 - 0.35, 3),
            "chunks": chunks}


class TestLoadDemo(unittest.TestCase):
    def test_three_scenes_with_hook_and_moral(self):
        d = demo.load_demo()
        self.assertEqual(len(d["scenes"]), 3)
        self.assertTrue(d["title"])
        self.assertTrue(d["hook"])
        self.assertTrue(d["moral"])
        self.assertIn("سليم", d["scenes"][0])

    def test_hook_never_starts_with_number(self):
        d = demo.load_demo()
        self.assertFalse(d["hook"][:1].isdigit())


class TestSceneImage(unittest.TestCase):
    def test_generates_720x1280_jpeg(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "scene.jpg")
            demo.make_scene_image(path, 720, 1280, "gold")
            self.assertTrue(os.path.isfile(path))
            from PIL import Image
            with Image.open(path) as im:
                self.assertEqual(im.size, (720, 1280))
                self.assertEqual(im.mode, "RGB")


class TestBuildDemoProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = {"video": {"width": 720, "height": 1280, "fps": 30}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_tracks_cover_narration(self):
        with mock.patch("lib.demo.long_narration.synthesize_long",
                        side_effect=_fake_synthesize), \
             mock.patch("lib.demo.long_narration.concatenate_with_gaps",
                        return_value=10.0):
            project, info = demo.build_demo_project(
                self.cfg, self.tmp.name)
        self.assertEqual(project["width"], 720)
        self.assertEqual(project["height"], 1280)
        images = [t for t in project["tracks"] if t["type"] == "image"]
        self.assertEqual(len(images), 3)
        audios = [t for t in project["tracks"] if t["type"] == "audio"]
        self.assertEqual(len(audios), 1)
        self.assertEqual(audios[0]["src"], info["narration"])
        # الصور تغطي السرد كاملًا بلا فجوة
        self.assertAlmostEqual(images[-1]["start"] + images[-1]["duration"],
                               info["duration"], places=2)
        texts = [t for t in project["tracks"] if t["type"] == "text"]
        # قاعدة دائمة 2026-11-22: لا نص أعلى الشاشة أبدًا — هوك
        # الديمو أسفل فوق الكابشن ("above")، وكل العبارات أسفل.
        self.assertFalse(any(t["position"] == "top" for t in texts))
        hook = [t for t in texts if t["position"] == "above"]
        self.assertEqual(len(hook), 1)
        self.assertEqual((hook[0]["start"], hook[0]["end"]), (0, 4.0))
        bottoms = [t for t in texts if t["position"] == "bottom"]
        self.assertEqual(len(bottoms), len(info["chunks"]))
        for t in bottoms:
            self.assertLess(t["start"], t["end"])
            self.assertLessEqual(t["end"], info["duration"] + 0.01)
        # كل صورة لها Ken Burns
        self.assertTrue(all("ken_burns" in t for t in images))

    def test_run_demo_rejects_other_backends(self):
        with self.assertRaises(demo.DemoError):
            demo.run_demo(self.cfg, "/tmp/x.mp4", backend="mlt")


if __name__ == "__main__":
    unittest.main()
