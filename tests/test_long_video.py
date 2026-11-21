#!/usr/bin/env python3
"""اختبارات الفيديو الطويل (lib.long_video) + الصورة الأفقية.

تعمل بـ `python3 -m unittest discover -s tests -v`.
الوسائط التجريبية صغيرة وتُولَّد بـffmpeg محليًا (بلا شبكة).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import long_video
from lib import thumbnail

ASS_FIXTURE = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Naskh Arabic,52,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,40,40,60,1
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


if __name__ == "__main__":
    unittest.main()
