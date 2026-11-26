#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات التقطيع المشهدي لفيديو طويل إلى أجزاء (lib.scene_shorts).

تعمل بـ `python3 -m unittest tests.test_scene_shorts -v` من مجلد
studio. الوسائط تُولَّد محليًا بـffmpeg (بلا شبكة): فيديو طويل
180 ثانية بحدود مشاهد معروفة، وفيديو صامت. لا يُولَّد أي فيديو
حقيقي للقصة — هذه قدرة تقطيع فقط، بانتظار موافقة المستخدم.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import scene_shorts


def _run(cmd):
    subprocess.run(cmd, check=True, timeout=300,
                   capture_output=True, text=True)


def _make_video(path, seconds=180, width=1280, height=720):
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i",
          "testsrc=size=%dx%d:rate=15:duration=%d"
          % (width, height, seconds),
          "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
          "-t", str(seconds),
          "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-shortest", path])


# مشاهد فيديو 180ث: ستة مشاهد 30ث — تتجمع في 3 أجزاء 60ث.
SCENES_180 = [
    {"start": 0.0, "end": 30.0, "title": "البداية"},
    {"start": 30.0, "end": 60.0, "title": "اللقاء"},
    {"start": 60.0, "end": 90.0, "title": "السر"},
    {"start": 90.0, "end": 120.0, "title": "الانقلاب"},
    {"start": 120.0, "end": 150.0, "title": "العوض"},
    {"start": 150.0, "end": 180.0, "title": "الخاتمة"},
]

PHRASES_180 = [
    {"start": 1.0, "end": 4.0, "text": "فجأة طرق الباب"},
    {"start": 61.0, "end": 65.0, "text": "لكن كل شيء انقلب"},
    {"start": 121.0, "end": 125.0, "text": "وجاء العوض من الله"},
    {"start": 151.0, "end": 155.0, "text": "وهكذا انتهت القصة"},
]


class TestValidateScenes(unittest.TestCase):
    def test_sorted_and_titles_kept(self):
        scenes = scene_shorts.validate_scenes(
            [{"start": 50.0, "end": 70.0, "scene": "الثاني"},
             {"start": 0.0, "end": 50.0, "title": "الأول"}], 180.0)
        self.assertEqual([(s["start"], s["end"], s["title"])
                          for s in scenes],
                         [(0.0, 50.0, "الأول"), (50.0, 70.0, "الثاني")])

    def test_empty_scenes_raise(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.validate_scenes([], 180.0)

    def test_end_before_start_raises(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.validate_scenes(
                [{"start": 50.0, "end": 40.0}], 180.0)

    def test_negative_start_raises(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.validate_scenes(
                [{"start": -1.0, "end": 10.0}], 180.0)

    def test_overlapping_scenes_raise(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.validate_scenes(
                [{"start": 0.0, "end": 60.0},
                 {"start": 50.0, "end": 90.0}], 180.0)

    def test_scene_beyond_duration_raises(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.validate_scenes(
                [{"start": 0.0, "end": 200.0}], 180.0)


class TestFindGaps(unittest.TestCase):
    def test_full_coverage_no_gaps(self):
        self.assertEqual(
            scene_shorts.find_gaps(SCENES_180, 180.0), [])

    def test_gap_between_and_after_scenes(self):
        scenes = [{"start": 10.0, "end": 50.0},
                  {"start": 60.0, "end": 100.0}]
        self.assertEqual(scene_shorts.find_gaps(scenes, 120.0),
                         [(0.0, 10.0), (50.0, 60.0), (100.0, 120.0)])


class TestPlanParts(unittest.TestCase):
    def test_whole_scenes_only_40_to_60(self):
        plan = scene_shorts.plan_parts(SCENES_180, 180.0)
        parts = plan["parts"]
        # 0–60 (30+30)، 60–120 (30+30)، 120–180 (30+30).
        self.assertEqual([(p["start"], p["end"]) for p in parts],
                         [(0.0, 60.0), (60.0, 120.0), (120.0, 180.0)])
        for p in parts:
            self.assertEqual(p["status"], "مكتمل")
            self.assertGreaterEqual(p["duration"], 40.0)
            self.assertLessEqual(p["duration"], 60.0)
            # كل حد جزء حد مشهد.
            self.assertIn(p["start"], [s["start"] for s in SCENES_180])
            self.assertIn(p["end"], [s["end"] for s in SCENES_180])

    def test_part_scenes_listed(self):
        plan = scene_shorts.plan_parts(SCENES_180, 180.0)
        self.assertEqual(plan["parts"][0]["scenes"],
                         ["البداية", "اللقاء"])
        self.assertEqual(plan["parts"][2]["scenes"],
                         ["العوض", "الخاتمة"])

    def test_short_tail_marked_incomplete_not_dropped(self):
        scenes = [{"start": 0.0, "end": 50.0, "title": "أول"},
                  {"start": 50.0, "end": 70.0, "title": "ذيل"}]
        plan = scene_shorts.plan_parts(scenes, 70.0)
        self.assertEqual(len(plan["parts"]), 2)
        tail = plan["parts"][1]
        self.assertEqual(tail["status"], "غير مكتمل")
        self.assertEqual((tail["start"], tail["end"]), (50.0, 70.0))
        self.assertIn("أقصر من 40ث", tail["reason"])

    def test_short_part_merges_with_next_when_possible(self):
        # مشهد 20ث + مشهد 30ث = 50ث جزء واحد مكتمل.
        scenes = [{"start": 0.0, "end": 20.0, "title": "قصير"},
                  {"start": 20.0, "end": 50.0, "title": "تالٍ"}]
        plan = scene_shorts.plan_parts(scenes, 50.0)
        self.assertEqual(len(plan["parts"]), 1)
        self.assertEqual(plan["parts"][0]["status"], "مكتمل")
        self.assertEqual(plan["parts"][0]["scenes"], ["قصير", "تالٍ"])

    def test_oversized_single_scene_marked_incomplete(self):
        scenes = [{"start": 0.0, "end": 80.0, "title": "مشهد طويل"},
                  {"start": 80.0, "end": 130.0, "title": "تالٍ"}]
        plan = scene_shorts.plan_parts(scenes, 130.0)
        self.assertEqual(plan["parts"][0]["status"], "غير مكتمل")
        self.assertIn("أطول من 60ث", plan["parts"][0]["reason"])
        self.assertEqual(plan["parts"][1]["status"], "مكتمل")

    def test_hook_from_first_phrase(self):
        plan = scene_shorts.plan_parts(SCENES_180, 180.0,
                                        phrases=PHRASES_180)
        self.assertEqual(plan["parts"][0]["hook"], "فجأة طرق الباب")
        self.assertEqual(plan["parts"][1]["hook"], "لكن كل شيء انقلب")
        self.assertEqual(plan["parts"][2]["hook"], "وجاء العوض من الله")

    def test_hook_word_raises_score(self):
        plain = scene_shorts.plan_parts(
            [{"start": 0.0, "end": 50.0}], 50.0,
            phrases=[{"start": 1.0, "end": 4.0, "text": "كان يا ما كان"}])
        hooked = scene_shorts.plan_parts(
            [{"start": 0.0, "end": 50.0}], 50.0,
            phrases=[{"start": 1.0, "end": 4.0, "text": "فجأة طرق الباب"}])
        self.assertGreater(hooked["parts"][0]["score"],
                           plain["parts"][0]["score"])
        self.assertIn("هوك في البداية", hooked["parts"][0]["reason"])

    def test_deterministic_same_inputs(self):
        first = scene_shorts.plan_parts(SCENES_180, 180.0,
                                         phrases=PHRASES_180)
        second = scene_shorts.plan_parts(SCENES_180, 180.0,
                                          phrases=PHRASES_180)
        self.assertEqual(first, second)

    def test_bad_length_bounds_raise(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.plan_parts(SCENES_180, 180.0,
                                    min_len=60.0, max_len=40.0)


class TestCutSceneShortsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="scene-shorts-")
        cls.video = os.path.join(cls.tmp, "long.mp4")
        _make_video(cls.video)

    def test_cuts_complete_parts_vertical(self):
        out = os.path.join(self.tmp, "out")
        results = scene_shorts.cut_scene_shorts(
            self.video, SCENES_180, out, phrases=PHRASES_180)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r["status"], "مكتمل")
            self.assertTrue(os.path.isfile(r["output"]))
            info = check_lib.probe(r["output"])
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            self.assertGreaterEqual(info["duration"], 39.0)
            self.assertLessEqual(info["duration"], 61.0)
            self.assertGreater(r["score"], 0.0)
            self.assertTrue(r["hook"])
        self.assertEqual(
            [os.path.basename(r["output"]) for r in results],
            ["scene-part-01.mp4", "scene-part-02.mp4",
             "scene-part-03.mp4"])

    def test_captions_ass_bottom_only(self):
        out = os.path.join(self.tmp, "out-cap")
        results = scene_shorts.cut_scene_shorts(
            self.video, SCENES_180, out, phrases=PHRASES_180)
        ass_path = results[0]["captions"]
        self.assertIsNotNone(ass_path)
        with open(ass_path, encoding="utf-8") as f:
            text = f.read()
        # عبارتا الجزء الأول فقط (0–60ث)، مُزاحتان؛ وعبارة 61ث خارجها.
        self.assertIn("فجأة طرق الباب", text)
        self.assertNotIn("لكن كل شيء انقلب", text)
        # محاذاة 2 = أسفل الشاشة فقط (نمط whisper_captions).
        self.assertIn(",2,40,40,64,1", text)

    def test_incomplete_part_not_cut_but_reported(self):
        scenes = [{"start": 0.0, "end": 50.0, "title": "أول"},
                  {"start": 50.0, "end": 70.0, "title": "ذيل"}]
        out = os.path.join(self.tmp, "out-tail")
        results = scene_shorts.cut_scene_shorts(self.video, scenes, out)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]["status"], "غير مكتمل")
        self.assertIsNone(results[1]["output"])
        self.assertIsNone(results[1]["captions"])
        self.assertTrue(os.path.isfile(results[0]["output"]))

    def test_cut_is_deterministic(self):
        out1 = os.path.join(self.tmp, "out-a")
        out2 = os.path.join(self.tmp, "out-b")
        r1 = scene_shorts.cut_scene_shorts(self.video, SCENES_180, out1)
        r2 = scene_shorts.cut_scene_shorts(self.video, SCENES_180, out2)
        self.assertEqual(
            [(r["start"], r["end"], r["score"]) for r in r1],
            [(r["start"], r["end"], r["score"]) for r in r2])

    def test_missing_file_raises_arabic_error(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.cut_scene_shorts(
                os.path.join(self.tmp, "nope.mp4"), SCENES_180,
                os.path.join(self.tmp, "out-x"))

    def test_empty_scenes_raise(self):
        with self.assertRaises(scene_shorts.SceneShortsError):
            scene_shorts.cut_scene_shorts(
                self.video, [], os.path.join(self.tmp, "out-y"))


class TestComparisonReport(unittest.TestCase):
    def test_report_full_vs_parts(self):
        plan = scene_shorts.plan_parts(SCENES_180, 180.0,
                                        phrases=PHRASES_180)
        report = scene_shorts.format_comparison_report(
            plan["parts"], "long.mp4", 180.0,
            full_hook="فجأة طرق الباب")
        self.assertIn("الفيديو الكامل: 180.0 ث", report)
        self.assertIn("الهوك: فجأة طرق الباب", report)
        self.assertIn("عدد الأجزاء: 3 (3 مكتمل، 0 غير مكتمل)", report)
        self.assertIn("فجأة طرق الباب", report)
        self.assertIn("التغطية: 180.0 ث من 180.0 ث (100%)", report)

    def test_report_marks_incomplete_and_gaps(self):
        scenes = [{"start": 10.0, "end": 60.0, "title": "أول"},
                  {"start": 60.0, "end": 80.0, "title": "ذيل"}]
        plan = scene_shorts.plan_parts(scenes, 100.0)
        self.assertEqual(plan["gaps"], [(0.0, 10.0), (80.0, 100.0)])
        report = scene_shorts.format_comparison_report(
            plan["parts"], "long.mp4", 100.0)
        self.assertIn("1 غير مكتمل", report)
        self.assertIn("التغطية: 70.0 ث من 100.0 ث (70%)", report)

    def test_report_empty_parts(self):
        report = scene_shorts.format_comparison_report(
            [], "long.mp4", 180.0)
        self.assertIn("لا أجزاء", report)


if __name__ == "__main__":
    unittest.main()
