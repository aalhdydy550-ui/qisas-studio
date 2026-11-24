#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مقاطع الحركة المولّدة للفيديو الطويل (lib.motion_clips).

تعمل بـ `python3 -m unittest tests.test_motion_clips -v`.
المانيفستات تركيبية صغيرة تُكتب في مجلد مؤقت، وملفات mp4 وهمية
فارغة (يكفي وجود الملف — التخطيط لا يقرأ محتوى الفيديو).
لا شبكة ولا ريندر فعلي.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import motion_clips

# المانيفست الحقيقي (خارج الشجرة — يُستخدم فقط إن وُجد، وإلا skip).
REAL_MANIFEST = os.path.expanduser(
    "~/workspace/flow-eval/phase1-wan-motion/manifest.json")

JSON_MANIFEST = {
    "generation_seconds": 5.04,
    "clips": [
        {"clip_id": "L-C01", "plan": "plan-a", "slice": "long-a",
         "duration_needed_s": 7.587,
         "generations": ["L-C01-a", "L-C01-b"],
         "coverage_note": "توليدان مستقلان"},
        {"clip_id": "L-C02", "plan": "plan-b", "slice": "long-a",
         "duration_needed_s": 4.413,
         "generations": ["L-C02-a"],
         "coverage_note": "توليد واحد"},
        {"clip_id": "L-C03", "plan": "plan-c", "slice": "shorts",
         "duration_needed_s": 5.0,
         "generations": ["L-C03-a"],
         "coverage_note": ""},
    ],
    "generations_list": [
        {"gen_id": "L-C01-a", "clip_id": "L-C01", "slice": "long-a",
         "scene": "chapter 1", "first_frame": "img1.jpg",
         "output_name": "L-C01-a.mp4", "take": "a"},
        {"gen_id": "L-C01-b", "clip_id": "L-C01", "slice": "long-a",
         "scene": "chapter 1", "first_frame": "img1.jpg",
         "output_name": "L-C01-b.mp4", "take": "b"},
        {"gen_id": "L-C02-a", "clip_id": "L-C02", "slice": "long-a",
         "scene": "chapter 2", "first_frame": "img2.jpg",
         "output_name": "L-C02-a.mp4", "take": "a"},
        {"gen_id": "L-C03-a", "clip_id": "L-C03", "slice": "shorts",
         "scene": "chapter 1", "first_frame": "img3.jpg",
         "output_name": "L-C03-a.mp4", "take": "a"},
    ],
}

CSV_ROWS = [
    {"gen_id": "L-C01-a", "clip_id": "L-C01", "slice": "long-a",
     "scene": "chapter 1", "first_frame": "img1.jpg",
     "output_name": "L-C01-a.mp4", "take": "a",
     "generation_seconds": "5.04", "duration_needed_s": "7.587"},
    {"gen_id": "L-C01-b", "clip_id": "L-C01", "slice": "long-a",
     "scene": "chapter 1", "first_frame": "img1.jpg",
     "output_name": "L-C01-b.mp4", "take": "b",
     "generation_seconds": "5.04", "duration_needed_s": "7.587"},
    {"gen_id": "L-C02-a", "clip_id": "L-C02", "slice": "long-a",
     "scene": "chapter 2", "first_frame": "img2.jpg",
     "output_name": "L-C02-a.mp4", "take": "a",
     "generation_seconds": "5.04", "duration_needed_s": "4.413"},
    {"gen_id": "L-C03-a", "clip_id": "L-C03", "slice": "shorts",
     "scene": "chapter 1", "first_frame": "img3.jpg",
     "output_name": "L-C03-a.mp4", "take": "a",
     "generation_seconds": "5.04", "duration_needed_s": "5.0"},
]


def _touch(path):
    with open(path, "wb") as f:
        f.write(b"")


class MotionClipsBase(unittest.TestCase):
    """مانيفست JSON + ملفات mp4 وهمية في مجلد مؤقت."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.motion_dir = os.path.join(self.tmp.name, "motion")
        os.makedirs(self.motion_dir)
        for name in ("L-C01-a.mp4", "L-C01-b.mp4", "L-C02-a.mp4",
                     "L-C03-a.mp4"):
            _touch(os.path.join(self.motion_dir, name))
        self.manifest_path = os.path.join(self.tmp.name, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(JSON_MANIFEST, f, ensure_ascii=False)
        self.manifest = motion_clips.load_motion_manifest(
            self.manifest_path)
        self.img = os.path.join(self.tmp.name, "img1.jpg")
        _touch(self.img)

    def tearDown(self):
        self.tmp.cleanup()

    def _chapter(self, duration=12.0, motion_clips_ids=None, images=None):
        ch = {"title": "فصل تجريبي", "duration": duration,
              "images": images or [self.img]}
        if motion_clips_ids is not None:
            ch["motion_clips"] = motion_clips_ids
        return ch


class TestLoadJsonManifest(MotionClipsBase):
    def test_clips_and_generations(self):
        self.assertEqual(self.manifest["generation_seconds"], 5.04)
        self.assertEqual(set(self.manifest["clips"]),
                         {"L-C01", "L-C02", "L-C03"})
        self.assertEqual(self.manifest["clips"]["L-C01"]["generations"],
                         ["L-C01-a", "L-C01-b"])
        self.assertEqual(
            self.manifest["clips"]["L-C01"]["duration_needed_s"], 7.587)
        self.assertEqual(len(self.manifest["generations"]), 4)
        gen = self.manifest["generations"]["L-C01-b"]
        self.assertEqual(gen["clip_id"], "L-C01")
        self.assertEqual(gen["output_name"], "L-C01-b.mp4")
        self.assertEqual(gen["scene"], "chapter 1")
        self.assertEqual(gen["take"], "b")

    def test_real_example_c01(self):
        """مثال حقيقي: C01 → توليدان ومدة 7.587 ثانية."""
        clip = self.manifest["clips"]["L-C01"]
        self.assertEqual(clip["generations"], ["L-C01-a", "L-C01-b"])
        self.assertEqual(clip["duration_needed_s"], 7.587)


class TestLoadCsvManifest(MotionClipsBase):
    def test_same_structure_as_json(self):
        csv_path = os.path.join(self.tmp.name, "manifest.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=list(CSV_ROWS[0].keys()))
            writer.writeheader()
            writer.writerows(CSV_ROWS)
        loaded = motion_clips.load_motion_manifest(csv_path)
        self.assertEqual(loaded["generation_seconds"], 5.04)
        self.assertEqual(set(loaded["clips"]),
                         {"L-C01", "L-C02", "L-C03"})
        self.assertEqual(loaded["clips"]["L-C01"]["generations"],
                         ["L-C01-a", "L-C01-b"])
        self.assertEqual(
            loaded["clips"]["L-C01"]["duration_needed_s"], 7.587)
        self.assertEqual(loaded["clips"]["L-C02"]["duration_needed_s"],
                         4.413)
        self.assertEqual(len(loaded["generations"]), 4)
        self.assertEqual(
            loaded["generations"]["L-C02-a"]["output_name"],
            "L-C02-a.mp4")
        self.assertEqual(
            loaded["generations"]["L-C03-a"]["scene"], "chapter 1")


class TestLoadManifestErrors(unittest.TestCase):
    def _write(self, tmp, name, text):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_missing_file(self):
        with self.assertRaises(motion_clips.MotionError):
            motion_clips.load_motion_manifest("/nonexistent/manifest.json")

    def test_broken_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "m.json", "{not json")
            with self.assertRaises(motion_clips.MotionError):
                motion_clips.load_motion_manifest(path)

    def test_empty_clips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "m.json", json.dumps(
                {"generation_seconds": 5.04, "clips": [],
                 "generations_list": []}))
            with self.assertRaises(motion_clips.MotionError):
                motion_clips.load_motion_manifest(path)

    def test_generation_without_output_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"generation_seconds": 5.04,
                    "clips": [{"clip_id": "C1", "generations": ["G1"]}],
                    "generations_list": [
                        {"gen_id": "G1", "clip_id": "C1",
                         "output_name": ""}]}
            path = self._write(tmp, "m.json", json.dumps(data))
            with self.assertRaises(motion_clips.MotionError):
                motion_clips.load_motion_manifest(path)

    def test_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "m.txt", "x")
            with self.assertRaises(motion_clips.MotionError):
                motion_clips.load_motion_manifest(path)


class TestPlanClipSegments(MotionClipsBase):
    def test_short_need_uses_a_only(self):
        res = motion_clips.plan_clip_segments(
            "L-C02", 3.0, self.manifest, self.motion_dir)
        self.assertEqual(len(res["segments"]), 1)
        seg = res["segments"][0]
        self.assertEqual(seg["kind"], "video")
        self.assertEqual(seg["in"], 0.0)
        self.assertEqual(seg["out"], 3.0)
        self.assertTrue(seg["src"].endswith("L-C02-a.mp4"))
        self.assertEqual(res["warnings"], [])

    def test_need_7587_uses_a_full_then_b_start(self):
        res = motion_clips.plan_clip_segments(
            "L-C01", 7.587, self.manifest, self.motion_dir)
        self.assertEqual(len(res["segments"]), 2)
        a, b = res["segments"]
        self.assertEqual((a["kind"], a["in"], a["out"]),
                         ("video", 0.0, 5.04))
        self.assertTrue(a["src"].endswith("L-C01-a.mp4"))
        self.assertEqual((b["kind"], b["in"], b["out"]),
                         ("video", 0.0, 2.547))
        self.assertTrue(b["src"].endswith("L-C01-b.mp4"))
        self.assertEqual(res["warnings"], [])

    def test_missing_b_freezes_remainder_with_warning(self):
        res = motion_clips.plan_clip_segments(
            "L-C02", 7.0, self.manifest, self.motion_dir)
        self.assertEqual(len(res["segments"]), 2)
        a, freeze = res["segments"]
        self.assertEqual((a["kind"], a["in"], a["out"]),
                         ("video", 0.0, 5.04))
        self.assertEqual(freeze["kind"], "freeze")
        self.assertEqual(freeze["duration"], 1.96)
        self.assertTrue(freeze["src"].endswith("L-C02-a.mp4"))
        self.assertEqual(len(res["warnings"]), 1)
        self.assertIn("جمَّد", res["warnings"][0])

    def test_missing_b_file_freezes_too(self):
        os.remove(os.path.join(self.motion_dir, "L-C01-b.mp4"))
        res = motion_clips.plan_clip_segments(
            "L-C01", 7.587, self.manifest, self.motion_dir)
        kinds = [s["kind"] for s in res["segments"]]
        self.assertEqual(kinds, ["video", "freeze"])
        self.assertEqual(res["segments"][1]["duration"], 2.547)
        self.assertIn("جمَّد", res["warnings"][0])

    def test_need_longer_than_two_generations_freezes_tail(self):
        res = motion_clips.plan_clip_segments(
            "L-C01", 12.0, self.manifest, self.motion_dir)
        kinds = [s["kind"] for s in res["segments"]]
        self.assertEqual(kinds, ["video", "video", "freeze"])
        self.assertEqual(res["segments"][1]["out"], 5.04)
        self.assertEqual(res["segments"][2]["duration"], 1.92)
        self.assertIn("جمَّد", res["warnings"][0])

    def test_missing_a_raises(self):
        os.remove(os.path.join(self.motion_dir, "L-C01-a.mp4"))
        with self.assertRaises(motion_clips.MotionError):
            motion_clips.plan_clip_segments(
                "L-C01", 3.0, self.manifest, self.motion_dir)

    def test_bad_durations_raise(self):
        for bad in (0, -1.0, "abc", 3601):
            with self.assertRaises(motion_clips.MotionError,
                                   msg="مدة %r" % (bad,)):
                motion_clips.plan_clip_segments(
                    "L-C01", bad, self.manifest, self.motion_dir)

    def test_unknown_clip_raises(self):
        with self.assertRaises(motion_clips.MotionError):
            motion_clips.plan_clip_segments(
                "L-C99", 3.0, self.manifest, self.motion_dir)


class TestResolveChapterMotion(MotionClipsBase):
    def test_explicit_clips_cover_chapter(self):
        ch = self._chapter(duration=12.0,
                           motion_clips_ids=["L-C01", "L-C02"])
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 1)
        self.assertEqual(res["mode"], "clips")
        total = sum(motion_clips._segment_duration(s)
                    for s in res["segments"])
        self.assertAlmostEqual(total, 12.0, places=2)
        self.assertTrue(all(s["kind"] == "video"
                            for s in res["segments"]))
        self.assertEqual(res["warnings"], [])

    def test_no_clips_falls_back_to_still(self):
        ch = self._chapter(duration=12.0)
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 5)
        self.assertEqual(res["mode"], "still")
        self.assertTrue(all(s["kind"] == "image"
                            for s in res["segments"]))
        total = sum(s["duration"] for s in res["segments"])
        self.assertAlmostEqual(total, 12.0, places=2)
        self.assertEqual(len(res["warnings"]), 1)
        self.assertIn("بلا Ken Burns", res["warnings"][0])

    def test_clips_run_out_then_still_tail(self):
        ch = self._chapter(duration=12.0,
                           motion_clips_ids=["L-C02"])
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 1)
        kinds = [s["kind"] for s in res["segments"]]
        self.assertEqual(kinds, ["video", "image", "image"])
        self.assertAlmostEqual(res["segments"][0]["out"], 4.413, places=2)
        # باقي المدة (7.587ث) يُقسَّم إلى صور 5ث متناوبة بدل صورة
        # واحدة متجمدة (إصلاح فجوة 2026-11-24): 5.0 + 2.587.
        self.assertAlmostEqual(res["segments"][1]["duration"], 5.0,
                               places=2)
        self.assertAlmostEqual(res["segments"][2]["duration"], 2.587,
                               places=2)
        self.assertEqual(res["mode"], "clips")
        self.assertEqual(len(res["warnings"]), 1)
        self.assertIn("صور ثابتة متناوبة", res["warnings"][0])

    def _riddle_chapter_2_manifest(self):
        """مانيفست بمقطع واحد 6.855ث بتوليدين — سيناريو الفصل 2
        في الألغاز (فيديو 6.855ث وباقٍ 53.421ث)."""
        manifest = {
            "generation_seconds": 5.04,
            "clips": {"C-X": {"generations": ["C-X-a", "C-X-b"],
                              "duration_needed_s": 6.855,
                              "coverage_note": ""}},
            "generations": {
                "C-X-a": {"clip_id": "C-X",
                          "output_name": "C-X-a.mp4",
                          "scene": "chapter 2", "slice": "",
                          "take": "a", "first_frame": ""},
                "C-X-b": {"clip_id": "C-X",
                          "output_name": "C-X-b.mp4",
                          "scene": "chapter 2", "slice": "",
                          "take": "b", "first_frame": ""},
            },
        }
        for name in ("C-X-a.mp4", "C-X-b.mp4"):
            _touch(os.path.join(self.motion_dir, name))
        return manifest

    def _three_images(self):
        images = [os.path.join(self.tmp.name, "img%d.jpg" % n)
                  for n in (1, 2, 3)]
        for p in images:
            _touch(p)
        return images

    def test_remainder_split_into_alternating_stills_youtube_long(self):
        # سيناريو الفصل 2 في الألغاز (تقرير التحويل §7): فيديو
        # 6.855ث ثم باقٍ 53.421ث — قبل الإصلاح صورة واحدة 53.421ث.
        manifest = self._riddle_chapter_2_manifest()
        images = self._three_images()
        ch = self._chapter(duration=60.276, motion_clips_ids=["C-X"],
                           images=images)
        res = motion_clips.resolve_chapter_motion(
            ch, manifest, self.motion_dir, 2, clip_seconds=2.5)
        video = [s for s in res["segments"] if s["kind"] == "video"]
        stills = [s for s in res["segments"] if s["kind"] == "image"]
        self.assertEqual(res["mode"], "clips")
        video_s = sum(motion_clips._segment_duration(s) for s in video)
        self.assertAlmostEqual(video_s, 6.855, places=2)
        # 53.421 / 2.5 = 21.37 → 21 صورة: 20 × 2.5ث + الأخيرة 3.421ث
        # (ممددة للباقي فقط — بحد أقصى 1.5 × المقدار = 3.75ث).
        self.assertEqual(len(stills), 21)
        self.assertTrue(all(s["duration"] == 2.5 for s in stills[:-1]))
        self.assertAlmostEqual(stills[-1]["duration"], 3.421, places=2)
        self.assertTrue(all(s["duration"] <= 3.75 for s in stills))
        # الصور متناوبة من صور الفصل لا صورة واحدة مكررة.
        self.assertEqual([s["src"] for s in stills],
                         [images[i % 3] for i in range(21)])
        total = sum(motion_clips._segment_duration(s)
                    for s in res["segments"])
        self.assertAlmostEqual(total, 60.276, places=2)
        self.assertIn("صور ثابتة متناوبة", res["warnings"][0])

    def test_remainder_split_into_alternating_stills_clips(self):
        # نفس الفصل في وضع clips الافتراضي (5ث): 53.421ث → 11 صورة
        # (10 × 5.0ث + الأخيرة 3.421ث) — الافتراضي يبقى 5ث كما هو.
        manifest = self._riddle_chapter_2_manifest()
        images = self._three_images()
        ch = self._chapter(duration=60.276, motion_clips_ids=["C-X"],
                           images=images)
        res = motion_clips.resolve_chapter_motion(
            ch, manifest, self.motion_dir, 2)
        video = [s for s in res["segments"] if s["kind"] == "video"]
        stills = [s for s in res["segments"] if s["kind"] == "image"]
        self.assertEqual(res["mode"], "clips")
        video_s = sum(motion_clips._segment_duration(s) for s in video)
        self.assertAlmostEqual(video_s, 6.855, places=2)
        self.assertEqual(len(stills), 11)
        self.assertTrue(all(s["duration"] == 5.0 for s in stills[:-1]))
        self.assertAlmostEqual(stills[-1]["duration"], 3.421, places=2)
        total = sum(motion_clips._segment_duration(s)
                    for s in res["segments"])
        self.assertAlmostEqual(total, 60.276, places=2)

    def test_no_clips_fallback_uses_clip_seconds(self):
        ch = self._chapter(duration=12.0)
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 5, clip_seconds=2.5)
        self.assertEqual(res["mode"], "still")
        self.assertEqual([s["duration"] for s in res["segments"]],
                         [2.5, 2.5, 2.5, 2.5, 2.0])
        # الافتراضي (clips) يبقى 5ث كما كان قبل الإصلاح.
        res5 = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 5)
        self.assertEqual([s["duration"] for s in res5["segments"]],
                         [5.0, 7.0])

    def test_bad_clip_seconds_raises(self):
        ch = self._chapter(duration=12.0)
        for bad in (0, -1.0, "x"):
            with self.assertRaises(motion_clips.MotionError,
                                   msg="مقدار %r" % (bad,)):
                motion_clips.resolve_chapter_motion(
                    ch, self.manifest, self.motion_dir, 5,
                    clip_seconds=bad)

    def test_auto_match_by_scene_chapter_1(self):
        # توليدات L-C01 وL-C03 تحملان scene "chapter 1" — تطابقان
        # الفصل 1؛ الأول طبيعيًا L-C01 يغطي المدة وحده (5.0 ث).
        ch = self._chapter(duration=5.0)
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 1)
        self.assertEqual(res["mode"], "clips")
        self.assertEqual(len(res["segments"]), 1)
        seg = res["segments"][0]
        self.assertEqual(seg["kind"], "video")
        self.assertTrue(seg["src"].endswith("L-C01-a.mp4"))
        self.assertEqual(seg["out"], 5.0)

    def test_auto_match_chapter_2_uses_its_own_scene(self):
        # الفصل 2 تطابقه توليدات scene "chapter 2" فقط — لا توليدات
        # "chapter 1" (L-C01/L-C03) تدخل فيه.
        ch = self._chapter(duration=4.413)
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 2)
        self.assertEqual(res["mode"], "clips")
        self.assertEqual(len(res["segments"]), 1)
        self.assertTrue(
            res["segments"][0]["src"].endswith("L-C02-a.mp4"))
        self.assertFalse(any("L-C01" in s.get("src", "")
                             or "L-C03" in s.get("src", "")
                             for s in res["segments"]))

    def test_auto_match_misses_when_no_scene(self):
        # لا توليد يحمل scene "chapter 3" — رجوع لصورة ثابتة.
        ch = self._chapter(duration=5.0)
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 3)
        self.assertEqual(res["mode"], "still")
        self.assertTrue(all(s["kind"] == "image"
                            for s in res["segments"]))

    def test_unknown_explicit_clip_is_skipped_with_warning(self):
        ch = self._chapter(duration=5.0,
                           motion_clips_ids=["L-C99"])
        res = motion_clips.resolve_chapter_motion(
            ch, self.manifest, self.motion_dir, 1)
        self.assertEqual(res["mode"], "still")
        self.assertTrue(any("غير موجود" in w for w in res["warnings"]))


class TestExtractLastFrame(unittest.TestCase):
    def test_missing_video_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(motion_clips.MotionError):
                motion_clips.extract_last_frame(
                    os.path.join(tmp, "nope.mp4"),
                    os.path.join(tmp, "last.jpg"))

    def test_extracts_last_frame_when_ffmpeg_available(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg غير متاح في بيئة الاختبار")
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "v.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", "testsrc=size=320x240:rate=30:duration=2",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", video],
                check=True, timeout=60)
            out = os.path.join(tmp, "last.jpg")
            result = motion_clips.extract_last_frame(video, out)
            self.assertEqual(result, out)
            self.assertTrue(os.path.isfile(out))
            self.assertGreater(os.path.getsize(out), 0)


class TestRealManifest(unittest.TestCase):
    def test_real_manifest_shape_when_present(self):
        if not os.path.isfile(REAL_MANIFEST):
            self.skipTest("المانيفست الحقيقي غير موجود في هذه البيئة")
        manifest = motion_clips.load_motion_manifest(REAL_MANIFEST)
        self.assertEqual(len(manifest["clips"]), 81)
        self.assertEqual(len(manifest["generations"]), 133)
        self.assertEqual(manifest["generation_seconds"], 5.04)


if __name__ == "__main__":
    unittest.main()
