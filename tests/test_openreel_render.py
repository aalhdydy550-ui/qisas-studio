#!/usr/bin/env python3
"""اختبارات طبقة تجميع OpenReel (lib.openreel_render).

تعمل بـ `python3 -m unittest tests.test_openreel_render -v` من مجلد studio.
تولّد أصول اختبار صغيرة (صور Pillow + سرد sine عبر ffmpeg) — بلا Veo
وبلا شبكة. اختبار الريندر الحقيقي قصير (12 ثانية) عمدًا.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import openreel_render as or_lib

RENDER_PATH = os.path.expanduser("~/workspace/openreel-auto/render.py")


def _make_image(path, color=(60, 40, 20)):
    from PIL import Image
    img = Image.new("RGB", (720, 1280), color)
    img.save(path, "JPEG")


def _make_wav(path, duration=12):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=440:sample_rate=48000:duration=%s" % duration,
         "-t", str(duration), path],
        check=True, timeout=120)


def _manifest(assets_dir, duration=12.0, clip_seconds=5, phrases=None):
    return {
        "project": "test-story",
        "sequence": ["scene1.jpg", "scene2.jpg"],
        "image_clip_seconds": clip_seconds,
        "narration_duration": duration,
        "phrases": phrases if phrases is not None else [
            {"text": "عبارة أولى", "start": 0.5, "end": 4.5},
            {"text": "عبارة ثانية", "start": 5.5, "end": 9.5},
        ],
    }


class TestBuildProject(unittest.TestCase):
    def test_image_clips_and_narration_and_texts(self):
        manifest = _manifest(None)
        project = or_lib.build_project(manifest, "هوك صادم",
                                       "/tmp/assets", {"width": 720,
                                                       "height": 1280,
                                                       "fps": 30})
        self.assertEqual(project["format"], "openreel-auto")
        self.assertEqual(project["version"], 1)
        self.assertEqual(project["settings"]["width"], 720)
        self.assertEqual(project["settings"]["height"], 1280)
        # مقطعان: الأول 5ث، والثاني ممدَّد ليغطي السرد (12ث)
        self.assertEqual(len(project["clips"]), 2)
        self.assertEqual(project["clips"][0]["kind"], "image")
        self.assertEqual(project["clips"][0]["duration"], 5)
        self.assertEqual(project["clips"][1]["duration"], 7)
        self.assertEqual(project["clips"][0]["file"],
                         "/tmp/assets/images/scene1.jpg")
        self.assertEqual(project["narration"]["file"],
                         "/tmp/assets/audio/narration-full.wav")
        self.assertEqual(project["narration"]["volume"], 1.0)
        texts = project["texts"]
        # الهوك أسفل الشاشة فوق العبارات أول 4 ثوانٍ (قاعدة دائمة
        # 2026-11-22: لا نص أعلى أبدًا) + عبارتان أسفلها؛ ولا موضع
        # "top" في أي نص مولَّد.
        self.assertEqual(texts[0]["text"], "هوك صادم")
        self.assertEqual(texts[0]["position"], "bottom")
        self.assertEqual(texts[0]["end"], 4.0)
        # إحداثيات صريحة فوق نطاق الكابشن: x وسط الإطار، وy حافة
        # الهوك السفلى 280px فوق أسفل الإطار (1280-280=1000).
        self.assertEqual(texts[0]["x"], 360)
        self.assertEqual(texts[0]["y"], 1000)
        self.assertFalse(any(t["position"] == "top" for t in texts))
        self.assertEqual(texts[1]["text"], "عبارة أولى")
        self.assertEqual(texts[1]["position"], "bottom")
        self.assertEqual(texts[1]["start"], 0.5)
        self.assertEqual(texts[2]["text"], "عبارة ثانية")

    def test_no_title_no_hook_text(self):
        manifest = _manifest(None, phrases=[])
        project = or_lib.build_project(manifest, "", "/tmp/assets",
                                       {"width": 720, "height": 1280,
                                        "fps": 30})
        self.assertEqual(project["texts"], [])

    def test_short_narration_no_extension(self):
        manifest = _manifest(None, duration=8.0)
        project = or_lib.build_project(manifest, "هوك", "/tmp/assets",
                                       {"width": 720, "height": 1280,
                                        "fps": 30})
        self.assertEqual(project["clips"][1]["duration"], 5)

    def test_path_traversal_rejected(self):
        manifest = _manifest(None)
        manifest["sequence"] = ["../../etc/passwd"]
        with self.assertRaises(ValueError):
            or_lib.build_project(manifest, "هوك", "/tmp/assets",
                                 {"width": 720, "height": 1280,
                                  "fps": 30})


class TestRenderProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="openreel-test-")
        self.assets = os.path.join(self.tmp, "assets")
        os.makedirs(os.path.join(self.assets, "images"))
        os.makedirs(os.path.join(self.assets, "audio"))
        _make_image(os.path.join(self.assets, "images", "scene1.jpg"),
                    (60, 40, 20))
        _make_image(os.path.join(self.assets, "images", "scene2.jpg"),
                    (20, 50, 30))
        _make_wav(os.path.join(self.assets, "audio", "narration-full.wav"),
                  duration=12)

    def test_real_render_12s(self):
        if not os.path.isfile(RENDER_PATH):
            self.skipTest("render.py غير موجود: %s" % RENDER_PATH)
        manifest = _manifest(self.assets)
        project = or_lib.build_project(
            manifest, "هوك صادم", self.assets,
            {"width": 720, "height": 1280, "fps": 30})
        project_path = os.path.join(self.tmp, "project.json")
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False)
        out_path = os.path.join(self.tmp, "out.mp4")
        result = or_lib.render_project(RENDER_PATH, project_path,
                                       out_path)
        self.assertTrue(os.path.isfile(out_path))
        self.assertEqual(result["output"], out_path)
        self.assertGreater(result["size_bytes"], 10000)
        info = check_lib.probe(out_path)
        self.assertEqual((info["width"], info["height"]), (720, 1280))
        self.assertTrue(info["has_audio"])
        self.assertAlmostEqual(info["duration"], 12.0, delta=0.5)

    def test_missing_render_script(self):
        with self.assertRaises(or_lib.OpenReelError):
            or_lib.render_project("/tmp/no-such-render.py",
                                  "/tmp/x.json", "/tmp/y.mp4")

    def test_missing_media_fails_arabic(self):
        if not os.path.isfile(RENDER_PATH):
            self.skipTest("render.py غير موجود: %s" % RENDER_PATH)
        manifest = _manifest(self.assets)
        manifest["sequence"] = ["missing.jpg"]
        project = or_lib.build_project(
            manifest, "هوك", self.assets,
            {"width": 720, "height": 1280, "fps": 30})
        project_path = os.path.join(self.tmp, "bad-project.json")
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False)
        with self.assertRaises(or_lib.OpenReelError) as ctx:
            or_lib.render_project(RENDER_PATH, project_path,
                                  os.path.join(self.tmp, "bad.mp4"))
        self.assertIn("غير موجود", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
