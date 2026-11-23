#!/usr/bin/env python3
"""اختبارات مجموعة التقييم الثابتة والبيان — جولة v0.1.37
(مقترحا tinker رقما 5 و2).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import eval_set as eval_set_lib
from lib import manifest as manifest_lib

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS_DIR = os.path.expanduser("~/workspace/videos")


def _make_video(out, duration=10, size="720x1280"):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
           "color=c=0x2a2a2a:s=%s:r=30:d=%s" % (size, duration),
           "-f", "lavfi", "-i",
           "sine=frequency=440:sample_rate=48000:duration=%s" % duration,
           "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", out]
    subprocess.run(cmd, check=True, timeout=300)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg/ffprobe غير متاحين")
class TestEvalSet(unittest.TestCase):
    def test_set_loads_five_seeded_videos(self):
        data = eval_set_lib.load_eval_set()
        self.assertEqual(data["seed"], 20261122)
        videos = eval_set_lib.eval_videos(data)
        self.assertEqual(len(videos), 5)
        self.assertEqual([v["id"] for v in videos],
                         ["najjar", "aisha1", "hamati", "anza",
                          "manqasha2"])

    def test_baseline_numbers_are_real_not_zero(self):
        # الأرقام المسجلة حقيقية: هوك 2–3/9 ومدد فعلية؛ وnull
        # تعني غير مقاس لا صفرًا.
        videos = eval_set_lib.eval_videos()
        by_id = {v["id"]: v for v in videos}
        self.assertEqual(by_id["najjar"]["hook_score"], 3)
        self.assertEqual(by_id["najjar"]["duration_seconds"], 47.6)
        self.assertEqual(by_id["najjar"]["wpm"], 126.1)
        self.assertEqual(by_id["najjar"]["facebook_views"], 702)
        self.assertEqual(by_id["aisha1"]["youtube_views"], 341)
        self.assertIsNone(by_id["manqasha2"]["duration_seconds"])
        self.assertIsNone(by_id["manqasha2"]["video_file"])

    def test_compare_detects_change_and_ignores_nulls(self):
        base = {"hook_score": 3, "duration_seconds": 47.6,
                "wpm": 126.1, "silence_ok": True, "shot_count": 5,
                "avg_shot_seconds": 9.52}
        same = dict(base)
        self.assertEqual(
            [d for d in eval_set_lib.compare_measurement(base, same)
             if d["changed"]], [])
        changed = dict(base, hook_score=5, wpm=None)
        diffs = [d for d in
                 eval_set_lib.compare_measurement(base, changed)
                 if d["changed"]]
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["metric"], "hook_score")
        self.assertEqual(diffs[0]["delta"], 2)

    @unittest.skipUnless(
        all(os.path.isfile(os.path.expanduser(p)) for p in (
            "~/workspace/videos/najjar-full-fixed.mp4",
            "~/workspace/videos/aisha-part1-full.mp4",
            "~/workspace/videos/hamati-full.mp4",
            "~/workspace/videos/openmontage-anza-part1-fixed.mp4")),
        "فيديوهات مجموعة التقييم غائبة — بيئة CI")
    def test_snapshot_cli_matches_baseline(self):
        # اللقطة الحية على الفيديوهات الأربعة المحلية تطابق
        # الأساس (نفس الأدوات ونفس الهوكات) — أي فرق هنا
        # انحدار حقيقي لا ضجيج قياس.
        proc = subprocess.run(
            [sys.executable, "studio.py", "analyze", "--snapshot"],
            cwd=STUDIO_ROOT, capture_output=True, text=True, timeout=900)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("مطابق للأساس", proc.stdout)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg/ffprobe غير متاحين")
class TestManifest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.video = os.path.join(self.td, "test.mp4")
        _make_video(self.video)

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_build_write_verify_ok(self):
        man = manifest_lib.build_manifest(
            self.video, title="قصة تجريبية", hook="هوك تجريبي",
            story="نص القصة", source="studio")
        path = manifest_lib.write_manifest(self.video, man)
        self.assertTrue(os.path.isfile(path))
        status, issues = manifest_lib.verify_manifest(self.video)
        self.assertEqual(status, "ok", issues)

    def test_missing_legacy_is_warning_only(self):
        # فيديو قديم (mtime قبل الحد) بلا بيان = legacy لا فشل.
        old = os.path.join(self.td, "old.mp4")
        _make_video(old)
        ancient = 1700000000  # 2023 — قبل الحد الفاصل بزمن
        os.utime(old, (ancient, ancient))
        status, _ = manifest_lib.verify_manifest(old)
        self.assertEqual(status, "legacy")

    def test_missing_new_is_refused(self):
        status, issues = manifest_lib.verify_manifest(self.video)
        self.assertEqual(status, "missing")
        self.assertTrue(issues)

    def test_mismatch_after_modification(self):
        manifest_lib.write_manifest(
            self.video,
            manifest_lib.build_manifest(
                self.video, title="t", hook="h", source="studio"))
        # عدّل الفيديو بعد البيان (أعد كتابته بمدة مختلفة).
        _make_video(self.video, duration=12)
        status, issues = manifest_lib.verify_manifest(self.video)
        self.assertEqual(status, "mismatch", issues)

    def test_invalid_missing_field(self):
        man = manifest_lib.build_manifest(
            self.video, title="t", hook="h", source="studio")
        del man["hook"]
        manifest_lib.write_manifest(self.video, man)
        status, issues = manifest_lib.verify_manifest(self.video)
        self.assertEqual(status, "invalid", issues)

    def test_manifest_cli_generates_for_legacy_video(self):
        proc = subprocess.run(
            [sys.executable, "studio.py", "manifest", "--video",
             self.video, "--title", "قصة تجريبية",
             "--hook", "هوك تجريبي"],
            cwd=STUDIO_ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        status, _ = manifest_lib.verify_manifest(self.video)
        self.assertEqual(status, "ok")


if __name__ == "__main__":
    unittest.main()
