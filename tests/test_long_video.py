#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الفيديو الطويل (lib.long_video) + الصورة الأفقية.

تعمل بـ `python3 -m unittest discover -s tests -v`.
الوسائط التجريبية صغيرة وتُولَّد بـffmpeg محليًا (بلا شبكة).
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import long_narration
from lib import long_video
from lib import motion_clips
from lib import thumbnail
from lib.stage_cache import StageCache

ASS_FIXTURE = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Naskh Arabic,52,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,40,40,64,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,في نص الليل،
Dialogue: 0,0:00:01.50,0:00:02.00,Default,,0,0,0,,طردت الحماة زوجة ابنها.
"""


def _make_wav(path, seconds=2):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=%d" % seconds,
                    "-c:a", "pcm_s16le", path], check=True, timeout=60)


def _make_jpg(path, width=1280, height=720):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=%dx%d:rate=30:duration=1"
                    % (width, height),
                    "-frames:v", "1", path], check=True, timeout=60)


def _make_video(path, seconds=2, width=1280, height=720):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=%dx%d:rate=30:duration=%d"
                    % (width, height, seconds),
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=%d" % seconds,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", path], check=True, timeout=60)


def _fake_chapter(tmp, name, duration=2.0):
    wav = os.path.join(tmp, name + ".wav")
    _make_wav(wav, seconds=int(duration))
    img = os.path.join(tmp, name + ".jpg")
    _make_jpg(img)
    return {"title": name, "moral": "عبرة " + name, "narration": wav,
            "duration": duration, "images": [img],
            "phrases": [{"start": 0.0, "end": duration, "text": "نص تجريبي",
                         "words": long_video.estimate_word_times(
                             "نص تجريبي", 0.0, duration)}]}


class TestMmss(unittest.TestCase):
    def test_values(self):
        self.assertEqual(long_video.mmss(0), "00:00")
        self.assertEqual(long_video.mmss(65), "01:05")
        self.assertEqual(long_video.mmss(600), "10:00")
        self.assertEqual(long_video.mmss(3661), "1:01:01")


class TestEstimateWordTimes(unittest.TestCase):
    def test_covers_range_sorted(self):
        words = long_video.estimate_word_times("ألف باء جيم", 1.0, 4.0)
        self.assertEqual(len(words), 3)
        self.assertEqual(words[0]["start"], 1.0)
        self.assertEqual(words[-1]["end"], 4.0)
        for a, b in zip(words, words[1:]):
            self.assertLessEqual(a["end"], b["start"] + 1e-9)

    def test_single_word(self):
        words = long_video.estimate_word_times("واحدة", 2.0, 3.0)
        self.assertEqual(words, [{"w": "واحدة", "start": 2.0, "end": 3.0}])

    def test_empty(self):
        self.assertEqual(long_video.estimate_word_times("", 0, 1), [])


class TestParseAss(unittest.TestCase):
    def test_phrases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.ass")
            with open(path, "w", encoding="utf-8") as f:
                f.write(ASS_FIXTURE)
            phrases = long_video.parse_ass(path)
            self.assertEqual(len(phrases), 2)
            self.assertEqual(phrases[0]["text"], "في نص الليل،")
            self.assertEqual(phrases[0]["start"], 0.0)
            self.assertEqual(phrases[0]["end"], 1.5)
            self.assertEqual(phrases[1]["start"], 1.5)
            self.assertEqual(phrases[1]["end"], 2.0)


class TestBuildProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ch1 = _fake_chapter(self.tmp.name, "القصة الأولى", 2.0)
        self.ch2 = _fake_chapter(self.tmp.name, "القصة الثانية", 2.0)
        self.intro_wav = os.path.join(self.tmp.name, "intro.wav")
        _make_wav(self.intro_wav, seconds=2)
        self.spec = {
            "title": "5 قصص مؤثرة",
            "hook": "5 قصص هزّت الأسبوع ده",
            "intro": {"text": "5 قصص هزّت الأسبوع ده",
                      "narration": self.intro_wav, "duration": 2.0},
            "outro": {"text": "اشترك في القناة",
                      "narration": self.intro_wav, "duration": 2.0},
            "chapters": [self.ch1, self.ch2], "music": None,
            "width": 1280, "height": 720, "fps": 30}

    def tearDown(self):
        self.tmp.cleanup()

    def test_structure_and_timing(self):
        project, meta = long_video.build_project(self.spec)
        self.assertEqual((project["width"], project["height"]), (1280, 720))
        # المجموع = مقدمة 3 + (3+2) + (3+2) + خاتمة 3 = 16 ثانية
        self.assertAlmostEqual(meta["total_duration"], 16.0)
        self.assertEqual(meta["chapters"][0]["start"], 3.0)
        self.assertEqual(meta["chapters"][1]["start"], 8.0)
        self.assertEqual(meta["outro"]["start"], 13.0)
        visuals = [t for t in project["tracks"]
                   if t["type"] in ("image", "video")]
        visuals.sort(key=lambda t: t["start"])
        self.assertEqual(visuals[0]["start"], 0.0)
        cursor = 0.0
        for v in visuals:
            self.assertAlmostEqual(v["start"], cursor, places=2)
            cursor += v["duration"]
        self.assertAlmostEqual(cursor, 16.0, places=2)
        # عبارات بمستوى الكلمة
        worded = [t for t in project["tracks"]
                  if t["type"] == "text" and t.get("word_highlight")]
        self.assertEqual(len(worded), 2)
        # لا بطاقات اقتباس في المشروع أبدًا
        blob = json.dumps(project, ensure_ascii=False)
        self.assertNotIn("cards", blob)
        self.assertNotIn("بطاقة", blob)
        # قاعدة دائمة 2026-11-22: لا نص أعلى الشاشة أبدًا — هوك
        # المقدمة أسفل فوق الكابشن ("above")، وبطاقات العناوين
        # والخاتمة في المنتصف (بطاقات لا تراكب)، وكل العبارات أسفل.
        texts = [t for t in project["tracks"] if t["type"] == "text"]
        self.assertFalse(any(t.get("position") == "top" for t in texts))
        intro_hook = [t for t in texts if t["start"] == 0.0]
        self.assertEqual(len(intro_hook), 1)
        self.assertEqual(intro_hook[0]["position"], "above")

    def test_music_track_is_background(self):
        spec = dict(self.spec)
        spec["music"] = self.intro_wav
        project, meta = long_video.build_project(spec)
        music = [t for t in project["tracks"]
                 if t.get("role") == "background"]
        self.assertEqual(len(music), 1)
        self.assertEqual(music[0]["duration"], 16.0)

    def test_empty_chapters_raises(self):
        spec = dict(self.spec)
        spec["chapters"] = []
        with self.assertRaises(long_video.LongVideoError):
            long_video.build_project(spec)

    def test_missing_narration_raises(self):
        ch = dict(self.ch1)
        ch["narration"] = "/nonexistent.wav"
        spec = dict(self.spec)
        spec["chapters"] = [ch]
        with self.assertRaises(long_video.LongVideoError):
            long_video.build_project(spec)

    def test_timestamps_and_description(self):
        _, meta = long_video.build_project(self.spec)
        ts = long_video.format_timestamps(meta)
        self.assertIn("00:00 المقدمة", ts)
        self.assertIn("00:03 الفصل 1: القصة الأولى", ts)
        self.assertIn("00:08 الفصل 2: القصة الثانية", ts)
        self.assertIn("00:13 الخاتمة", ts)
        desc = long_video.build_description(
            meta, self.spec["hook"], "اشترك في القناة",
            "https://www.facebook.com/1048148471706586")
        self.assertIn("5 قصص هزّت الأسبوع ده", desc)
        self.assertIn("القصة الأولى", desc)
        self.assertIn("عبرة القصة الأولى", desc)
        self.assertIn("اشترك في القناة", desc)
        self.assertIn("#قصص_وعبر", desc)


class TestChapterFromManifest(unittest.TestCase):
    def test_real_word_timings(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = os.path.join(tmp, "assets")
            os.makedirs(os.path.join(assets, "audio"))
            os.makedirs(os.path.join(assets, "images"))
            _make_wav(os.path.join(assets, "audio", "narration-full.wav"),
                      seconds=2)
            _make_jpg(os.path.join(assets, "images", "img1.jpg"))
            _make_jpg(os.path.join(assets, "images", "img2.jpg"))
            captions = [
                {"word": "كلمة", "startMs": 0, "endMs": 400},
                {"word": "أولى", "startMs": 400, "endMs": 1000,
                 "pageBreakAfter": True},
                {"word": "كلمة", "startMs": 1000, "endMs": 1500},
                {"word": "ثانية", "startMs": 1500, "endMs": 2000,
                 "pageBreakAfter": True},
            ]
            with open(os.path.join(assets, "captions.json"), "w",
                      encoding="utf-8") as f:
                json.dump(captions, f, ensure_ascii=False)
            manifest = {
                "project": "test", "hook": "هوك تجريبي",
                "sequence": ["img1.jpg", "img2.jpg"],
                "narration_duration": 2.0,
                "phrases": [
                    {"start": 0.0, "end": 1.0, "text": "كلمة أولى"},
                    {"start": 1.0, "end": 2.0, "text": "كلمة ثانية"}]}
            ch = long_video.chapter_from_manifest(manifest, assets)
            self.assertEqual(ch["title"], "هوك تجريبي")
            self.assertEqual(ch["duration"], 2.0)
            self.assertEqual(len(ch["phrases"]), 2)
            words = ch["phrases"][0]["words"]
            self.assertEqual(words[0]["w"], "كلمة")
            self.assertEqual(words[0]["start"], 0.0)
            self.assertEqual(words[1]["end"], 1.0)


class TestLoadChapterDir(unittest.TestCase):
    def _write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_narration_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            ch_dir = os.path.join(tmp, "ch")
            os.makedirs(os.path.join(ch_dir, "images"))
            self._write(os.path.join(ch_dir, "title.txt"), "حماتي")
            self._write(os.path.join(ch_dir, "moral.txt"), "العفو عند المقدرة")
            _make_wav(os.path.join(ch_dir, "narration.wav"), seconds=2)
            self._write(os.path.join(ch_dir, "phrases.ass"), ASS_FIXTURE)
            _make_jpg(os.path.join(ch_dir, "images", "a.jpg"))
            _make_jpg(os.path.join(ch_dir, "images", "b.jpg"))
            ch = long_video.load_chapter_dir(ch_dir, work_dir=tmp)
            self.assertEqual(ch["title"], "حماتي")
            self.assertEqual(ch["moral"], "العفو عند المقدرة")
            self.assertEqual(ch["duration"], 2.0)
            self.assertEqual(len(ch["images"]), 2)
            self.assertEqual(len(ch["phrases"]), 2)
            self.assertEqual(len(ch["phrases"][0]["words"]), 3)

    def test_scene_variant_merges_with_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            ch_dir = os.path.join(tmp, "ch")
            os.makedirs(ch_dir)
            self._write(os.path.join(ch_dir, "title.txt"), "النجار الأمين")
            _make_wav(os.path.join(ch_dir, "scene1.wav"), seconds=2)
            _make_wav(os.path.join(ch_dir, "scene2.wav"), seconds=2)
            self._write(os.path.join(ch_dir, "scene1.ass"), ASS_FIXTURE)
            self._write(os.path.join(ch_dir, "scene2.ass"), ASS_FIXTURE)
            _make_jpg(os.path.join(ch_dir, "cover.jpg"))
            ch = long_video.load_chapter_dir(ch_dir, work_dir=tmp)
            # 2 + 0.35 + 2 = 4.35 ثانية
            self.assertAlmostEqual(ch["duration"], 4.35, places=1)
            self.assertEqual(len(ch["phrases"]), 4)
            # عبارات المشهد الثاني مزاحة بمقدار 2.35 ثانية
            self.assertAlmostEqual(ch["phrases"][2]["start"], 2.35,
                                   places=1)
            self.assertAlmostEqual(ch["phrases"][3]["end"], 4.35, places=1)

    def test_missing_title_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(long_video.LongVideoError):
                long_video.load_chapter_dir(tmp)


class TestThumbnailHorizontal(unittest.TestCase):
    def test_long_thumbnail_is_1280x720(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "v.mp4")
            _make_video(video, seconds=2)
            out = os.path.join(tmp, "thumb.jpg")
            thumbnail.make_long_thumbnail(video, "هوك صادم للتجربة", out)
            self.assertEqual(thumbnail.probe_image(out), (1280, 720))

    def test_default_thumbnail_stays_vertical(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "v.mp4")
            _make_video(video, seconds=2)
            out = os.path.join(tmp, "thumb.jpg")
            thumbnail.make_thumbnail(video, "هوك صادم للتجربة", out)
            self.assertEqual(thumbnail.probe_image(out), (720, 1280))


class TestDuckingWiring(unittest.TestCase):
    def test_music_produces_sidechaincompress(self):
        editor = os.path.expanduser("~/workspace/headless-editor/editor.py")
        if not os.path.isfile(editor):
            self.skipTest("headless-editor غير متاح")
        with tempfile.TemporaryDirectory() as tmp:
            ch = _fake_chapter(tmp, "قصة", 2.0)
            music = os.path.join(tmp, "music.wav")
            _make_wav(music, seconds=16)
            intro_wav = os.path.join(tmp, "intro.wav")
            _make_wav(intro_wav, seconds=2)
            spec = {
                "title": "اختبار", "hook": "هوك",
                "intro": {"text": "هوك", "narration": intro_wav,
                          "duration": 2.0},
                "outro": {"text": "اشترك", "narration": intro_wav,
                          "duration": 2.0},
                "chapters": [ch], "music": music,
                "width": 1280, "height": 720, "fps": 30}
            project, _ = long_video.build_project(spec)
            proj_path = os.path.join(tmp, "project.json")
            with open(proj_path, "w", encoding="utf-8") as f:
                json.dump(project, f, ensure_ascii=False)
            proc = subprocess.run(
                [sys.executable, editor, "render", proj_path,
                 "-o", os.path.join(tmp, "o.mp4"), "--dry-run"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("sidechaincompress", proc.stdout)


class TestMotionModes(unittest.TestCase):
    """أوضاع الحركة في build_project (v0.1.44 + الموجة الأولى).

    الافتراضي الجديد kenburns (المسار السريع بلا GPU)؛ وclips
    الصريح يعيد السلوك السابق بلا Ken Burns؛ وstill صور ثابتة
    بلا أي حركة.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ch1 = _fake_chapter(self.tmp.name, "القصة الأولى", 2.0)
        self.ch2 = _fake_chapter(self.tmp.name, "القصة الثانية", 2.0)
        self.intro_wav = os.path.join(self.tmp.name, "intro.wav")
        _make_wav(self.intro_wav, seconds=2)
        self.video = os.path.join(self.tmp.name, "clip.mp4")
        _make_video(self.video, seconds=2)

    def tearDown(self):
        self.tmp.cleanup()

    def _spec(self, chapters=None, motion=None):
        spec = {
            "title": "5 قصص مؤثرة",
            "hook": "5 قصص هزّت الأسبوع ده",
            "intro": {"text": "5 قصص هزّت الأسبوع ده",
                      "narration": self.intro_wav, "duration": 2.0},
            "outro": {"text": "اشترك في القناة",
                      "narration": self.intro_wav, "duration": 2.0},
            "chapters": chapters or [self.ch1, self.ch2], "music": None,
            "width": 1280, "height": 720, "fps": 30}
        if motion is not None:
            spec["motion"] = motion
        return spec

    def _image_tracks(self, project):
        return [t for t in project["tracks"] if t["type"] == "image"]

    def test_default_mode_is_kenburns(self):
        # الموجة الأولى (الطلب 1): الافتراضي الجديد kenburns —
        # المسار السريع بلا GPU أولًا، وclips خيار صريح فقط.
        self.assertEqual(long_video.FAST_MOTION_DEFAULT, "kenburns")
        project, meta = long_video.build_project(self._spec())
        self.assertEqual(meta["motion"], "kenburns")
        self.assertTrue(any("ken_burns" in t
                            for t in self._image_tracks(project)),
                        "الافتراضي kenburns يجب أن يحمل ken_burns")
        self.assertEqual(self._image_tracks(project)[0]["ken_burns"],
                         "in")

    def test_still_mode_has_no_ken_burns(self):
        project, meta = long_video.build_project(
            self._spec(motion="still"))
        self.assertEqual(meta["motion"], "still")
        self.assertFalse(any("ken_burns" in t
                             for t in project["tracks"]))

    def test_kenburns_mode_restores_old_behavior(self):
        # kenburns هو الافتراضي الآن؛ والصريح يطابقه تمامًا.
        ch = _fake_chapter(self.tmp.name, "قصة طويلة", 12.0)
        project, meta = long_video.build_project(
            self._spec(chapters=[ch], motion="kenburns"))
        self.assertEqual(meta["motion"], "kenburns")
        images = self._image_tracks(project)
        # مقدمة in + بطاقة عنوان in + محتوى in/out + خاتمة out
        self.assertEqual(images[0]["ken_burns"], "in")
        self.assertEqual(images[1]["ken_burns"], "in")
        content = images[2:-1]
        self.assertEqual([t["ken_burns"] for t in content],
                         ["in", "out"])
        self.assertEqual(images[-1]["ken_burns"], "out")

    def test_clips_with_motion_segments(self):
        ch = dict(self.ch1)
        ch["motion_segments"] = [
            {"kind": "video", "src": self.video, "in": 0.0, "out": 1.0},
            {"kind": "image", "src": self.ch1["images"][0],
             "duration": 1.0}]
        project, meta = long_video.build_project(
            self._spec(chapters=[ch], motion="clips"))
        videos = [t for t in project["tracks"] if t["type"] == "video"]
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["volume"], 0)
        self.assertEqual(videos[0]["in"], 0.0)
        self.assertEqual(videos[0]["out"], 1.0)
        self.assertEqual(videos[0]["transition_in"], "none")
        self.assertFalse(any("ken_burns" in t
                             for t in project["tracks"]))
        self.assertEqual(meta["chapters"][0]["motion"]["mode"], "clips")

    def test_clips_without_segments_falls_back_to_still_images(self):
        project, meta = long_video.build_project(
            self._spec(chapters=[self.ch1], motion="clips"))
        content = [t for t in project["tracks"]
                   if t["type"] == "image" and t["start"] >= 6.0]
        self.assertTrue(content)
        self.assertFalse(any("ken_burns" in t for t in content))
        self.assertEqual(meta["chapters"][0]["motion"]["mode"], "clips")

    def test_youtube_long_uses_fast_cut_still_images(self):
        # v0.1.45: الصور الاحتياطية 2.5 ثانية بدل 5، وبلا Ken Burns.
        ch = _fake_chapter(self.tmp.name, "قصة طويلة", 12.0)
        project, meta = long_video.build_project(
            self._spec(chapters=[ch], motion="youtube-long"))
        self.assertEqual(meta["motion"], "youtube-long")
        images = self._image_tracks(project)
        content = images[2:-1]
        self.assertEqual([t["duration"] for t in content],
                         [2.5, 2.5, 2.5, 2.5, 2.0])
        self.assertFalse(any("ken_burns" in t
                             for t in project["tracks"]),
                         "youtube-long يجب ألا يحمل أي ken_burns")
        self.assertEqual([t["transition_in"] for t in content],
                         ["none"] * 5)

    def test_youtube_long_with_motion_segments(self):
        # v0.1.45: مقاطع الحركة تُحلّ في youtube-long كما في clips.
        ch = dict(self.ch1)
        ch["motion_segments"] = [
            {"kind": "video", "src": self.video, "in": 0.0, "out": 1.0},
            {"kind": "image", "src": self.ch1["images"][0],
             "duration": 1.0}]
        project, meta = long_video.build_project(
            self._spec(chapters=[ch], motion="youtube-long"))
        videos = [t for t in project["tracks"] if t["type"] == "video"]
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["volume"], 0)
        self.assertFalse(any("ken_burns" in t
                             for t in project["tracks"]))
        self.assertEqual(meta["chapters"][0]["motion"]["mode"],
                         "youtube-long")

    def test_clips_still_image_duration_unchanged(self):
        # حارس: وضع clips الصريح ما زال 5 ثوانٍ للصورة (v0.1.45 لم
        # يغيّر إلا youtube-long) — والافتراضي الجديد kenburns
        # يستخدم المقدار نفسه للصور.
        ch = _fake_chapter(self.tmp.name, "قصة طويلة", 12.0)
        project, _meta = long_video.build_project(
            self._spec(chapters=[ch], motion="clips"))
        images = self._image_tracks(project)
        content = images[2:-1]
        self.assertEqual([t["duration"] for t in content], [5.0, 7.0])

    def test_unknown_motion_raises(self):
        with self.assertRaises(long_video.LongVideoError):
            long_video.build_project(self._spec(motion="spin"))

    def test_segments_duration_mismatch_raises(self):
        ch = dict(self.ch1)
        ch["motion_segments"] = [
            {"kind": "video", "src": self.video, "in": 0.0, "out": 1.0}]
        with self.assertRaises(long_video.LongVideoError):
            long_video.build_project(self._spec(chapters=[ch]))

    def test_unresolved_freeze_raises(self):
        ch = dict(self.ch1)
        ch["motion_segments"] = [
            {"kind": "freeze", "src": self.video, "duration": 2.0}]
        with self.assertRaises(long_video.LongVideoError):
            long_video.build_project(self._spec(chapters=[ch]))

    def test_meta_carries_motion_warnings_and_chapter_modes(self):
        ch = dict(self.ch1)
        ch["motion_report"] = {"mode": "still",
                               "warnings": ["تحذير تجريبي"]}
        _, meta = long_video.build_project(self._spec(chapters=[ch]))
        self.assertIsInstance(meta["motion_warnings"], list)
        self.assertIn("تحذير تجريبي", meta["motion_warnings"])
        self.assertEqual(meta["chapters"][0]["motion"]["mode"], "still")
        self.assertEqual(meta["chapters"][0]["motion"]["warnings"],
                         ["تحذير تجريبي"])

    def test_cli_long_video_help_lists_motion_flag(self):
        # نمط test_version_help_round8: فحص أعلام argparse عبر --help.
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "studio.py", "long-video", "--help"],
            cwd=studio_dir, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--motion", proc.stdout)
        self.assertIn("clips", proc.stdout)
        self.assertIn("youtube-long", proc.stdout)
        self.assertIn("--motion-manifest", proc.stdout)


class TestFastDraftNote(unittest.TestCase):
    """رسالة المسار السريع — نص حرفي من خطة الموجة الأولى."""

    def test_note_text_is_exact(self):
        self.assertEqual(
            long_video.FAST_DRAFT_GPU_NOTE,
            "الفيديو السريع جاهز الآن؛ الحركة المولّدة تحتاج حصة GPU "
            "ووقتًا — أعد التشغيل بـ`--motion clips` لاحقًا")
        self.assertEqual(long_video.FAST_MOTION_DEFAULT, "kenburns")


class TestFastDraft(unittest.TestCase):
    """المسودة السريعة build_fast_draft (الموجة الأولى، الطلب 1)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.intro_wav = os.path.join(self.tmp.name, "intro.wav")
        _make_wav(self.intro_wav, seconds=2)
        self.ch1 = _fake_chapter(self.tmp.name, "القصة الأولى", 2.0)

    def tearDown(self):
        self.tmp.cleanup()

    def _spec(self, chapters=None, music=None, width=1280, height=720,
              motion=None):
        spec = {
            "title": "5 قصص مؤثرة",
            "hook": "5 قصص هزّت الأسبوع ده",
            "intro": {"text": "5 قصص هزّت الأسبوع ده",
                      "narration": self.intro_wav, "duration": 2.0},
            "outro": {"text": "اشترك في القناة",
                      "narration": self.intro_wav, "duration": 2.0},
            "chapters": chapters or [self.ch1], "music": music,
            "width": width, "height": height, "fps": 30}
        if motion is not None:
            spec["motion"] = motion
        return spec

    def _load_project_json(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_json_output_has_report_and_note(self):
        ch2 = _fake_chapter(self.tmp.name, "القصة الثانية", 2.0)
        spec = self._spec(chapters=[self.ch1, ch2])
        out = os.path.join(self.tmp.name, "draft.json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = long_video.build_fast_draft(spec, out)
        self.assertEqual(set(result), {"output", "duration", "report"})
        self.assertEqual(result["output"], os.path.abspath(out))
        # المجموع = مقدمة 3 + (3+2) + (3+2) + خاتمة 3 = 16 ثانية
        self.assertAlmostEqual(result["duration"], 16.0)
        report = result["report"]
        self.assertEqual(report["motion"], "kenburns")
        self.assertEqual(report["note"], long_video.FAST_DRAFT_GPU_NOTE)
        self.assertIn(long_video.FAST_DRAFT_GPU_NOTE, buf.getvalue())
        self.assertFalse(report["cache_hit"])
        self.assertFalse(report["music_dropped"])
        self.assertEqual(report["format"], "project-json")
        self.assertTrue(os.path.isfile(out))
        project = self._load_project_json(out)
        self.assertTrue(any("ken_burns" in t
                            for t in project["tracks"]))
        # spec الممرَّرة لا تُعدَّل (بلا motion مفروض عليها)
        self.assertNotIn("motion", spec)

    def test_explicit_clips_still_works(self):
        # clips الصريح ما زال يعمل كما كان — بلا Ken Burns.
        project, meta = long_video.build_project(
            self._spec(motion="clips"))
        self.assertEqual(meta["motion"], "clips")
        self.assertFalse(any("ken_burns" in t
                             for t in project["tracks"]))

    def test_drops_music(self):
        # المسودة السريعة بلا موسيقى أبدًا — تُسقَط وتُوثَّق.
        spec = self._spec(music=self.intro_wav)
        out = os.path.join(self.tmp.name, "draft.json")
        result = long_video.build_fast_draft(spec, out)
        self.assertTrue(result["report"]["music_dropped"])
        project = self._load_project_json(out)
        self.assertFalse(any(t.get("role") == "background"
                             for t in project["tracks"]))

    def test_captions_bottom_only(self):
        # الكتابة المتزامنة أسفل الصورة فقط — محفوظة في المسار
        # السريع: عبارات word_highlight كلها bottom، ولا top أبدًا.
        out = os.path.join(self.tmp.name, "draft.json")
        long_video.build_fast_draft(self._spec(), out)
        project = self._load_project_json(out)
        texts = [t for t in project["tracks"] if t["type"] == "text"]
        self.assertTrue(texts)
        self.assertFalse(any(t.get("position") == "top" for t in texts))
        worded = [t for t in texts if t.get("word_highlight")]
        self.assertTrue(worded)
        self.assertTrue(all(t["position"] == "bottom" for t in worded))
        self.assertTrue(all(t.get("words") for t in worded))

    def test_text_chapter_synthesizes_piper(self):
        # فصل نصي بلا سرد جاهز: يُركَّب بـPiper (الراوي الرجل)
        # وتُبنى عباراته بتوقيتات الجمل.
        if not os.path.isfile(long_narration.PIPER_BIN) or \
                not os.path.isfile(long_narration.PIPER_MODEL):
            self.skipTest("Piper غير متاح")
        img = self.ch1["images"][0]
        spec = {
            "title": "قصة نصية", "hook": "هوك تجريبي قصير",
            "intro": {"text": "هوك تجريبي قصير"},
            "outro": {"text": "اشترك في القناة"},
            "chapters": [{"title": "قصة نصية",
                          "text": "في يوم من الأيام، وجد رجل أمين "
                                  "حقيبة. أعادها لصاحبها.",
                          "images": [img], "moral": "الأمانة"}],
            "music": None, "width": 640, "height": 360, "fps": 30}
        out = os.path.join(self.tmp.name, "draft.json")
        result = long_video.build_fast_draft(
            spec, out, work_dir=os.path.join(self.tmp.name, "work"))
        self.assertGreater(result["duration"], 0)
        self.assertEqual(result["report"]["voice"], "piper")
        project = self._load_project_json(out)
        audios = [t for t in project["tracks"] if t["type"] == "audio"]
        self.assertTrue(audios)
        for a in audios:
            self.assertTrue(os.path.isfile(a["src"]),
                            "سرد المسودة غير موجود: %s" % a["src"])
        worded = [t for t in project["tracks"]
                  if t["type"] == "text" and t.get("word_highlight")]
        self.assertTrue(worded)
        self.assertTrue(all(t["position"] == "bottom" for t in worded))

    def test_renders_real_mp4_with_kenburns(self):
        # ريندر حقيقي عبر headless-editor (بلا GPU): فيديو MP4
        # بصور Ken Burns وكتابة متزامنة أسفل الصورة فقط.
        if not os.path.isfile(long_video.DEFAULT_HEADLESS_EDITOR):
            self.skipTest("headless-editor غير متاح")
        spec = self._spec(width=640, height=360)
        out = os.path.join(self.tmp.name, "draft.mp4")
        result = long_video.build_fast_draft(spec, out)
        self.assertEqual(result["report"]["format"], "video")
        self.assertTrue(os.path.isfile(out))
        self.assertGreater(os.path.getsize(out), 0)
        self.assertAlmostEqual(
            long_narration.probe_duration(out), 11.0, delta=0.6)
        self.assertTrue(os.path.isfile(result["report"]["project_json"]))
        project = self._load_project_json(
            result["report"]["project_json"])
        images = [t for t in project["tracks"] if t["type"] == "image"]
        self.assertTrue(any("ken_burns" in t for t in images))
        self.assertFalse(any(t.get("role") == "background"
                             for t in project["tracks"]))

    def test_cache_hit_reuses_video_without_rerender(self):
        # إصابة التخزين تعيد استخدام الفيديو بلا إعادة ريندر:
        # الريندر الثاني ممنوع (يرفع) ومع ذلك ينجح الإنتاج.
        if not os.path.isfile(long_video.DEFAULT_HEADLESS_EDITOR):
            self.skipTest("headless-editor غير متاح")
        cache = StageCache(root=os.path.join(self.tmp.name, "cache"))
        spec = self._spec(width=640, height=360)
        out = os.path.join(self.tmp.name, "draft.mp4")
        first = long_video.build_fast_draft(spec, out, cache=cache)
        self.assertFalse(first["report"]["cache_hit"])
        self.assertTrue(os.path.isfile(out))
        # التخزين record في مكانه: المخرج نفسه هو النسخة المخزّنة،
        # فيبقى في مكانه؛ والاستدعاء الثاني يجب أن ينجح بلا ريندر
        # (الريندر ممنوع هنا) وبلا إعادة كتابة للملف.
        before = os.stat(out)
        with mock.patch.object(
                long_video.headless_stage, "render_project",
                side_effect=AssertionError("يجب ألا يُعاد الريندر")):
            second = long_video.build_fast_draft(spec, out, cache=cache)
        self.assertTrue(second["report"]["cache_hit"])
        self.assertEqual(second["report"].get("reused"), ["video"])
        self.assertTrue(os.path.isfile(out))
        after = os.stat(out)
        self.assertEqual(after.st_size, before.st_size)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        self.assertAlmostEqual(second["duration"], first["duration"])


class TestImproveMotion(unittest.TestCase):
    """ترقية الحركة improve_motion (الموجة الأولى، الطلب 1)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.intro_wav = os.path.join(self.tmp.name, "intro.wav")
        _make_wav(self.intro_wav, seconds=2)
        self.img = os.path.join(self.tmp.name, "a.jpg")
        _make_jpg(self.img)
        # مقطع مولَّد واحد (7 ثوانٍ) يغطي فصلًا 7 ثوانٍ عبر
        # توليد a ‏(5.04 ث) + تجميد آخر إطار (1.96 ث).
        self.motion_dir = os.path.join(self.tmp.name, "motion")
        os.makedirs(self.motion_dir)
        _make_video(os.path.join(self.motion_dir, "gen1-a.mp4"),
                    seconds=7)
        manifest = {
            "generation_seconds": 5.04,
            "clips": [{"clip_id": "clip1", "generations": ["gen1-a"],
                       "duration_needed_s": 7.0, "coverage_note": ""}],
            "generations_list": [
                {"gen_id": "gen1-a", "clip_id": "clip1",
                 "output_name": "gen1-a.mp4", "scene": "chapter 1",
                 "take": "a", "first_frame": ""}]}
        self.manifest_path = os.path.join(self.tmp.name, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        ch_wav = os.path.join(self.tmp.name, "ch.wav")
        _make_wav(ch_wav, seconds=7)
        self.chapter = {
            "title": "قصة", "moral": "عبرة", "narration": ch_wav,
            "duration": 7.0, "images": [self.img],
            "phrases": [{"start": 0.0, "end": 7.0,
                         "text": "نص تجريبي طويل",
                         "words": long_video.estimate_word_times(
                             "نص تجريبي طويل", 0.0, 7.0)}]}
        self.spec = {
            "title": "تجربة", "hook": "هوك",
            "intro": {"text": "هوك", "narration": self.intro_wav,
                      "duration": 2.0},
            "outro": {"text": "اشترك", "narration": self.intro_wav,
                      "duration": 2.0},
            "chapters": [self.chapter], "music": None,
            "width": 640, "height": 360, "fps": 30}
        self.cache = StageCache(root=os.path.join(self.tmp.name, "cache"))
        self.freeze_dir = os.path.join(self.tmp.name, "freezes")

    def tearDown(self):
        self.tmp.cleanup()

    def test_freeze_frame_cached_and_reused(self):
        # أول استدعاء يولّد الإطار المجمّد مرة واحدة؛ والثاني
        # يعيد استخدامه بلا إعادة استخراج (extract_last_frame
        # يُستدعى مرة واحدة فقط عبر الاستدعاءين).
        calls = []
        orig = motion_clips.extract_last_frame

        def counting(src, out):
            calls.append((src, out))
            return orig(src, out)

        with mock.patch.object(long_video.motion_clips,
                               "extract_last_frame", counting):
            first = long_video.improve_motion(
                self.spec, self.manifest_path, self.motion_dir,
                cache=self.cache, freeze_dir=self.freeze_dir)
            second = long_video.improve_motion(
                self.spec, self.manifest_path, self.motion_dir,
                cache=self.cache, freeze_dir=self.freeze_dir)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first["motion"], "clips")
        self.assertEqual(first["generated"], ["chapter-1-freeze-1"])
        self.assertEqual(first["reused"], [])
        self.assertEqual(second["reused"], ["chapter-1-freeze-1"])
        self.assertEqual(second["generated"], [])
        segs1 = first["spec"]["chapters"][0]["motion_segments"]
        segs2 = second["spec"]["chapters"][0]["motion_segments"]
        self.assertEqual(segs1, segs2)
        self.assertEqual(segs1[0]["kind"], "video")
        self.assertEqual(segs1[1]["kind"], "image")
        self.assertTrue(os.path.isfile(segs1[1]["src"]))
        # الإطار المجمّد المعاد استخدامه نسخة التخزين (داخل جذره)
        self.assertTrue(segs1[1]["src"].startswith(
            os.path.join(self.tmp.name, "cache")))
        # spec الأصلية لا تُعدَّل
        self.assertNotIn("motion", self.spec)
        self.assertNotIn("motion_segments", self.spec["chapters"][0])
        # الناتج يبني مشروعًا صالحًا بمقطع فيديو فعلي
        project, meta = long_video.build_project(second["spec"])
        self.assertEqual(meta["motion"], "clips")
        videos = [t for t in project["tracks"] if t["type"] == "video"]
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["volume"], 0)

    def test_without_cache_still_works(self):
        result = long_video.improve_motion(
            self.spec, self.manifest_path, self.motion_dir,
            cache=None, freeze_dir=self.freeze_dir)
        self.assertEqual(result["generated"], ["chapter-1-freeze-1"])
        self.assertEqual(result["reused"], [])
        segs = result["spec"]["chapters"][0]["motion_segments"]
        self.assertEqual(segs[1]["kind"], "image")
        self.assertTrue(os.path.isfile(segs[1]["src"]))
        self.assertTrue(segs[1]["src"].startswith(self.freeze_dir))
        project, meta = long_video.build_project(result["spec"])
        self.assertEqual(meta["motion"], "clips")

    def test_missing_manifest_raises(self):
        with self.assertRaises(long_video.LongVideoError):
            long_video.improve_motion(
                self.spec, "/nonexistent/manifest.json", self.motion_dir,
                cache=self.cache, freeze_dir=self.freeze_dir)


if __name__ == "__main__":
    unittest.main()
