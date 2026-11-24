#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تقطيع الفيديو الطويل إلى شورتات (lib.shorts_cut).

تعمل بـ `python3 -m unittest tests.test_shorts_cut -v` من مجلد
studio. الوسائط تُولَّد محليًا بـffmpeg (بلا شبكة): فيديو
طويل 150 ثانية بثلاثة مقاطع كلام واضحة يفصلها صمت، وفيديو
صامت تمامًا.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import shorts_cut


def _run(cmd):
    subprocess.run(cmd, check=True, timeout=300,
                   capture_output=True, text=True)


def _make_audio(path):
    """صوت 150 ث: نغمة 50ث + صمت 2ث + نغمة 50ث + صمت 2ث + نغمة 46ث."""
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=50",
          "-t", "2", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
          "-f", "lavfi", "-i", "sine=frequency=660:duration=50",
          "-t", "2", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=46",
          "-filter_complex",
          "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1[a]",
          "-map", "[a]", "-c:a", "pcm_s16le", path])


def _make_video(path, audio=None, seconds=150, width=1280, height=720):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i",
           "testsrc=size=%dx%d:rate=15:duration=%d"
           % (width, height, seconds)]
    if audio:
        cmd += ["-i", audio]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", path]
    _run(cmd)


def _make_silent_video(path, seconds=50):
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i",
          "testsrc=size=1280x720:rate=15:duration=%d" % seconds,
          "-f", "lavfi", "-i",
          "anullsrc=r=44100:cl=mono",
          "-t", str(seconds),
          "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-shortest", path])


class TestSpeechSegments(unittest.TestCase):
    def test_complement_of_silences(self):
        segs = shorts_cut.detect_speech_segments(
            100.0, [(10.0, 12.0, 2.0), (50.0, 51.0, 1.0)])
        self.assertEqual(segs, [(0.0, 10.0), (12.0, 50.0), (51.0, 100.0)])

    def test_short_gap_merged(self):
        # فجوة 0.5ث داخل جملة تُدمج ولا تقطع المقطع.
        segs = shorts_cut.detect_speech_segments(
            100.0, [(10.0, 10.5, 0.5)])
        self.assertEqual(segs, [(0.0, 100.0)])

    def test_unclosed_silence_closes_at_duration(self):
        segs = shorts_cut.detect_speech_segments(
            60.0, [(20.0, None, None)])
        self.assertEqual(segs, [(0.0, 20.0)])

    def test_fully_silent_has_no_segments(self):
        segs = shorts_cut.detect_speech_segments(
            60.0, [(0.0, 60.0, 60.0)])
        self.assertEqual(segs, [])


class TestCandidateWindows(unittest.TestCase):
    def test_windows_from_segments(self):
        segs = [(0.0, 50.0), (52.0, 102.0), (104.0, 150.0)]
        wins = shorts_cut.candidate_windows(segs)
        self.assertEqual([(w[0], w[1]) for w in wins],
                         [(0.0, 50.0), (52.0, 102.0), (104.0, 150.0)])

    def test_oversized_segment_cut_at_max(self):
        wins = shorts_cut.candidate_windows([(0.0, 100.0)])
        self.assertEqual(len(wins), 1)
        self.assertEqual((wins[0][0], wins[0][1]), (0.0, 60.0))

    def test_short_speech_produces_no_window(self):
        self.assertEqual(
            shorts_cut.candidate_windows([(0.0, 20.0)]), [])


class TestScoring(unittest.TestCase):
    def test_deterministic_same_inputs(self):
        segs = [(0.0, 50.0), (52.0, 102.0)]
        window = (0.0, 50.0, 50.0)
        first = shorts_cut.score_window(window, segs)
        second = shorts_cut.score_window(window, segs)
        self.assertEqual(first, second)

    def test_hook_word_raises_score(self):
        segs = [(0.0, 50.0)]
        window = (0.0, 50.0, 50.0)
        plain, _ = shorts_cut.score_window(window, segs)
        hook_phrases = [{"start": 0.0, "end": 5.0,
                         "text": "فجأة طرق الباب"}]
        hooked, _ = shorts_cut.score_window(window, segs, hook_phrases)
        self.assertGreater(hooked, plain)
        self.assertAlmostEqual(hooked, 1.0)

    def test_mid_speech_cut_loses_completeness(self):
        segs = [(0.0, 100.0)]
        full, _ = shorts_cut.score_window((0.0, 50.0, 50.0),
                                          [(0.0, 50.0)])
        cut, _ = shorts_cut.score_window((0.0, 60.0, 60.0), segs)
        self.assertGreater(full, cut)

    def test_ranking_orders_by_score_then_start(self):
        segs = [(0.0, 50.0), (52.0, 102.0)]
        wins = [(0.0, 50.0, 50.0), (52.0, 102.0, 50.0)]
        phrases = [{"start": 52.0, "end": 57.0,
                    "text": "فجأة انقلب كل شيء"}]
        ranked = shorts_cut.rank_windows(wins, segs, phrases)
        self.assertEqual(ranked[0]["start"], 52.0)
        self.assertEqual(ranked[1]["start"], 0.0)


class TestCutShortsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="shorts-cut-")
        cls.audio = os.path.join(cls.tmp, "audio.wav")
        _make_audio(cls.audio)
        cls.video = os.path.join(cls.tmp, "long.mp4")
        _make_video(cls.video, audio=cls.audio)

    def test_long_video_cuts_expected_count(self):
        out = os.path.join(self.tmp, "out")
        results = shorts_cut.cut_shorts(self.video, out, count=3)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(os.path.isfile(r["output"]))
            info = check_lib.probe(r["output"])
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            self.assertGreaterEqual(info["duration"], 39.0)
            self.assertLessEqual(info["duration"], 61.0)
            self.assertGreater(r["score"], 0.0)
            self.assertIn("كثافة كلام", r["reason"])

    def test_cut_is_deterministic(self):
        out1 = os.path.join(self.tmp, "out-a")
        out2 = os.path.join(self.tmp, "out-b")
        r1 = shorts_cut.cut_shorts(self.video, out1, count=3)
        r2 = shorts_cut.cut_shorts(self.video, out2, count=3)
        self.assertEqual(
            [(r["start"], r["end"], r["score"]) for r in r1],
            [(r["start"], r["end"], r["score"]) for r in r2])

    def test_captions_ass_bottom_only(self):
        phrases = [{"start": 1.0, "end": 4.0, "text": "في نص الليل"},
                   {"start": 5.0, "end": 9.0, "text": "فجأة طرق الباب"},
                   {"start": 60.0, "end": 64.0, "text": "عبارة لاحقة"}]
        out = os.path.join(self.tmp, "out-cap")
        results = shorts_cut.cut_shorts(self.video, out, count=1,
                                        phrases=phrases)
        self.assertEqual(len(results), 1)
        ass_path = results[0]["captions"]
        self.assertIsNotNone(ass_path)
        with open(ass_path, encoding="utf-8") as f:
            text = f.read()
        # عبارتا النافذة الأولى فقط، مُزاحتان؛ وعبارة 60ث خارجها.
        self.assertIn("في نص الليل", text)
        self.assertIn("فجأة طرق الباب", text)
        self.assertNotIn("عبارة لاحقة", text)
        # محاذاة 2 = أسفل الشاشة فقط (نمط whisper_captions).
        self.assertIn(",2,40,40,60,1", text)

    def test_silent_video_produces_no_shorts(self):
        silent = os.path.join(self.tmp, "silent.mp4")
        _make_silent_video(silent)
        out = os.path.join(self.tmp, "out-silent")
        self.assertEqual(shorts_cut.cut_shorts(silent, out), [])

    def test_missing_file_raises_arabic_error(self):
        with self.assertRaises(shorts_cut.ShortsCutError):
            shorts_cut.cut_shorts(os.path.join(self.tmp, "nope.mp4"),
                                  os.path.join(self.tmp, "out-x"))

    def test_bad_count_raises(self):
        with self.assertRaises(shorts_cut.ShortsCutError):
            shorts_cut.cut_shorts(self.video,
                                  os.path.join(self.tmp, "out-y"),
                                  count=0)

    def test_report_mentions_shorts(self):
        out = os.path.join(self.tmp, "out-rep")
        results = shorts_cut.cut_shorts(self.video, out, count=2)
        report = shorts_cut.format_report(results, self.video)
        self.assertIn("عدد الشورتات: 2", report)
        self.assertIn("short-01.mp4", report)
        empty = shorts_cut.format_report([], self.video)
        self.assertIn("لا شورتات", empty)


if __name__ == "__main__":
    unittest.main()
